"""Download ~40 New York Appellate Division tort opinions (2015-2025) from CourtListener.

Usage:
    export COURTLISTENER_TOKEN=...   # never hard-code the token
    python download_cases.py
"""

import csv
import html
import os
import re
import sys
import time
from pathlib import Path

import requests

SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
OPINION_URL = "https://www.courtlistener.com/api/rest/v4/opinions/{}/"
CASES_DIR = Path("cases")
INDEX_FILE = Path("cases_index.csv")
PER_SEARCH = 8
PAUSE = 2.0  # seconds between API calls (CourtListener rate-limits bursts)

# Borough/county names rather than "New York City", which mostly matches agency names
# in case captions (e.g. "New York City Tr. Auth.") and skews results toward those defendants.
NYC = ('(Manhattan OR Brooklyn OR Bronx OR Queens OR "Staten Island" OR "Kings County" '
       'OR "New York County" OR "Queens County" OR "Richmond County")')
SEARCHES = {
    "premises": f'("slip and fall" OR "trip and fall" OR "premises liability") AND {NYC}',
    "motor_vehicle": f'("motor vehicle" OR pedestrian OR "rear-end") AND negligence AND {NYC}',
    "labor_law": f'("Labor Law § 240" OR "Labor Law § 241" OR "Labor Law 240" OR "Labor Law 241") AND {NYC}',
    "city_nycha": '("City of New York" OR "New York City Housing Authority" OR NYCHA) AND negligence AND (injured OR injuries)',
    "med_mal": f'("medical malpractice") AND {NYC}',
}


def get_token():
    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        sys.exit("Set the COURTLISTENER_TOKEN environment variable first.")
    return token


def api_get(session, url, params=None):
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                if wait > 300:
                    sys.exit(f"Rate limited by CourtListener; try again in {wait // 60} minutes. "
                             "Already-saved cases will be reused.")
                print(f"  rate limited; waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  request failed ({e}); retrying")
            time.sleep(5)
    return None


def opinion_text(op):
    """Return the best available plain text for an opinion record."""
    if op.get("plain_text", "").strip():
        return op["plain_text"]
    for field in ("html_with_citations", "html", "html_lawbox", "html_columbia", "xml_harvard"):
        raw = op.get(field) or ""
        if raw.strip():
            text = re.sub(r"<(br|p|div)[^>]*>", "\n", raw, flags=re.I)
            text = re.sub(r"<[^>]+>", "", text)
            text = html.unescape(text)
            return re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return ""


def slugify(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:60]


def main():
    session = requests.Session()
    session.headers["Authorization"] = f"Token {get_token()}"
    CASES_DIR.mkdir(exist_ok=True)

    rows = []
    seen_clusters = set()
    seen_names = set()  # catches the same decision filed under sibling clusters

    for topic, query in SEARCHES.items():
        print(f"Searching: {topic}")
        params = {
            "q": query,
            "type": "o",
            "court": "nyappdiv",
            "filed_after": "2015-01-01",
            "filed_before": "2025-12-31",
            "order_by": "score desc",
        }
        data = api_get(session, SEARCH_URL, params)
        time.sleep(PAUSE)
        found = 0
        while data and found < PER_SEARCH:
            for res in data["results"]:
                if found >= PER_SEARCH:
                    break
                key = (res["caseName"].lower(), res["dateFiled"])
                if res["cluster_id"] in seen_clusters or key in seen_names or not res.get("opinions"):
                    continue
                filename = f"{res['dateFiled']}_{slugify(res['caseName'])}_{res['cluster_id']}.txt"
                if not (CASES_DIR / filename).exists():  # reuse files from an earlier run
                    op = api_get(session, OPINION_URL.format(res["opinions"][0]["id"]))
                    time.sleep(PAUSE)
                    text = opinion_text(op) if op else ""
                    if len(text) < 500:  # skip empty or stub opinions
                        continue
                    (CASES_DIR / filename).write_text(text, encoding="utf-8")
                seen_clusters.add(res["cluster_id"])
                seen_names.add(key)
                rows.append({
                    "file": filename,
                    "case_name": res["caseName"],
                    "date": res["dateFiled"],
                    "court": res["court"],
                    "search_topic": topic,
                    "url": "https://www.courtlistener.com" + res["absolute_url"],
                })
                found += 1
                print(f"  [{found}] {res['caseName']} ({res['dateFiled']})")
            if found < PER_SEARCH and data.get("next"):
                data = api_get(session, data["next"])
                time.sleep(PAUSE)
            else:
                break

    with INDEX_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} cases to {CASES_DIR}/ and {INDEX_FILE}")


if __name__ == "__main__":
    main()
