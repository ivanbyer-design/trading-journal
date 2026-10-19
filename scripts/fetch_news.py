"""Fetch ForexFactory's weekly economic calendar and store it per week.

Usage: python3 fetch_news.py <output_dir>
Writes <output_dir>/news/<sunday>.json and keeps <output_dir>/news/index.json current.
The feed only covers the current week, so running this on a schedule builds an archive.
"""
import json, os, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def week_key(iso):
    d = datetime.fromisoformat(iso).date()  # local (ET) calendar date from the feed's offset
    return (d - timedelta(days=(d.weekday() + 1) % 7)).isoformat()


def main(out):
    try:
        req = urllib.request.Request(FEED, headers={"User-Agent": "EdgeFlow news sync (GitHub Actions)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            feed = json.load(r)
        if not isinstance(feed, list) or not feed:
            raise ValueError("unexpected feed format")
    except Exception as e:  # don't fail the workflow on a flaky upstream
        print(f"fetch failed: {e}")
        return 0

    events = [{"t": e.get("title", ""), "cur": e.get("country", ""), "imp": e.get("impact", ""),
               "date": e.get("date", ""), "fc": e.get("forecast", ""), "prev": e.get("previous", "")}
              for e in feed if e.get("date")]
    week = Counter(week_key(e["date"]) for e in events).most_common(1)[0][0]

    news = os.path.join(out, "news")
    os.makedirs(news, exist_ok=True)
    path = os.path.join(news, f"{week}.json")
    old = []
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f).get("events") or []
    # Keep a stored event the feed no longer lists only if its day (ET) was already over:
    # it happened. Removed before its day ended means cancelled/rescheduled, so drop it.
    today_et = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    key = lambda e: (e["t"], e["cur"], e["date"])
    seen = {key(e) for e in events}
    events = sorted(events + [e for e in old if key(e) not in seen and e["date"][:10] < today_et], key=lambda e: e["date"])
    if old != events:
        with open(path, "w") as f:
            json.dump({"week": week, "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "events": events}, f, separators=(",", ":"))
        print(f"wrote {path} ({len(events)} events)")
    else:
        print(f"{path} unchanged")

    weeks = sorted(f[:-5] for f in os.listdir(news) if f.endswith(".json") and f != "index.json")
    with open(os.path.join(news, "index.json"), "w") as f:
        json.dump({"weeks": weeks}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
