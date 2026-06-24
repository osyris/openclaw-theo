#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl-cffi>=0.7", "playwright>=1.45"]
# ///
"""
price_tracker — детерминированный трекер цен (agent-first CLI).

Этот инструмент рассчитан на вызов агентом по ПОЛНОМУ ПУТИ. Запусти
`price_tracker.py help`, чтобы загрузить полный контракт.

Одна точка входа на весь функционал отслеживания цен. Вся «грязь» транспорта
(Chrome-impersonating curl, social-UA, локальный headless chromium для JS-сайтов)
и извлечения цены спрятана внутри. Цены извлекаются ДЕТЕРМИНИРОВАННО (Shopify JSON
/ JSON-LD / OpenGraph-meta / микроданные) — модель НИКОГДА не выбирает цену.
Конфиг правится ТОЛЬКО этими командами — руками JSON не трогать.

Команды:
  help                         Напечатать этот контракт.
  doctor [--deep]              Проверка готовности: curl_cffi, конфиг, openclaw,
                               chromium (рендер JS-сайтов). --deep также проверяет,
                               что импортируется playwright.
  check [--json] [--send] [--only ID] [--debug]
                               Получить цены по всем включённым товарам, обновить
                               состояние и напечатать сводку.
                               default : текст (🛍) — это и пересылается владельцу
                               --json  : структура {generated_at,text,warnings,items,summary}
                               --send  : дополнительно отправить текст владельцу
                                         напрямую (openclaw message send → delivery.target)
  add <url> [--title "Имя"] [--id ID]
                               Добавить товар. Сам подбирает рабочий способ фетча
                               и фиксирует базовую цену.
  remove <id>                  Убрать товар.
  enable <id> | disable <id>   Включить/приостановить отслеживание товара.
  set <id> <price>             Вручную записать цену (если страница не поддаётся).
  list                         Список отслеживаемых товаров.
  methods                      Какой метод фетча сейчас рабочий по каждому товару.
  schedule [status|install|off]
                               Управление плановым запуском (08:00 и 20:00 Tallinn).
                               status (default): показать текущую джобу.
                               install: создать/пересоздать джобу (агент-триггер
                                        запускает `check --send`).
                               off: удалить джобу.

I/O:
  - stdout: результат команды (для check без --json — готовая сводка 🛍).
  - stderr: ошибки в виде {"error":{"code","message","hint"}}.
  - Состояние: price-tracker.json рядом со скриптом (атомарная запись, единственный писатель — скрипт).
  - Доставка: delivery.target в конфиге (telegram chat id владельца).
  - JS-сайты (Oysho/Zara и пр.) рендерятся локальным chromium (/usr/bin/chromium) —
    внешних токенов и оплаты не нужно. ScrapingBee отключён (закомментирован в
    каскаде), код транспорта оставлен в файле на случай возврата.

Коды выхода:
  0 ok · 3 не найдено (id) · 5 транспорт/сеть/CLI · 6 неверный ввод.

Заметки:
  - При `add` скрипт сразу пробует вытащить цену и пишет владельцу, получилось или
    нет — этот текст передавай владельцу как есть.
  - Зависимости (curl_cffi, playwright) подтянутся сами через uv (или `python3`
    сам переподхватит uv).
"""

import os
import sys
import re
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# --- self-bootstrap: ensure deps via uv -------------------------------------
try:
    from curl_cffi import requests as cffi  # type: ignore
    HAVE_CFFI = True
except Exception:
    HAVE_CFFI = False
    cffi = None
    if os.environ.get("PT_REEXEC") != "1" and shutil.which("uv"):
        os.environ["PT_REEXEC"] = "1"
        os.execvp("uv", ["uv", "run", "--script",
                         os.path.abspath(__file__)] + sys.argv[1:])

# exit codes (capabilities taxonomy)
OK, E_AUTH, E_NOTFOUND, E_POLICY, E_NET, E_INPUT = 0, 2, 3, 4, 5, 6

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.abspath(__file__)
CONFIG_PATH = os.path.join(HERE, "price-tracker.json")
DEFAULT_SB_ENV = "/data/workspace/skills/scrapingbee/.env"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SOCIAL_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
# In-container Chromium (Debian package, baked into the image → restored on every
# redeploy). Override with PT_CHROMIUM if the path ever changes.
CHROMIUM_PATH = os.environ.get("PT_CHROMIUM", "/usr/bin/chromium")
# A normal desktop-Chrome UA. The default headless UA ("HeadlessChrome") + the
# webdriver flag get 403'd by Akamai bot-protection (Oysho/Zara/Inditex); a clean
# Chrome fingerprint passes from a plain datacenter IP — no proxy/ScrapingBee.
CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")

JOB_NAME = "Цены 08:00 и 20:00"
SCHED_EXPR = "0 8,20 * * *"
SCHED_TZ = "Europe/Tallinn"

# Runtime health of the ScrapingBee tier, surfaced in `check` output.
SB_STATUS = {"tried": False, "ok": False, "reason": None}

def fail(code, token, message, hint=None):
    e = {"code": token, "message": message}
    if hint:
        e["hint"] = hint
    print(json.dumps({"error": e}, ensure_ascii=False), file=sys.stderr)
    return code

# --------------------------------------------------------------- config I/O

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)

def get_sb_key(cfg):
    path = cfg.get("scrapingbee_env", DEFAULT_SB_ENV)
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("SCRAPINGBEE_API_KEY="):
                    return line.strip().split("=", 1)[1] or None
    except OSError:
        pass
    return os.environ.get("SCRAPINGBEE_API_KEY")

# --------------------------------------------------------------- transports

def t_cffi(url, timeout=40):
    if not HAVE_CFFI:
        return None
    try:
        r = cffi.get(url, impersonate="chrome", timeout=timeout)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        pass
    return None

def t_social(url, timeout=30):
    if not HAVE_CFFI:
        return None
    try:
        r = cffi.get(url, impersonate="chrome", timeout=timeout,
                     headers={"User-Agent": SOCIAL_UA})
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        pass
    return None

def t_flaresolverr(url, fs_url, timeout=70):
    if not (fs_url and HAVE_CFFI):
        return None
    try:
        r = cffi.post(fs_url.rstrip("/") + "/v1", timeout=timeout,
                      json={"cmd": "request.get", "url": url,
                            "maxTimeout": (timeout - 5) * 1000})
        if r.status_code == 200:
            return (r.json().get("solution") or {}).get("response")
    except Exception:
        pass
    return None

def t_scrapingbee(url, key, render_js=False, timeout=75):
    if not key:
        return None
    api = ("https://app.scrapingbee.com/api/v1?api_key=" + key +
           "&url=" + urllib.parse.quote(url, safe="") +
           ("&render_js=true&wait=6000" if render_js else "&render_js=false"))
    SB_STATUS["tried"] = True
    status, body = None, None
    try:
        if HAVE_CFFI:
            r = cffi.get(api, timeout=timeout)
            status, body = r.status_code, r.text
        else:
            try:
                with urllib.request.urlopen(api, timeout=timeout) as resp:
                    status, body = resp.status, resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as he:
                status = he.code
                try:
                    body = he.read().decode("utf-8", "replace")
                except Exception:
                    body = ""
    except Exception:
        SB_STATUS["reason"] = SB_STATUS["reason"] or "network"
        return None
    if status == 200 and body:
        SB_STATUS["ok"] = True
        return body
    low = (body or "").lower()
    if status in (401, 403) and "limit" in low:
        SB_STATUS["reason"] = "exhausted"
    elif status in (401, 403):
        SB_STATUS["reason"] = "auth"
    else:
        SB_STATUS["reason"] = "http_%s" % status
    return None

# JS predicate: true once a usable price is present in the rendered DOM. Mirrors
# the python extractors (JSON-LD Product offer, then OG/product meta) so we wait
# for the *price*, not just for the network to settle — Inditex SPAs (Oysho/Zara)
# inject the JSON-LD offer asynchronously after first paint.
PRICE_READY_JS = r"""
() => {
  const blocks = document.querySelectorAll('script[type="application/ld+json"]');
  for (const b of blocks) {
    let data; try { data = JSON.parse(b.textContent); } catch (e) { continue; }
    const stack = Array.isArray(data) ? data.slice() : [data];
    while (stack.length) {
      const n = stack.pop();
      if (!n || typeof n !== 'object') continue;
      if (Array.isArray(n)) { stack.push(...n); continue; }
      if (Array.isArray(n['@graph'])) stack.push(...n['@graph']);
      const t = n['@type'];
      const types = Array.isArray(t) ? t : [t];
      if (!types.includes('Product')) continue;
      let offers = n.offers;
      if (!offers) continue;
      offers = Array.isArray(offers) ? offers : [offers];
      for (const o of offers) {
        if (!o || typeof o !== 'object') continue;
        const sp = o.priceSpecification;
        const spPrice = sp && (Array.isArray(sp) ? sp[0] : sp) && (Array.isArray(sp) ? sp[0] : sp).price;
        if (o.price || o.lowPrice || o.highPrice || spPrice) return true;
      }
    }
  }
  const m = document.querySelector('meta[property="product:price:amount"], meta[property="og:price:amount"]');
  return !!(m && m.getAttribute('content'));
}
"""

def t_chromium(url, timeout=45):
    """Render via the in-container headless chromium (for JS-rendered sites).

    Free, no token, no external service. Presents a clean desktop-Chrome
    fingerprint (real UA, no automation flag, webdriver hidden) so Akamai-style
    bot protection (Oysho/Zara/Inditex) returns 200 instead of 403 — this is what
    ScrapingBee's proxy network used to buy us. Waits until a price actually
    appears in the DOM (PRICE_READY_JS) so client-rendered prices are captured
    deterministically; if the wait times out it still returns whatever rendered,
    so the regular extractors get a chance. Returns rendered HTML or None.
    """
    os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")
    try:
        from playwright.sync_api import sync_playwright  # lazy: only JS-sites pay for it
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROMIUM_PATH, headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-blink-features=AutomationControlled"])
            try:
                ctx = browser.new_context(
                    user_agent=CHROME_UA, locale="et-EE",
                    timezone_id="Europe/Tallinn",
                    viewport={"width": 1366, "height": 900})
                ctx.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                try:
                    page.wait_for_function(PRICE_READY_JS, timeout=15000)
                except Exception:
                    pass  # let the extractors try whatever did render
                return page.content()
            finally:
                browser.close()
    except Exception:
        return None

def transports(cfg):
    key = get_sb_key(cfg)
    fs = cfg.get("flaresolverr_url") or os.environ.get("FLARESOLVERR_URL")
    out = [("cffi", lambda u: t_cffi(u)), ("social", lambda u: t_social(u))]
    if fs:
        out.append(("flaresolverr", lambda u: t_flaresolverr(u, fs)))
    # JS-сайты (Oysho/Zara/Inditex SPA и пр.): локальный headless chromium —
    # бесплатно, без токена, заменяет render-тир ScrapingBee.
    out.append(("chromium", lambda u: t_chromium(u)))
    # --- ScrapingBee: ОТКЛЮЧЁН (закомментирован в каскаде) --------------------
    # Раньше JS-сайты добивались через ScrapingBee render_js. Теперь это делает
    # локальный chromium. Транспорт t_scrapingbee оставлен в файле; чтобы вернуть
    # SB — раскомментируй две строки ниже (нужен SCRAPINGBEE_API_KEY в .env/env):
    # if key:
    #     out.append(("sb", lambda u: t_scrapingbee(u, key, False)))
    #     out.append(("sbjs", lambda u: t_scrapingbee(u, key, True)))
    out.append(("plain", lambda u: t_plain(u)))
    return out

def t_plain(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "et,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", "replace")
    except Exception:
        pass
    return None

# --------------------------------------------------------------- price parse

def parse_price(raw):
    if raw is None:
        return None
    s = re.sub(r"[^0-9.,]", "", str(raw))
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    try:
        v = float(s)
        return round(v, 2) if v > 0 else None
    except ValueError:
        return None

# --------------------------------------------------------------- extractors

def is_shopify_like(url):
    return "/products/" in urllib.parse.urlsplit(url).path

def shopify_json_url(url):
    p = urllib.parse.urlsplit(url)
    path = p.path if p.path.endswith(".json") else p.path.rstrip("/") + ".json"
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, "", ""))

def extract_shopify_json(body, url):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    prod = data.get("product") if isinstance(data, dict) else None
    if not isinstance(prod, dict):
        return None
    variants = prod.get("variants") or []
    want = (urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("variant") or [None])[0]
    chosen = None
    for v in variants:
        if want and str(v.get("id")) == str(want):
            chosen = v
            break
    if chosen is None and variants:
        chosen = variants[0]
    if chosen and chosen.get("price") is not None:
        return parse_price(chosen["price"]), "EUR"
    return None

def _walk_jsonld(blocks):
    for b in blocks:
        try:
            obj = json.loads(b)
        except ValueError:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                g = cur.get("@graph")
                if isinstance(g, list):
                    stack.extend(g)
                yield cur
            elif isinstance(cur, list):
                stack.extend(cur)

def extract_jsonld(body):
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        body, re.S | re.I)
    for node in _walk_jsonld(blocks):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if "Product" not in types:
            continue
        offers = node.get("offers")
        cands = offers if isinstance(offers, list) else [offers] if offers else []
        for off in cands:
            if not isinstance(off, dict):
                continue
            cur = off.get("priceCurrency") or "EUR"
            for k in ("price", "lowPrice", "highPrice"):
                p = parse_price(off.get(k)) if off.get(k) is not None else None
                if p:
                    return p, cur
            spec = off.get("priceSpecification")
            for sp in (spec if isinstance(spec, list) else [spec] if spec else []):
                if isinstance(sp, dict) and sp.get("price") is not None:
                    p = parse_price(sp["price"])
                    if p:
                        return p, sp.get("priceCurrency") or cur
    return None

def _meta(body, attr, name):
    for pat in (r'<meta[^>]*' + attr + r'=["\']' + re.escape(name) +
                r'["\'][^>]*content=["\']([^"\']+)["\']',
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*' + attr +
                r'=["\']' + re.escape(name) + r'["\']'):
        m = re.search(pat, body, re.I)
        if m:
            return m.group(1)
    return None

def extract_meta(body):
    cur = (_meta(body, "property", "product:price:currency")
           or _meta(body, "property", "og:price:currency") or "EUR")
    for attr, name in (("property", "product:price:amount"),
                       ("property", "og:price:amount"),
                       ("itemprop", "price")):
        p = parse_price(_meta(body, attr, name))
        if p:
            return p, cur
    return None

def extract_microdata(body):
    for pat in (r'itemprop=["\']price["\'][^>]*content=["\']([^"\']+)["\']',
                r'content=["\']([^"\']+)["\'][^>]*itemprop=["\']price["\']'):
        m = re.search(pat, body, re.I)
        if m:
            p = parse_price(m.group(1))
            if p:
                return p, "EUR"
    return None

def extract_site_visible_price(body, url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text)

    if "shop.mango.com" in host:
        # Mango sale pages often expose the stale/original price in meta/JSON-LD,
        # while the real discounted value appears in rendered copy as
        # “Current price [€ 59,99]”. Prefer the visible current price.
        m = re.search(r"Current price\s*\[?\s*€\s*([0-9.,]+)", text, re.I)
        if m:
            p = parse_price(m.group(1))
            if p:
                return p, "EUR"

    if "massimodutti.com" in host:
        # Massimo Dutti sale pages render the live value like “-20% 200 €”.
        m = re.search(r"-\s*\d+%\s*([0-9.,]+)\s*€", text, re.I)
        if m:
            p = parse_price(m.group(1))
            if p:
                return p, "EUR"
        # Fallback for non-sale pages: first visible euro price in the product block.
        m = re.search(r"([0-9.,]+)\s*€", text, re.I)
        if m:
            p = parse_price(m.group(1))
            if p:
                return p, "EUR"
    return None

def extract_price(body, url):
    if not body:
        return None
    s = body.lstrip()
    if s[:1] in "{[" and '"product"' in body[:2000]:
        r = extract_shopify_json(body, url)
        if r:
            return r
    for fn in (extract_site_visible_price, extract_jsonld, extract_meta, extract_microdata):
        r = fn(body, url) if fn is extract_site_visible_price else fn(body)
        if r:
            return r
    return None

def resolve(item, cfg):
    """Return (price, currency, method) or None. Remembers the working method."""
    url = item["url"]
    methods = transports(cfg)
    pref = item.get("method")
    methods.sort(key=lambda m: 0 if m[0] == pref else 1)
    for name, fetch in methods:
        body = fetch(url)
        r = extract_price(body, url) if body else None
        if not r and is_shopify_like(url):
            jb = fetch(shopify_json_url(url))
            if jb:
                r = extract_shopify_json(jb, url)
        if r:
            return r[0], r[1], name
    return None

# --------------------------------------------------------------- formatting

def fmt_money(p, cur="EUR"):
    if p is None:
        return "—"
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur, "")
    s = ("%.2f" % p).rstrip("0").rstrip(".")
    return (s + " " + sym).strip() if sym else (s + " " + (cur or "")).strip()

def now_tallinn():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Tallinn"))
    except Exception:
        return datetime.now()

def classify(price, prev):
    if price is None:
        return "fail"
    if prev is None:
        return "new"
    if price > prev + 0.005:
        return "up"
    if price < prev - 0.005:
        return "down"
    return "same"

def build_text(rows):
    # Title is rendered as a Markdown link; OpenClaw converts [label](url) to a
    # clickable Telegram link (HTML parse mode). No marker for unchanged prices;
    # only ▲/▼ when the price actually moved.
    lines = ["\U0001F6CD️ Цены — " + now_tallinn().strftime("%d.%m %H:%M")]
    marks = {"up": " ▲", "down": " ▼", "same": "", "new": "", "fail": ""}
    for r in rows:
        name = ("[%s](%s)" % (r["title"], r["url"])) if r.get("url") else r["title"]
        if r["price"] is None:
            lines.append("• " + name + " — не удалось получить цену")
            continue
        line = "• " + name + " — " + fmt_money(r["price"], r["currency"]) + marks[r["change"]]
        if r["change"] in ("up", "down") and r["prev"] is not None:
            line += " (было " + fmt_money(r["prev"], r["currency"]) + ")"
        lines.append(line)
    return "\n".join(lines)

# --------------------------------------------------------------- openclaw glue

def oc(args, timeout=140):
    """Run an `openclaw` CLI command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(["openclaw"] + args, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)

def send_telegram(cfg, text):
    d = cfg.get("delivery", {})
    target = d.get("target")
    if not target:
        return fail(E_INPUT, "no_delivery_target", "delivery.target не задан в конфиге")
    rc, out, err = oc(["message", "send", "--channel", d.get("channel", "telegram"),
                       "--target", str(target), "--message", text], timeout=120)
    if rc != 0:
        return fail(E_NET, "delivery_failed", (err or out).strip()[:300])
    return OK

# --------------------------------------------------------------- commands

def cmd_check(args):
    cfg = load_config()
    as_json = "--json" in args
    do_send = "--send" in args
    only = args[args.index("--only") + 1] if "--only" in args else None
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in cfg.get("items", []):
        if not item.get("enabled", True) or (only and item.get("id") != only):
            continue
        prev = item.get("last_price")
        res = resolve(item, cfg)
        price = currency = method = None
        if res:
            price, currency, method = res
            if item.get("baseline_price") is None:
                item["baseline_price"] = price
            item["last_price"] = price
            item["currency"] = currency
            item["method"] = method
            hist = item.setdefault("history", [])
            hist.append({"t": now_iso, "price": price})
            del hist[:-60]
        item["last_checked"] = now_iso
        item["last_status"] = "ok" if price is not None else "failed"
        rows.append({"id": item["id"], "title": item.get("title", item["id"]),
                     "url": item["url"], "price": price,
                     "currency": currency or item.get("currency", "EUR"),
                     "prev": prev, "baseline": item.get("baseline_price"),
                     "change": classify(price, prev), "method": method})
    save_config(cfg)
    warnings = []
    if SB_STATUS["tried"] and not SB_STATUS["ok"]:
        reason = SB_STATUS["reason"]
        if reason == "exhausted":
            warnings.append("⚠️ ScrapingBee: исчерпан месячный лимит — "
                            "пришлите свежий токен, иначе часть цен не получить.")
        elif reason == "auth":
            warnings.append("⚠️ ScrapingBee: токен не принят — "
                            "пришлите свежий токен, иначе часть цен не получить.")
        else:
            warnings.append("⚠️ ScrapingBee недоступен (%s) — часть цен не получить." % reason)
    body_text = build_text(rows)
    text = ("\n".join(warnings) + "\n\n" + body_text) if warnings else body_text
    if as_json:
        print(json.dumps({"generated_at": now_iso, "timezone": "Europe/Tallinn",
                          "text": text, "warnings": warnings, "sb_status": SB_STATUS,
                          "items": rows,
                          "summary": {"ok": sum(1 for r in rows if r["price"] is not None),
                                      "failed": sum(1 for r in rows if r["price"] is None)}},
                         ensure_ascii=False, indent=2))
    else:
        print(text)
        if "--debug" in args:
            for r in rows:
                print("   [%s] %s -> %s" % (r["method"] or "FAIL", r["id"], r["price"]),
                      file=sys.stderr)
    if do_send:
        return send_telegram(cfg, text)
    return OK

def slugify(s):
    return (re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "item")

def cmd_add(args):
    if not args or args[0].startswith("--"):
        return fail(E_INPUT, "usage", 'add <url> [--title "Имя"] [--id ID]')
    url = args[0]
    if not re.match(r"^https?://", url):
        return fail(E_INPUT, "bad_url", "URL должен начинаться с http(s)://")
    title = args[args.index("--title") + 1] if "--title" in args else None
    iid = args[args.index("--id") + 1] if "--id" in args else None
    cfg = load_config()
    existing = {i["id"] for i in cfg.get("items", [])}
    if not iid:
        seed = urllib.parse.urlsplit(url).path.rstrip("/").split("/")[-1] \
            or urllib.parse.urlsplit(url).netloc
        iid = slugify(seed)
        base, n = iid, 2
        while iid in existing:
            iid = base + "-" + str(n); n += 1
    elif iid in existing:
        return fail(E_INPUT, "duplicate_id", "id уже существует: " + iid)
    item = {"id": iid, "url": url, "title": title or iid, "currency": "EUR",
            "baseline_price": None, "last_price": None, "last_checked": None,
            "method": None, "enabled": True}
    res = resolve(item, cfg)
    item["last_checked"] = datetime.now(timezone.utc).isoformat()
    if res:
        item["baseline_price"] = item["last_price"] = res[0]
        item["currency"] = res[1]
        item["method"] = res[2]
        item["last_status"] = "ok"
    else:
        item["last_status"] = "failed"
    cfg.setdefault("items", []).append(item)
    save_config(cfg)
    name = title or iid
    if res:
        print("✅ Готово, добавил в трекер: %s — %s.\n"
              "Буду проверять цену дважды в день.\n%s"
              % (name, fmt_money(res[0], res[1]), url))
    else:
        print("⚠️ Не смог сразу вытащить цену со страницы «%s» — возможно, она "
              "временно недоступна или нестандартная.\n"
              "Добавил в трекер и проверю ещё раз при ближайшем обходе. Если цена так и "
              "не подхватится — пришли её, поставлю вручную (id: %s).\n%s"
              % (name, iid, url))
    return OK

def cmd_set(args):
    if len(args) < 2:
        return fail(E_INPUT, "usage", "set <id> <price>")
    iid, price = args[0], parse_price(args[1])
    if price is None:
        return fail(E_INPUT, "bad_price", "не похоже на цену: " + args[1])
    cfg = load_config()
    now_iso = datetime.now(timezone.utc).isoformat()
    for i in cfg.get("items", []):
        if i.get("id") == iid:
            if i.get("baseline_price") is None:
                i["baseline_price"] = price
            i["last_price"] = price
            i["last_checked"] = now_iso
            i["method"] = "manual"
            i["last_status"] = "ok"
            hist = i.setdefault("history", [])
            hist.append({"t": now_iso, "price": price}); del hist[:-60]
            save_config(cfg)
            print("set %s -> %s" % (iid, fmt_money(price, i.get("currency", "EUR"))))
            return OK
    return fail(E_NOTFOUND, "not_found", "нет товара с id: " + iid)

def cmd_list(args):
    cfg = load_config()
    items = cfg.get("items", [])
    if not items:
        print("(нет отслеживаемых товаров)"); return OK
    for i in items:
        print("%-3s %-26s %-10s %s" % ("on " if i.get("enabled", True) else "off",
              i["id"], fmt_money(i.get("last_price"), i.get("currency", "EUR")), i["url"]))
    return OK

def cmd_methods(args):
    cfg = load_config()
    for i in cfg.get("items", []):
        print("%-26s %-12s %s" % (i["id"], i.get("method") or "-", i.get("last_status") or "-"))
    return OK

def cmd_remove(args):
    if not args:
        return fail(E_INPUT, "usage", "remove <id>")
    cfg = load_config()
    before = len(cfg.get("items", []))
    cfg["items"] = [i for i in cfg.get("items", []) if i.get("id") != args[0]]
    if len(cfg["items"]) == before:
        return fail(E_NOTFOUND, "not_found", "нет товара с id: " + args[0])
    save_config(cfg)
    print("removed " + args[0])
    return OK

def cmd_toggle(args, value):
    if not args:
        return fail(E_INPUT, "usage", "enable/disable <id>")
    cfg = load_config()
    hit = False
    for i in cfg.get("items", []):
        if i.get("id") == args[0]:
            i["enabled"] = value; hit = True
    if not hit:
        return fail(E_NOTFOUND, "not_found", "нет товара с id: " + args[0])
    save_config(cfg)
    print(("enabled " if value else "disabled ") + args[0])
    return OK

# --------------------------------------------------------------- doctor

def cmd_doctor(args):
    deep = "--deep" in args
    lines, ok = [], True
    lines.append("curl_cffi: " + ("ok" if HAVE_CFFI else "ОТСУТСТВУЕТ (uv bootstrap не сработал)"))
    if not HAVE_CFFI:
        ok = False
    try:
        cfg = load_config()
        n = len([i for i in cfg.get("items", []) if i.get("enabled", True)])
        lines.append("config: ok (%d активных товаров)" % n)
    except Exception as e:
        lines.append("config: ОШИБКА — " + str(e))
        print("\n".join(lines))
        return fail(E_NET, "config_unreadable", str(e))
    has_oc = bool(shutil.which("openclaw"))
    lines.append("openclaw CLI: " + ("ok" if has_oc else "ОТСУТСТВУЕТ"))
    if not has_oc:
        ok = False
    chromium_ok = os.path.exists(CHROMIUM_PATH)
    lines.append("chromium: " + (("ok (%s)" % CHROMIUM_PATH) if chromium_ok
                 else "ОТСУТСТВУЕТ по %s — рендер JS-сайтов не сработает" % CHROMIUM_PATH))
    if not chromium_ok:
        ok = False
    if deep:
        try:
            import playwright  # noqa: F401
            lines.append("playwright: ok (импортируется)")
        except Exception as e:
            lines.append("playwright: ОТСУТСТВУЕТ — " + str(e).splitlines()[0][:120])
            ok = False
    # ScrapingBee отключён в каскаде — справочно, на код выхода не влияет.
    key = get_sb_key(cfg)
    lines.append("ScrapingBee: отключён в каскаде" +
                 (" (токен задан, но не используется)" if key else " (токен не нужен)"))
    print("\n".join(lines))
    return OK if ok else E_NET

# --------------------------------------------------------------- schedule

def _cron_jobs():
    rc, out, _ = oc(["cron", "list", "--json"], timeout=60)
    if rc != 0:
        return None
    try:
        d = json.loads(out)
    except ValueError:
        return None
    return d if isinstance(d, list) else d.get("jobs", [])

def cmd_schedule(args):
    sub = args[0] if args else "status"
    if sub == "status":
        jobs = _cron_jobs()
        if jobs is None:
            return fail(E_NET, "cron_unreachable", "не удалось получить список cron")
        mine = [j for j in jobs if j.get("name") == JOB_NAME]
        if not mine:
            print("расписание: НЕ установлено (запусти `schedule install`)")
            return OK
        for j in mine:
            sch = j.get("schedule", {})
            print("расписание: %s | %s %s | enabled=%s | next=%s" % (
                j.get("name"), sch.get("expr"), sch.get("tz", ""),
                j.get("enabled"), j.get("state", {}).get("nextRunAtMs")))
        return OK
    if sub == "install":
        jobs = _cron_jobs() or []
        for j in jobs:
            if j.get("name") == JOB_NAME:
                oc(["cron", "remove", j["id"]], timeout=60)
        msg = ("Выполни ровно эту команду и больше ничего, ответ не пересылай: "
               "python3 %s check --send" % SCRIPT_PATH)
        rc, out, err = oc(["cron", "add", "--name", JOB_NAME, "--cron", SCHED_EXPR,
                           "--tz", SCHED_TZ, "--session", "isolated", "--no-deliver",
                           "--exact", "--timeout-seconds", "180", "--message", msg],
                          timeout=60)
        if rc != 0:
            return fail(E_NET, "cron_add_failed", (err or out).strip()[:300])
        print("расписание установлено: %s в %s (%s).\n"
              "Агент-триггер запускает `check --send`; скрипт сам шлёт сводку владельцу."
              % (JOB_NAME, SCHED_EXPR, SCHED_TZ))
        return OK
    if sub in ("off", "remove", "uninstall"):
        jobs = _cron_jobs()
        if jobs is None:
            return fail(E_NET, "cron_unreachable", "не удалось получить список cron")
        removed = 0
        for j in jobs:
            if j.get("name") == JOB_NAME:
                oc(["cron", "remove", j["id"]], timeout=60); removed += 1
        print("расписание удалено (%d джоб)" % removed if removed else "расписание не было установлено")
        return OK
    return fail(E_INPUT, "usage", "schedule [status|install|off]")

# --------------------------------------------------------------- dispatch

def cmd_help(args):
    print(__doc__.strip())
    return OK

def main(argv):
    if not argv:
        return cmd_help(argv)
    cmd, rest = argv[0], argv[1:]
    table = {"help": cmd_help, "doctor": cmd_doctor, "check": cmd_check, "add": cmd_add,
             "set": cmd_set, "list": cmd_list, "methods": cmd_methods,
             "remove": cmd_remove, "schedule": cmd_schedule,
             "enable": lambda a: cmd_toggle(a, True),
             "disable": lambda a: cmd_toggle(a, False)}
    if cmd in ("-h", "--help"):
        return cmd_help(rest)
    if cmd in table:
        return table[cmd](rest)
    print(__doc__.strip())
    return fail(E_INPUT, "unknown_command", "неизвестная команда: " + cmd)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
