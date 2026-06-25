#!/usr/bin/env python3
"""
auth-monitor — deterministic model-auth expiry reporter for the OpenClaw bot.

Runs from the HOST cron via `docker exec` so it survives a dead model (it must
not depend on the very thing it watches). Uses only native harness commands:
  - `openclaw models status --json`  → read provider OAuth/token health (no inference)
  - `openclaw message send`          → report to the user's main channel (bot token, no inference)

Reports to the MAIN user channel (the chat where the user talks with the agent),
phrased as the bot reporting its own state. Debounced so it doesn't spam.

Lives in /data so it survives Coolify redeploys.

Usage:
  auth-monitor.py            # check + (maybe) notify, update state
  auth-monitor.py --dry      # compute + print decision, do NOT send, do NOT touch state
  auth-monitor.py --test-send  # send a clearly-labelled test line to the channel
"""

import json
import os
import sys
import time
import subprocess

PROVIDER = "openai-codex"     # the OAuth provider we watch
TARGET = "448934333"          # main user channel (Telegram DM with the owner)
CHANNEL = "telegram"
WARN_HOURS = 24               # warn when the token expires within this window
RENAG_HOURS = 20              # re-send a still-active alert at most this often
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auth-monitor-state.json")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth-monitor.log")

def log(line):
    """Append a timestamped line so every run leaves a trace in the volume."""
    try:
        with open(LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + line + "\n")
    except Exception:
        pass

def oc(args, timeout=60):
    try:
        r = subprocess.run(["openclaw"] + args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)

def now_ms():
    return int(time.time() * 1000)

def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}

def save_state(s):
    try:
        json.dump(s, open(STATE, "w"))
    except Exception:
        pass

def read_provider():
    """Return {'status':..., 'expiresAt':...} for PROVIDER, or None if unreadable."""
    rc, out, _ = oc(["models", "status", "--json"])
    if rc != 0 or not out.strip():
        return None
    try:
        data = json.loads(out)
    except Exception:
        return None
    found = {}
    def walk(o):
        if isinstance(o, dict):
            if o.get("provider") == PROVIDER and ("expiresAt" in o or "status" in o):
                if o.get("expiresAt") is not None:
                    if "expiresAt" not in found or o["expiresAt"] < found["expiresAt"]:
                        found["expiresAt"] = o["expiresAt"]
                if o.get("status"):
                    found["status"] = o["status"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return found or None

def decide(info):
    """Return (level, hours_left). level in ok|warn|expired|unknown."""
    if info is None:
        return "unknown", None
    exp = info.get("expiresAt")
    status = info.get("status")
    hours = (exp - now_ms()) / 3600000.0 if exp is not None else None
    if (status and status != "ok") or (hours is not None and hours <= 0):
        return "expired", hours
    if hours is not None and hours <= WARN_HOURS:
        return "warn", hours
    return "ok", hours

def message_for(level, hours):
    if level == "expired":
        return ("🚨 У меня истёк доступ к модели (codex) — я временно работаю с "
                "ограничениями. Нужна повторная авторизация.")
    if level == "warn":
        h = int(hours) if hours is not None else "?"
        return ("⚠️ Мой доступ к модели (codex) истекает примерно через %s ч — "
                "нужна повторная авторизация, пока всё не отключилось." % h)
    return "✅ Доступ к модели (codex) снова в порядке."

def main(argv):
    if "--test-send" in argv:
        rc, _, err = oc(["message", "send", "--channel", CHANNEL, "--target", TARGET,
                         "--message", "🧪 Тест: монитор авторизации работает (это проверочное сообщение)."])
        print("[auth-monitor] test-send rc=%s %s" % (rc, err.strip()[:200]))
        log("test-send rc=%s" % rc)
        return 0 if rc == 0 else 1

    info = read_provider()
    level, hours = decide(info)
    dry = "--dry" in argv

    if level == "unknown":
        # Can't read status (gateway restart?). Stay silent to avoid false alarms.
        print("[auth-monitor] level=unknown (status unreadable) — no action")
        log("level=unknown (status unreadable)")
        return 0

    msg = message_for(level, hours)
    st = load_state()
    last_level, last_ts = st.get("level"), st.get("ts", 0)
    n = now_ms()

    send = False
    if level in ("warn", "expired"):
        send = (level != last_level) or (n - last_ts >= RENAG_HOURS * 3600000)
    elif level == "ok":
        send = last_level in ("warn", "expired")  # recovery notice only

    hrs = ("%.1f" % hours) if hours is not None else "?"
    if dry:
        print("[auth-monitor] DRY level=%s hours_left=%s would_send=%s" % (level, hrs, send))
        if send:
            print("  message: " + msg)
        return 0

    if send:
        rc, _, err = oc(["message", "send", "--channel", CHANNEL, "--target", TARGET, "--message", msg])
        save_state({"level": level, "ts": n, "delivered": rc == 0})
        print("[auth-monitor] level=%s hours_left=%s sent=%s %s"
              % (level, hrs, rc == 0, ("" if rc == 0 else err.strip()[:150])))
        log("level=%s hours=%s sent=%s" % (level, hrs, rc == 0))
    else:
        if level != last_level:
            st["level"] = level
            if level == "ok":
                st["ts"] = 0
            save_state(st)
        print("[auth-monitor] level=%s hours_left=%s (no send)" % (level, hrs))
        log("level=%s hours=%s (no send)" % (level, hrs))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
