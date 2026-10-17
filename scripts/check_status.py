#!/usr/bin/env python3
"""Fieldnote register status check.

Makes ONE light GET request to each register's public endpoint and writes
status.json (state, HTTP code, response time, checked_at). When a register's
state changes, a dated entry is added to data/changelog.json.

Standard library only. MIT licence (see LICENSE).
"""
import datetime as dt
import json
import pathlib
import socket
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTERS = ROOT / "data" / "registers.json"
CHANGELOG = ROOT / "data" / "changelog.json"
STATUS = ROOT / "status.json"
TIMEOUT = 20
HISTORY_KEEP = 120  # 30 days at 4 checks/day
UA = "FieldnoteRegisterStatus/1.0 (one request per register per run; open-source status check)"
MAINTENANCE_WORDS = ("przerwa techniczna", "maintenance", "wartung", "mantenimiento", "maintenance en cours")
BOT_WALL_WORDS = ("just a moment", "cf-chl", "challenge-platform")

LABELS = {
    "up": "Up",
    "limited": "Up (rate-limited)",
    "maintenance": "Maintenance",
    "degraded": "Unexpected response",
    "down": "Down",
    "unknown": "Unknown",
}


def last_weekday(today):
    d = today
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.strftime("%Y%m%d")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(200_000)
            return r.status, r.headers.get("Content-Type", ""), body, time.monotonic() - t0, None
    except urllib.error.HTTPError as e:
        body = e.read(50_000) if hasattr(e, "read") else b""
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", body, time.monotonic() - t0, None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        return None, "", b"", time.monotonic() - t0, str(getattr(e, "reason", e))


def classify(check, code, ctype, body, err):
    text = body[:20_000].decode("utf-8", "replace").lower()
    ok = check.get("ok", [200])
    expect = check.get("expect", "json")
    if err:
        return "down", f"No response ({err[:80]})"
    if code == 429:
        return "limited", "HTTP 429: answering, but rate-limited"
    if any(w in text for w in BOT_WALL_WORDS) and code in (403, 503):
        return "unknown", f"HTTP {code}: bot protection in front of the site; cannot tell if the register is up"
    if code >= 500:
        if any(w in text for w in MAINTENANCE_WORDS):
            return "maintenance", f"HTTP {code}: maintenance notice"
        return "down", f"HTTP {code}: server error"
    if expect == "auth":
        if code in ok:
            return "up", f"HTTP {code}: endpoint answering (credentials required)"
        return "degraded", f"HTTP {code}: expected an authentication challenge"
    if code in ok:
        is_json = "json" in ctype
        if expect == "json" and not is_json:
            if any(w in text for w in MAINTENANCE_WORDS):
                return "maintenance", f"HTTP {code}: maintenance page instead of data"
            return "degraded", f"HTTP {code}: expected JSON, got {ctype.split(';')[0] or 'unknown type'}"
        if expect == "html" and any(w in text for w in MAINTENANCE_WORDS[:1]):
            return "maintenance", f"HTTP {code}: maintenance notice"
        return "up", f"HTTP {code}"
    return "degraded", f"HTTP {code}: unexpected status"


def vies_detail(body):
    try:
        d = json.loads(body)
        down = [c["countryCode"] for c in d.get("countries", []) if c.get("availability") != "Available"]
        return {"member_states_unavailable": down}
    except Exception:
        return {}


def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    regs = json.loads(REGISTERS.read_text())["registers"]
    prev = json.loads(STATUS.read_text()) if STATUS.exists() else {"registers": {}}
    out = {"checked_at": now.isoformat().replace("+00:00", "Z"), "registers": {}}
    changes = []
    for r in regs:
        chk = r["check"]
        url = chk["url"].replace("{last_weekday}", last_weekday(now.date()))
        code, ctype, body, secs, err = fetch(url)
        state, detail = classify(chk, code, ctype, body, err)
        p = prev["registers"].get(r["slug"], {})
        hist = (p.get("history") or [])[-(HISTORY_KEEP - 1):] + [[out["checked_at"], state]]
        ups = sum(1 for _, s in hist if s in ("up", "limited"))
        entry = {
            "state": state,
            "label": LABELS[state],
            "detail": detail,
            "http_status": code,
            "response_ms": round(secs * 1000),
            "checked_at": out["checked_at"],
            "endpoint": url,
            "uptime_pct": round(100 * ups / len(hist), 1),
            "checks": len(hist),
            "history": hist,
        }
        if chk.get("vies") and code == 200:
            entry.update(vies_detail(body))
        out["registers"][r["slug"]] = entry
        if p.get("state") and p["state"] != state:
            changes.append({"date": now.date().isoformat(), "type": "status", "code": r["code"],
                            "text": f"{r['register'].split(' – ')[0]}: status changed from {LABELS.get(p['state'], p['state'])} to {LABELS[state]} ({detail})."})
        print(f"{r['code']:3} {r['slug']:32} {state:12} {code!s:5} {entry['response_ms']:6} ms  {detail}")
        time.sleep(0.5)
    STATUS.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    if changes:
        log = json.loads(CHANGELOG.read_text())
        log["entries"] = changes + log["entries"]
        CHANGELOG.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
