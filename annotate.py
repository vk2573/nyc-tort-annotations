"""Annotate downloaded opinions with an LLM via the OpenRouter API.

Usage:
    export OPENROUTER_API_KEY=...   # never hard-code the key
    python annotate.py              # annotate every case not yet in results.csv
    python annotate.py --limit 5    # annotate at most 5 new cases (for testing)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"
INDEX_FILE = Path("cases_index.csv")
CASES_DIR = Path("cases")
RESULTS_FILE = Path("results.csv")
PROMPT = Path("prompt.txt").read_text(encoding="utf-8")
WAIT = 5            # seconds between requests
MAX_CHARS = 30000   # truncate very long opinions to stay within context limits

FIELDS = ["file", "case_name", "year", "tort_type", "defendant_type",
          "procedural_stage", "winner", "reason", "model"]


def get_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("Set the OPENROUTER_API_KEY environment variable first.")
    return key


def parse_json(text):
    """Pull the first JSON object out of the model's reply."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"no JSON in reply: {text[:200]!r}")
    return json.loads(match.group(0))


def annotate(key, opinion):
    r = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": PROMPT + "\n" + opinion[:MAX_CHARS]}],
            "temperature": 0,
        },
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    if "choices" not in data:
        raise ValueError(f"unexpected response: {str(data)[:200]}")
    result = parse_json(data["choices"][0]["message"]["content"] or "")
    result["model"] = data.get("model", MODEL)  # the free router reports which model answered
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="max number of new cases to annotate")
    args = parser.parse_args()
    key = get_key()

    with INDEX_FILE.open(encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    done = set()
    if RESULTS_FILE.exists():
        with RESULTS_FILE.open(encoding="utf-8") as f:
            done = {row["file"] for row in csv.DictReader(f)}

    todo = [c for c in cases if c["file"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(done)} already done, annotating {len(todo)} now")

    new_file = not RESULTS_FILE.exists()
    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        for i, case in enumerate(todo, 1):
            opinion = (CASES_DIR / case["file"]).read_text(encoding="utf-8")
            result = None
            for attempt in (1, 2):  # one retry on failure
                try:
                    result = annotate(key, opinion)
                    break
                except (requests.RequestException, ValueError) as e:
                    print(f"  attempt {attempt} failed for {case['file']}: {e}")
                    time.sleep(WAIT * 2)
            if result:
                result["file"] = case["file"]
                writer.writerow(result)
                f.flush()  # save progress so a rerun can resume
                print(f"[{i}/{len(todo)}] {result.get('case_name')}: "
                      f"{result.get('defendant_type')} / winner={result.get('winner')}")
            else:
                print(f"[{i}/{len(todo)}] skipped {case['file']} (will retry on next run)")
            time.sleep(WAIT)


if __name__ == "__main__":
    main()
