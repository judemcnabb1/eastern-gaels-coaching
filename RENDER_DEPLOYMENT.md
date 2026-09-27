# Eastern Gaels V8 — Render Deployment

This package is based on the working V8 Native Course Preview build.

## Render settings

Create a Render Web Service from this repository, or use `render.yaml`.

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python eastern_gaels_v7.py`
- Health check: `/`
- Persistent disk mount path: `/var/data`
- Environment variable: `DATA_DIR=/var/data`
- Secret environment variable: `ADMIN_PASSWORD=<choose a strong password>`

The application reads Render's `PORT` environment variable automatically.

## Persistent data

The SQLite database and uploaded spreadsheet data are written to `DATA_DIR`.
On Render this is `/var/data`, so attach the persistent disk there.

Do not put the admin password in the repository. Set `ADMIN_PASSWORD` in
Render's Environment settings.

## First deployment

The bundled Club demographics workbook and Schools timetable are included as
seed/reference files. After deployment, use the two Admin uploaders to load the
latest versions. Subsequent uploaded data is stored on the persistent disk.
