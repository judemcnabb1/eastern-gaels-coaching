# Eastern Gaels Schools Coaching — V3

V3 adds a visual coaching dashboard with:
- completed sessions, programme completion %, coaching hours and attendance KPIs
- completed sessions by month
- session-status visual summary
- completed sessions by school and by coach
- school progress cards
- clickable school/coach drill-down reports
- CSV export for admins
- all V2 past-due session features

## Upgrade from V2 on Windows
1. Stop V2 with Ctrl+C in its Command Prompt.
2. Extract this V3 ZIP to a new folder.
3. Copy `eastern_gaels.db` from your V2 folder into the V3 folder (replace the empty/new one if present).
4. In the V3 folder address bar type `cmd` and press Enter.
5. Run: `python app.py`
6. Open http://localhost:8000 and click Reports.

Your existing users, completed statuses, attendance and notes live in `eastern_gaels.db`, so copying that database preserves them.
