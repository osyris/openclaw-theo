#!/usr/bin/env python3
"""iCloud Calendar management via CalDAV."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import caldav

ICLOUD_CALDAV_URL = "https://caldav.icloud.com"
TZ_OFFSET = timezone(timedelta(hours=2))  # UTC+2


def get_client():
    email = os.environ.get("ICLOUD_EMAIL")
    password = os.environ.get("ICLOUD_APP_PASSWORD")
    if not email or not password:
        print("Error: ICLOUD_EMAIL and ICLOUD_APP_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)
    return caldav.DAVClient(url=ICLOUD_CALDAV_URL, username=email, password=password)


def parse_dt(s):
    """Parse datetime string in various formats."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=TZ_OFFSET)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s}")


def cmd_calendars(args):
    client = get_client()
    principal = client.principal()
    calendars = principal.calendars()
    result = []
    for cal in calendars:
        result.append({"name": cal.name, "id": str(cal.id), "url": str(cal.url)})
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_list(args):
    client = get_client()
    principal = client.principal()
    calendars = principal.calendars()

    start = parse_dt(args.start) if args.start else datetime.now(TZ_OFFSET).replace(hour=0, minute=0, second=0)
    end = parse_dt(args.end) if args.end else start + timedelta(days=7)

    all_events = []
    for cal in calendars:
        try:
            events = cal.date_search(start=start, end=end, expand=True)
        except Exception:
            continue
        for event in events:
            try:
                vevent = event.vobject_instance.vevent
                uid = str(vevent.uid.value) if hasattr(vevent, "uid") else "unknown"
                summary = str(vevent.summary.value) if hasattr(vevent, "summary") else "(no title)"
                dtstart = vevent.dtstart.value if hasattr(vevent, "dtstart") else None
                dtend = vevent.dtend.value if hasattr(vevent, "dtend") else None

                ev = {
                    "uid": uid,
                    "title": summary,
                    "calendar": cal.name,
                    "start": str(dtstart) if dtstart else None,
                    "end": str(dtend) if dtend else None,
                }

                if hasattr(vevent, "location"):
                    ev["location"] = str(vevent.location.value)
                if hasattr(vevent, "description"):
                    ev["description"] = str(vevent.description.value)

                all_events.append(ev)
            except Exception as e:
                all_events.append({"error": str(e), "calendar": cal.name})

    all_events.sort(key=lambda x: x.get("start") or "")
    print(json.dumps(all_events, indent=2, ensure_ascii=False, default=str))


def cmd_add(args):
    client = get_client()
    principal = client.principal()
    calendars = principal.calendars()

    target_cal = None
    if args.calendar:
        for cal in calendars:
            if cal.name.lower() == args.calendar.lower():
                target_cal = cal
                break
        if not target_cal:
            print(f"Error: Calendar '{args.calendar}' not found", file=sys.stderr)
            sys.exit(1)
    else:
        target_cal = calendars[0] if calendars else None
        if not target_cal:
            print("Error: No calendars found", file=sys.stderr)
            sys.exit(1)

    start = parse_dt(args.start)
    end = parse_dt(args.end) if args.end else start + timedelta(hours=1)

    import uuid
    uid = str(uuid.uuid4())

    vcal = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OpenClaw//iCloud Calendar Skill//EN
BEGIN:VEVENT
UID:{uid}
DTSTART:{start.strftime('%Y%m%dT%H%M%S')}
DTEND:{end.strftime('%Y%m%dT%H%M%S')}
SUMMARY:{args.title}
{f'LOCATION:{args.location}' if args.location else ''}
{f'DESCRIPTION:{args.description}' if args.description else ''}
END:VEVENT
END:VCALENDAR"""

    # Clean up empty lines from optional fields
    vcal = "\n".join(line for line in vcal.split("\n") if line.strip())

    event = target_cal.save_event(vcal)
    print(json.dumps({"ok": True, "uid": uid, "calendar": target_cal.name, "title": args.title, "start": str(start), "end": str(end)}, indent=2, ensure_ascii=False))


def cmd_edit(args):
    client = get_client()
    principal = client.principal()
    calendars = principal.calendars()

    for cal in calendars:
        try:
            event = cal.event_by_uid(args.uid)
        except Exception:
            continue

        vevent = event.vobject_instance.vevent
        if args.title:
            vevent.summary.value = args.title
        if args.start:
            vevent.dtstart.value = parse_dt(args.start)
        if args.end:
            vevent.dtend.value = parse_dt(args.end)
        if args.location:
            if hasattr(vevent, "location"):
                vevent.location.value = args.location
            else:
                vevent.add("location").value = args.location

        event.save()
        print(json.dumps({"ok": True, "uid": args.uid, "message": "Event updated"}, indent=2))
        return

    print(json.dumps({"ok": False, "error": f"Event with UID {args.uid} not found"}), file=sys.stderr)
    sys.exit(1)


def cmd_delete(args):
    client = get_client()
    principal = client.principal()
    calendars = principal.calendars()

    for cal in calendars:
        try:
            event = cal.event_by_uid(args.uid)
            event.delete()
            print(json.dumps({"ok": True, "uid": args.uid, "message": "Event deleted"}, indent=2))
            return
        except Exception:
            continue

    print(json.dumps({"ok": False, "error": f"Event with UID {args.uid} not found"}), file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="iCloud Calendar management via CalDAV")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # calendars
    subparsers.add_parser("calendars", help="List all calendars")

    # list
    p_list = subparsers.add_parser("list", help="List events")
    p_list.add_argument("--from", dest="start", help="Start date (YYYY-MM-DD)")
    p_list.add_argument("--to", dest="end", help="End date (YYYY-MM-DD)")

    # add
    p_add = subparsers.add_parser("add", help="Add an event")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--start", required=True)
    p_add.add_argument("--end")
    p_add.add_argument("--calendar")
    p_add.add_argument("--location")
    p_add.add_argument("--description")

    # edit
    p_edit = subparsers.add_parser("edit", help="Edit an event")
    p_edit.add_argument("--uid", required=True)
    p_edit.add_argument("--title")
    p_edit.add_argument("--start")
    p_edit.add_argument("--end")
    p_edit.add_argument("--location")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete an event")
    p_del.add_argument("--uid", required=True)

    args = parser.parse_args()

    commands = {
        "calendars": cmd_calendars,
        "list": cmd_list,
        "add": cmd_add,
        "edit": cmd_edit,
        "delete": cmd_delete,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
