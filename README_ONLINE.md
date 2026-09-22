# Eastern Gaels Coaching — Online-ready V3

This package is V3 prepared for deployment to a small Docker-capable web host.

## What changed
- Reads the host-provided `PORT` automatically.
- Supports a persistent data directory via `DATA_DIR`.
- Supports an explicit database path via `DATABASE_PATH`.
- Can mark the login cookie `Secure` in HTTPS production using `COOKIE_SECURE=1`.
- Includes a `Dockerfile`, `.dockerignore`, and an example `render.yaml` deployment definition.
- The existing Windows/local workflow still works: `python app.py`.

## Your existing database
Before deployment, keep a backup copy of `eastern_gaels.db`. Do not commit a live database containing user accounts/password hashes to a public Git repository.

For a hosted deployment, the database must live on persistent storage. Set `DATA_DIR` to that persistent disk's mount path. On a new deployment the app creates a fresh database and asks you to create the first administrator. If you want to carry your existing records online, copy your existing `eastern_gaels.db` onto the host's persistent disk before using the production app.

## Production settings
Set:
- `DATA_DIR` = persistent disk path (example `/data`)
- `COOKIE_SECURE` = `1` when served over HTTPS
- `PORT` is normally supplied by the hosting provider

## Backups
Back up the persistent `eastern_gaels.db` regularly. The Admin CSV export is useful for reporting but is not a complete database backup because it does not contain users/audit data.

## Important limitation before wider use
V3 stores active login sessions in server memory. This is acceptable for one small app instance, but restarting the service logs everyone out. It does not lose timetable/session records. For a larger deployment, move login sessions to the database or another persistent session store.
