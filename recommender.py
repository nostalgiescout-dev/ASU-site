"""
Simple "look-alike users" recommender.

This is intentionally dependency-free (no numpy/sklearn) and relies on:
- UserProfile (preferences + locale)
- UserInteraction (events like views/purchases)
"""

from __future__ import annotations

from typing import Iterable

from models import db, Activity, UserProfile, UserInteraction, cosine_similarity_sets


def get_or_create_profile(user_key: str, *, locale: str | None = None) -> UserProfile:
    profile = UserProfile.query.filter_by(user_key=user_key).first()
    if profile:
        if locale and not profile.locale:
            profile.locale = locale
            db.session.commit()
        return profile

    profile = UserProfile(user_key=user_key, locale=locale or None)
    db.session.add(profile)
    db.session.commit()
    return profile


def update_profile_preferences(
    user_key: str,
    *,
    locale: str | None = None,
    preferred_club_ids: Iterable[str] | None = None,
    preferred_unit_ids: Iterable[str] | None = None,
) -> UserProfile:
    profile = get_or_create_profile(user_key, locale=locale)
    profile.set_preferences(
        preferred_club_ids=list(preferred_club_ids) if preferred_club_ids is not None else None,
        preferred_unit_ids=list(preferred_unit_ids) if preferred_unit_ids is not None else None,
        locale=locale,
    )
    db.session.commit()
    return profile


def record_interaction(
    user_key: str,
    *,
    item_type: str,
    item_id: str,
    event_type: str,
    weight: int = 1,
    commit: bool = True,
) -> None:
    interaction = UserInteraction(
        user_key=user_key,
        item_type=item_type,
        item_id=str(item_id),
        event_type=event_type,
        weight=int(weight or 1),
    )
    db.session.add(interaction)
    if commit:
        db.session.commit()


def _similarity(target: UserProfile | None, candidate: UserProfile) -> float:
    if not target:
        return 0.0

    target_locale = (target.locale or "").strip()
    candidate_locale = (candidate.locale or "").strip()

    target_clubs = target.preferred_club_ids()
    candidate_clubs = candidate.preferred_club_ids()

    sim_clubs = cosine_similarity_sets(target_clubs, candidate_clubs)
    sim_locale = 1.0 if target_locale and target_locale == candidate_locale else 0.0

    if not target_clubs:
        return sim_locale

    return 0.8 * sim_clubs + 0.2 * sim_locale


def recommend_activities_for_user(
    user_key: str,
    *,
    locale: str | None = None,
    limit: int = 12,
    neighbor_count: int = 25,
    min_similarity: float = 0.05,
) -> list[dict]:
    """
    Returns a list of activity dicts (Activity.to_dict()) with an added "score".
    """
    limit = max(1, min(int(limit or 12), 50))
    neighbor_count = max(1, min(int(neighbor_count or 25), 200))

    target_profile = UserProfile.query.filter_by(user_key=user_key).first()
    if target_profile and locale and not target_profile.locale:
        target_profile.locale = locale
        db.session.commit()

    # Find similar users (look-alikes) by profile preferences.
    candidate_profiles = (
        UserProfile.query.filter(UserProfile.user_key != user_key)
        .order_by(UserProfile.updated_at.desc())
        .limit(750)
        .all()
    )

    neighbors: list[tuple[str, float]] = []
    for candidate in candidate_profiles:
        sim = _similarity(target_profile, candidate)
        if sim >= float(min_similarity):
            neighbors.append((candidate.user_key, sim))
    neighbors.sort(key=lambda x: x[1], reverse=True)
    neighbors = neighbors[:neighbor_count]

    # Exclude items already seen by this user.
    seen_rows = (
        UserInteraction.query.filter_by(user_key=user_key, item_type="activity")
        .with_entities(UserInteraction.item_id)
        .all()
    )
    seen_activity_ids = {row[0] for row in seen_rows}

    # Score items based on interactions from similar users.
    scores: dict[str, float] = {}
    if neighbors:
        neighbor_keys = [n[0] for n in neighbors]
        sim_by_key = {n[0]: float(n[1]) for n in neighbors}

        interaction_rows = (
            UserInteraction.query.filter(UserInteraction.user_key.in_(neighbor_keys))
            .filter_by(item_type="activity")
            .with_entities(
                UserInteraction.user_key,
                UserInteraction.item_id,
                UserInteraction.weight,
            )
            .all()
        )

        for neighbor_key, item_id, weight in interaction_rows:
            if item_id in seen_activity_ids:
                continue
            scores[item_id] = scores.get(item_id, 0.0) + (sim_by_key.get(neighbor_key, 0.0) * float(weight or 1))

    # If we have no collaborative signal, fallback to popular activities.
    if not scores:
        fallback = (
            Activity.query.order_by(Activity.views.desc(), Activity.date.desc())
            .limit(limit)
            .all()
        )
        return [{**a.to_dict(), "score": None, "reason": "popular"} for a in fallback]

    # Fetch activities and return top-N.
    activity_ids_sorted = [k for k, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
    activity_ids_sorted = activity_ids_sorted[: max(limit * 3, limit)]

    activities = Activity.query.filter(Activity.id.in_(activity_ids_sorted)).all()
    activity_by_id = {a.id: a for a in activities}

    results: list[dict] = []
    for activity_id in activity_ids_sorted:
        activity = activity_by_id.get(activity_id)
        if not activity:
            continue
        results.append({**activity.to_dict(), "score": round(scores.get(activity_id, 0.0), 6), "reason": "lookalike"})
        if len(results) >= limit:
            break

    if results:
        return results

    fallback = Activity.query.order_by(Activity.views.desc(), Activity.date.desc()).limit(limit).all()
    return [{**a.to_dict(), "score": None, "reason": "popular"} for a in fallback]
