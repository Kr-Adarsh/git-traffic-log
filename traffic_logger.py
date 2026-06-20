"""
traffic logger — discovers all repos via your token and logs traffic to CSV.
requires TRAFFIC_TOKEN env var.
"""

import os
import csv
import sys
import time
import requests
from datetime import datetime, timezone

# ── config
TOKEN    = os.environ["TRAFFIC_TOKEN"]
API_BASE = "https://api.github.com"
HEADERS  = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

LOG_PATH   = "traffic/traffic_log.csv"
FIELDNAMES = ["captured_at_utc", "repo", "type", "timestamp_utc", "count", "uniques"]

MAX_RETRIES   = 3
RETRY_BACKOFF = 2   # seconds, doubles each retry

def api_get(url, params=None):
    """GET with retries for transient failures."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)

            if r.status_code == 403:
                if "rate limit" in r.text.lower():
                    remaining = r.headers.get("X-RateLimit-Remaining", "?")
                    print(f"  [!] rate limit hit ({remaining} requests left), skipping")
                return None

            if r.status_code == 404:
                return None

            if r.status_code >= 500:
                wait = RETRY_BACKOFF ** attempt
                print(f"  [!] server error {r.status_code}, retrying in {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r

        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                print(f"  [x] request failed after {MAX_RETRIES} attempts: {e}")
                return None
            wait = RETRY_BACKOFF ** attempt
            print(f"  [!] network error, retrying in {wait}s: {e}")
            time.sleep(wait)

    return None

# ── Repo discovery
def discover_repos():
    """Fetch all repos the token can access. Filters to admin/push only."""
    repos = []
    url = f"{API_BASE}/user/repos"
    params = {"per_page": 100, "page": 1}

    while True:
        r = api_get(url, params=params)
        if r is None:
            print("[x] failed to fetch repo list, aborting.")
            sys.exit(1)

        data = r.json()
        if not data:
            break

        for repo in data:
            perms = repo.get("permissions", {})
            full_name = repo["full_name"]
            if perms.get("admin") or perms.get("push"):
                repos.append(full_name)
            else:
                print(f"  [-] {full_name} (no admin/push permission)")

        # check for next page via Link header
        link_header = r.headers.get("Link", "")
        if 'rel="next"' not in link_header:
            break
        params["page"] += 1

    return repos

# ── Traffic fetching
def fetch_traffic(repo_full_name):
    """Fetch clones + views for a repo. Returns (None, None) if no access."""
    clones_url = f"{API_BASE}/repos/{repo_full_name}/traffic/clones"
    views_url  = f"{API_BASE}/repos/{repo_full_name}/traffic/views"

    clones_r = api_get(clones_url)
    views_r  = api_get(views_url)

    if clones_r is None or views_r is None:
        return None, None

    return clones_r.json().get("clones", []), views_r.json().get("views", [])

# ── CSV handling
def load_existing_keys():
    if not os.path.exists(LOG_PATH):
        return set()
    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            (row["repo"], row["type"], row["timestamp_utc"].strip().replace(" ", "T").replace("+00:00", "Z"))
            for row in reader
        }

# ── Main
def main():
    now = datetime.now(timezone.utc).isoformat()

    print("Discovering repos...")
    repos = discover_repos()

    if not repos:
        print("No repos found with admin/push access.")
        return

    print(f"Found {len(repos)} repo(s):")
    for r in repos:
        print(f"  {r}")

    os.makedirs("traffic", exist_ok=True)
    existing_keys = load_existing_keys()
    file_exists   = os.path.exists(LOG_PATH)

    total_new    = 0
    repo_stats   = []
    all_new_rows = []

    for repo_name in repos:
        clones, views = fetch_traffic(repo_name)

        if clones is None and views is None:
            repo_stats.append((repo_name, 0, "skipped"))
            print(f"  {repo_name} — no traffic permission, skipped")
            continue

        new_rows = []

        for entry in (clones or []):
            key = (repo_name, "clone", entry["timestamp"])
            if key not in existing_keys:
                new_rows.append([now, repo_name, "clone", entry["timestamp"], entry["count"], entry["uniques"]])

        for entry in (views or []):
            key = (repo_name, "view", entry["timestamp"])
            if key not in existing_keys:
                new_rows.append([now, repo_name, "view", entry["timestamp"], entry["count"], entry["uniques"]])

        all_new_rows.extend(new_rows)
        status = f"{len(new_rows)} new" if new_rows else "up to date"
        repo_stats.append((repo_name, len(new_rows), status))
        total_new += len(new_rows)

    if all_new_rows:
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(FIELDNAMES)
            writer.writerows(all_new_rows)

    # summary
    print()
    for name, count, status in repo_stats:
        display = name if len(name) <= 38 else name[:35] + "..."
        print(f"  {display:<40} {status}")

    if total_new == 0:
        print(f"\nCSV already up to date.")
    else:
        print(f"\nAppended {total_new} row(s) to {LOG_PATH}")

if __name__ == "__main__":
    main()