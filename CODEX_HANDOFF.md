# Codex Handoff

Run `./start.sh`, then open `http://127.0.0.1:5174`. The backend source of truth is `backend/app/seed.py`; avoid adding business fixtures to React components. API routes live in `backend/app/main.py`, and mutable demonstration behavior is in `backend/app/services.py`.

Before changing provider behavior, retain the explicit Mock/Implemented/Planned distinction in the README and Settings UI. Run backend tests, frontend tests, and `npm run build` before committing.
