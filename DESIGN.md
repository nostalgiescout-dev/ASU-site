# Design System Specification: The Digital Trail

## 1. Overview & Creative North Star
### Creative North Star: "The Modern Pathfinder"
This design system moves away from the rigid, institutional aesthetic of traditional youth organizations. Instead, it adopts a **"High-End Editorial"** approach that feels like a premium outdoor lifestyle magazine. We are not just building a portal; we are creating a digital campfire.

The system is defined by **Organic Asymmetry** and **Tonal Depth**. We bypass the "template" look by using exaggerated white space, overlapping imagery, and a sophisticated layering of earth-toned surfaces. The goal is to evoke the feeling of nature—not through literal textures, but through a layout that breathes and flows naturally from right to left.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the scouting tradition but elevated through a Material 3 tonal logic. We utilize a rich forest green for authority and an earth-toned secondary palette for warmth.

### Core Palette (Material Tokens)
* **Primary:** `#0d631b` (The Forest Canopy - used for main brand actions)
* **Primary Container:** `#2e7d32` (Deep Foliage - used for hero backgrounds)
* **Secondary:** `#77574d` (The Earth - used for grounded, supportive elements)
* **Surface:** `#fbfbe2` (Warm Parchment - the base of our digital world)
* **On-Surface:** `#1b1d0e` (Night Sky - for high-contrast legibility)

### The "No-Line" Rule
**Borders are prohibited for sectioning.** To create distinction between content areas, use background color shifts only.
* *Example:* Place a `surface-container-low` section (#f5f5dc) directly against a `surface` (#fbfbe2) background. The subtle shift in warmth is enough to signal a transition without the "boxed-in" feeling of a line.

### Surface Hierarchy & Nesting
Treat the UI as physical layers. Use the `surface-container` tiers to define "altitude":
* **Surface (Base):** The wide-open background.
* **Surface-Container-Low:** For secondary content blocks.
* **Surface-Container-Highest:** For high-priority interactive cards.
* **Glassmorphism:** For floating navigation or modal overlays, use `surface` at 70% opacity with a `20px` backdrop blur. This allows the "nature" of the background to bleed through, softening the interface.

---

## 3. Typography
The system uses a dual-font strategy to balance character with utility. While the technical tokens use Plus Jakarta Sans and Be Vietnam Pro, these must be mapped to **Cairo** or **Almarai** for Arabic RTL implementation to maintain the "Modern Pathfinder" spirit.

### Typography Scale
* **Display (Large/Medium):** `beVietnamPro` / 3.5rem – 2.75rem. Used for aspirational headlines. These should use tight letter-spacing and an intentional "hanging" alignment in RTL layouts.
* **Headline (Small/Medium):`beVietnamPro` / 1.5rem – 1.75rem. The "Editorial" voice. Use these for section titles with generous bottom margins.
* **Body (Large/Medium):`plusJakartaSans` / 1rem – 0.875rem. Optimized for long-form reading about scout values and activity descriptions.
* **Label:** `plusJakartaSans` / 0.75rem. Used for "Unit" tags (e.g., Cubs, Venturers) in all-caps or heavy weight.

---

## 4. Elevation & Depth
We eschew traditional "box shadows" in favor of **Tonal Layering**.

* **The Layering Principle:** Depth is achieved by "stacking." A card using `surface-container-lowest` (#ffffff) sitting on a `surface-container-low` (#f5f5dc) background creates a natural lift.
* **Ambient Shadows:** If a card must float (e.g., a "Join Now" CTA), use a shadow tinted with the brand color: `rgba(13, 99, 27, 0.06)` with a `32px` blur and `8px` Y-offset. Shadows should look like soft light filtering through trees, not a harsh drop shadow.
* **The "Ghost Border" Fallback:** If a layout requires a container edge for accessibility, use the `outline-variant` token (#bfcaba) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### The "Pathfinder" Hero Section
A bold, asymmetric layout. The headline should be right-aligned (RTL), with an image or organic shape overlapping the background container. Use a `surface-tint` (#1b6d24) gradient for the CTA to give it "soul" and depth.

### Buttons
* **Primary:** High-pill shape (`rounded-full`). Background: `primary` (#0d631b). Text: `on-primary` (#ffffff). No borders.
* **Secondary:** `rounded-full`. Background: `secondary-container` (#fed3c7). Text: `on-secondary-container` (#795950).
* **Interactive State:** On hover, apply a subtle scale-up (1.02x) rather than just a color change to mimic a friendly, tactile response.

### Activity Cards
* **Layout:** Strictly forbid divider lines.
* **Structure:** Use a `1.5rem` (xl) corner radius. Place the image at the top with no padding, and use `surface-container-highest` for the text area.
* **Spacing:** Use "Breathing Room" (32px padding) within cards to ensure the youth-focused content feels approachable.

### Input Fields
* **Style:** Soft-filled fields using `surface-variant`. Avoid high-contrast outlines.
* **Focus State:** A `2px` glow using `primary` at 30% opacity.

---

## 6. Do’s and Don’ts

### Do:
* **Do** embrace asymmetry. Let images break the grid lines to create a sense of outdoor adventure.
* **Do** use RTL-specific iconography. Arrows and directional icons must be flipped to point "forward" in the Arabic reading flow.
* **Do** use "Editorial Spacing." If you think there is enough white space, add 20% more.

### Don’t:
* **Don’t** use black (#000000) for text. Always use `on-surface` (#1b1d0e) to maintain the warm, organic feel.
* **Don’t** use 1px solid borders. They create a "digital" feel that contradicts the outdoor, scout-inspired mission.
* **Don’t** use sharp corners. Every element should have at least a `0.5rem` (md) radius to feel "friendly" and "youth-oriented."
