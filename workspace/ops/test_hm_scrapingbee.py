#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error

API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www2.hm.com/en_eur/productpage.1321898001.html"

if not API_KEY:
    print(json.dumps({"ok": False, "error": "missing SCRAPINGBEE_API_KEY"}, ensure_ascii=False))
    sys.exit(1)

results = []
for render_js in (False, True):
    api = (
        "https://app.scrapingbee.com/api/v1?api_key=" + urllib.parse.quote(API_KEY, safe="") +
        "&url=" + urllib.parse.quote(URL, safe="") +
        ("&render_js=true&wait=6000" if render_js else "&render_js=false")
    )
    item = {"render_js": render_js}
    try:
        with urllib.request.urlopen(api, timeout=90) as resp:
            body = resp.read().decode("utf-8", "replace")
            item["status"] = resp.status
            item["title"] = re.search(r"<title>(.*?)</title>", body, re.I | re.S).group(1).strip() if re.search(r"<title>(.*?)</title>", body, re.I | re.S) else None
            item["has_access_denied"] = "access denied" in body.lower()
            item["has_hm"] = "h&amp;m" in body.lower() or "h&m" in body.lower()
            item["price_hits"] = re.findall(r'€\s*[0-9]+(?:[.,][0-9]{2})?|[0-9]+(?:[.,][0-9]{2})?\s*€', body)
            item["snippet"] = re.sub(r"\s+", " ", body)[:1200]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if hasattr(e, 'read') else ""
        item["status"] = e.code
        item["error"] = "HTTPError"
        item["has_access_denied"] = "access denied" in body.lower()
        item["snippet"] = re.sub(r"\s+", " ", body)[:1200]
    except Exception as e:
        item["error"] = repr(e)
    results.append(item)

print(json.dumps({"url": URL, "results": results}, ensure_ascii=False, indent=2))
