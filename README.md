# Scouts Only (ASU-siteweb)

Flask web platform with a public website + admin dashboard (SQLite + SQLAlchemy) and multi-language support (Flask-Babel).

## Quick start (Windows / PowerShell)
1) Install Python (recommended: python.org installer, not Microsoft Store).
2) Create a virtual environment and install deps:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
3) Run:
```powershell
python app.py
```
Open `http://localhost:5000/`.

## Important (security / production)
- Set `SECRET_KEY` in the environment for any non-local deployment.
- Don’t run with `debug=True` in production.
- The app seeds sample data and may create a default admin user on first run (see `SETUP.md`).
