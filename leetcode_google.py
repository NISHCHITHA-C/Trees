"""
Extract LeetCode questions asked in Google interviews (last 30 days).
Requires a valid LeetCode session cookie (LEETCODE_SESSION).

Usage:
    python leetcode_google.py --session <your_session_cookie>
    python leetcode_google.py --session <cookie> --output results.csv
"""

import argparse
import csv
import json
import sys
import time
import requests

GRAPHQL_URL = "https://leetcode.com/graphql"
FAVORITE_SLUG = "google-thirty-days"
PAGE_SIZE = 50

QUERY = """
query favoriteQuestionList($favoriteSlug: String!, $skip: Int!, $limit: Int!) {
  favoriteQuestionList(favoriteSlug: $favoriteSlug, skip: $skip, limit: $limit) {
    hasMore
    totalLength
    questions {
      questionFrontendId
      title
      titleSlug
      difficulty
      paidOnly
      status
      acRate
      topicTags {
        name
        slug
      }
      companyTagStats
    }
  }
}
"""


def make_session(leetcode_session: str) -> requests.Session:
    session = requests.Session()
    session.cookies.set("LEETCODE_SESSION", leetcode_session, domain="leetcode.com")
    session.headers.update({
        "Content-Type": "application/json",
        "Referer": f"https://leetcode.com/company/google/?favoriteSlug={FAVORITE_SLUG}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "x-csrftoken": _get_csrf(session),
    })
    return session


def _get_csrf(session: requests.Session) -> str:
    resp = session.get("https://leetcode.com/", timeout=10)
    return session.cookies.get("csrftoken", "")


def fetch_all_questions(session: requests.Session) -> list[dict]:
    questions = []
    skip = 0

    while True:
        payload = {
            "query": QUERY,
            "variables": {
                "favoriteSlug": FAVORITE_SLUG,
                "skip": skip,
                "limit": PAGE_SIZE,
            },
        }
        resp = session.post(GRAPHQL_URL, json=payload, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        if "errors" in data:
            print(f"GraphQL error: {data['errors']}", file=sys.stderr)
            sys.exit(1)

        page = data["data"]["favoriteQuestionList"]
        questions.extend(page["questions"])

        total = page["totalLength"]
        skip += PAGE_SIZE
        print(f"  Fetched {min(skip, total)}/{total} questions...", flush=True)

        if not page["hasMore"]:
            break

        time.sleep(0.5)  # be polite

    return questions


def format_question(q: dict) -> dict:
    tags = ", ".join(t["name"] for t in q.get("topicTags", []))
    url = f"https://leetcode.com/problems/{q['titleSlug']}/"
    return {
        "id": q["questionFrontendId"],
        "title": q["title"],
        "difficulty": q["difficulty"],
        "acceptance_rate": f"{float(q.get('acRate', 0)):.1f}%",
        "paid_only": q["paidOnly"],
        "status": q.get("status") or "not attempted",
        "tags": tags,
        "url": url,
    }


def print_table(rows: list[dict]) -> None:
    if not rows:
        print("No questions found.")
        return

    col_widths = {k: len(k) for k in rows[0]}
    for row in rows:
        for k, v in row.items():
            col_widths[k] = max(col_widths[k], len(str(v)))

    header = "  ".join(k.upper().ljust(col_widths[k]) for k in col_widths)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row[k]).ljust(col_widths[k]) for k in col_widths))


def save_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} questions to {path}")


def save_json(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print(f"\nSaved {len(rows)} questions to {path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch Google LeetCode questions (last 30 days)")
    parser.add_argument("--session", required=True, help="Your LEETCODE_SESSION cookie value")
    parser.add_argument("--output", help="Output file path (.csv or .json). Defaults to stdout table.")
    args = parser.parse_args()

    print(f"Connecting to LeetCode...")
    session = make_session(args.session)

    print(f"Fetching Google interview questions (last 30 days)...")
    raw = fetch_all_questions(session)

    rows = [format_question(q) for q in raw]
    rows.sort(key=lambda r: int(r["id"]))

    print(f"\nFound {len(rows)} questions\n")

    if args.output:
        if args.output.endswith(".json"):
            save_json(rows, args.output)
        else:
            save_csv(rows, args.output)
    else:
        print_table(rows)


if __name__ == "__main__":
    main()
