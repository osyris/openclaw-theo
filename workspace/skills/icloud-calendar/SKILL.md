---
name: icloud_calendar
description: Manage iCloud Calendar — read, create, edit, and delete events via CalDAV
metadata: {"openclaw": {"requires": {"env": ["ICLOUD_EMAIL", "ICLOUD_APP_PASSWORD"], "bins": ["uv"]}, "primaryEnv": "ICLOUD_APP_PASSWORD"}}
---

# iCloud Calendar Skill

Manage events in an iCloud Calendar using CalDAV protocol.

## Usage

All commands are run via `uv run` from the skill directory `{baseDir}`:

```bash
# List events for a date range (defaults to today + 7 days)
uv run --with caldav --with vobject python3 {baseDir}/ical.py list --from YYYY-MM-DD --to YYYY-MM-DD

# List all calendars
uv run --with caldav --with vobject python3 {baseDir}/ical.py calendars

# Add an event
uv run --with caldav --with vobject python3 {baseDir}/ical.py add --title "Meeting" --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM" [--calendar "Calendar Name"]

# Edit an event
uv run --with caldav --with vobject python3 {baseDir}/ical.py edit --uid <event-uid> --title "New Title" --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"

# Delete an event
uv run --with caldav --with vobject python3 {baseDir}/ical.py delete --uid <event-uid>
```

## Environment Variables

- `ICLOUD_EMAIL` — Apple ID email
- `ICLOUD_APP_PASSWORD` — App-specific password (generate at appleid.apple.com)

## Notes

- Dates without times default to 00:00.
- If `--calendar` is not specified, the default calendar is used.
- Event UIDs are returned by `list` and `add` commands.
- All times are treated as local time (UTC+2 for Natalia).
