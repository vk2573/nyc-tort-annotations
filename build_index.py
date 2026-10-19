"""Build cases_index.csv from the opinion .txt files in cases/.

Use this when cases were added by hand (copied from courtlistener.com) instead of
through download_cases.py. Case name, date, and court are read from the opinion
header; duplicates are skipped by their NY Slip Op citation.

Usage:
    python build_index.py
"""

import csv
import re
from datetime import datetime
from pathlib import Path

CASES_DIR = Path("cases")
INDEX_FILE = Path("cases_index.csv")


def parse_header(text):
    first = text.strip().splitlines()[0]
    m = re.match(r"(.+?)\s*\((\d{4} NY Slip Op \d+)\)", first)
    case_name, citation = (m.group(1), m.group(2)) if m else (first.strip(), "")
    d = re.search(r"Decided on ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    date = datetime.strptime(d.group(1), "%B %d, %Y").date().isoformat() if d else ""
    c = re.search(r"Appellate Division, (First|Second|Third|Fourth) (?:Judicial )?Department", text)
    court = f"Appellate Division, {c.group(1)} Department" if c else ""
    return case_name, citation, date, court


def main():
    rows, seen = [], set()
    for path in sorted(CASES_DIR.glob("*.txt")):
        case_name, citation, date, court = parse_header(path.read_text(encoding="utf-8"))
        key = citation or case_name.lower()
        if key in seen:
            print(f"Skipping duplicate: {path.name}")
            continue
        seen.add(key)
        rows.append({"file": path.name, "case_name": case_name, "date": date,
                     "court": court, "citation": citation})

    with INDEX_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Indexed {len(rows)} cases in {INDEX_FILE}")


if __name__ == "__main__":
    main()
