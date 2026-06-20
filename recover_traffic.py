"""
This file is only for the old users to resolve the issues with git-traffic-log's old version, new users don't need to run this, it's unnecessary.

- recover_traffic.py is used to recover the traffic log from the analytics branch extracting all the commits and then creating a new traffic log, it concatenates all 14days chunks in commits and then deduplicating them, to recover all the traffic logs which got lost due to an issue in old version.

Usage:
    python recover_traffic.py
"""

import subprocess
import sys
from io import StringIO

import pandas as pd


# ── helpers ─────────────────────────────────────────────────────────────────

def run_git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def ensure_analytics_fetched():
    print("Fetching origin/analytics …")
    r = run_git("fetch", "origin", "analytics", "--quiet")
    if r.returncode != 0:
        # Maybe already have it locally
        r2 = run_git("branch", "-r")
        if "origin/analytics" not in r2.stdout:
            print("[x] Could not fetch origin/analytics. Check your remote and token.")
            sys.exit(1)


def get_commits():
    """Return list of (hash, subject) for every commit on origin/analytics."""
    r = run_git("log", "--format=%H\t%s", "origin/analytics")
    if r.returncode != 0:
        # Fallback: try local branch name
        r = run_git("log", "--format=%H\t%s", "analytics")
    if r.returncode != 0 or not r.stdout.strip():
        print("[x] Could not list commits on analytics branch.")
        print("    Make sure you ran: git fetch origin analytics")
        sys.exit(1)
    rows = []
    for line in r.stdout.strip().splitlines():
        if "\t" in line:
            h, subj = line.split("\t", 1)
            rows.append((h.strip(), subj.strip()))
    return rows


def read_csv_at_commit(commit_hash):
    """Extract traffic/traffic_log.csv from a specific git commit."""
    r = run_git("show", f"{commit_hash}:traffic/traffic_log.csv")
    if r.returncode != 0:
        return None
    try:
        df = pd.read_csv(StringIO(r.stdout))
        # Must have at minimum these columns to be a valid traffic CSV
        required = {"repo", "type", "timestamp_utc", "count", "uniques"}
        if not required.issubset(df.columns):
            return None
        return df
    except Exception:
        return None


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ensure_analytics_fetched()

    commits = get_commits()
    print(f"Found {len(commits)} commit(s) on analytics branch\n")

    all_dfs = []
    skipped = 0

    for i, (commit_hash, subject) in enumerate(commits, start=1):
        df = read_csv_at_commit(commit_hash)
        if df is not None:
            all_dfs.append(df)
            label = f"{len(df):>5} rows"
        else:
            skipped += 1
            label = "  (no CSV)"
        short_subj = subject[:60] + ("…" if len(subject) > 60 else "")
        print(f"  [{i:>3}/{len(commits)}] {commit_hash[:8]}  {label}  — {short_subj}")

    print()
    if not all_dfs:
        print("[x] No usable CSV found in any commit. Nothing to recover.")
        sys.exit(1)

    if skipped:
        print(f"  (skipped {skipped} commit(s) with no CSV — likely the initial empty commit)")
        print()

    # ── merge & deduplicate ──────────────────────────────────────────────────
    print(f"Merging {len(all_dfs)} snapshot(s) …")
    merged = pd.concat(all_dfs, ignore_index=True)
    total_before = len(merged)

    # Normalize types first
    merged["captured_at_utc"] = pd.to_datetime(merged["captured_at_utc"], utc=True)
    merged["timestamp_utc"] = pd.to_datetime(merged["timestamp_utc"], utc=True)
    merged["repo"] = merged["repo"].astype(str).str.strip()
    merged["type"] = merged["type"].astype(str).str.strip()
    merged["count"] = pd.to_numeric(merged["count"], errors="coerce").astype("Int64")
    merged["uniques"] = pd.to_numeric(merged["uniques"], errors="coerce").astype("Int64")

    # Keep earliest capture for each logical traffic row
    merged = merged.sort_values("captured_at_utc")
    merged = merged.drop_duplicates(
        subset=["repo", "type", "timestamp_utc"],
        keep="first",
    )

    # Final canonical order
    merged = merged.sort_values(
        ["repo", "type", "timestamp_utc", "captured_at_utc"]
    ).reset_index(drop=True)

    # Canonical column order
    merged = merged[
        ["captured_at_utc", "repo", "type", "timestamp_utc", "count", "uniques"]
    ]

    print(f"  Rows before dedup : {total_before:,}")
    print(f"  Rows after  dedup : {len(merged):,}")
    print()

    merged["captured_at_utc"] = pd.to_datetime(
        merged["captured_at_utc"],
        utc=True,
        format="mixed",
    )

    merged["timestamp_utc"] = pd.to_datetime(
        merged["timestamp_utc"],
        utc=True,
        format="mixed",
    )
    # ── write output ─────────────────────────────────────────────────────────
    out_path = "traffic_log_recovered.csv"
    merged.to_csv(out_path, index=False, lineterminator="\n")
    # ── summary ──────────────────────────────────────────────────────────────
    print(f"Saved  →  {out_path}")
    print()
    print("=" * 55)
    print("RECOVERED SUMMARY")
    print("=" * 55)
    ts_min = merged["timestamp_utc"].min().date()
    ts_max = merged["timestamp_utc"].max().date()
    span = (merged["timestamp_utc"].max() - merged["timestamp_utc"].min()).days
    print(f"  Traffic date range : {ts_min}  →  {ts_max}  ({span} days)")
    print(f"  Repos tracked      : {merged['repo'].nunique()}")
    print(f"  Unique capture days: {merged['captured_at_utc'].dt.date.nunique()}")
    print()

    by_type = merged.groupby("type")[["count", "uniques"]].sum()
    print(by_type.to_string())
    print()

    final_actions = """
    set -euo pipefail

    repo_root="$(git rev-parse --show-toplevel)"
    tmpworktree="$(mktemp -d -p "$(dirname "$repo_root")" analytics-fix.XXXXXX)"
    branch="analytics-recovery-$(date +%s)"

    git fetch origin analytics
    git worktree add -b "$branch" "$tmpworktree" origin/analytics
    mkdir -p "$tmpworktree/traffic"
    cp "$repo_root/traffic_log_recovered.csv" "$tmpworktree/traffic/traffic_log.csv"

    git -C "$tmpworktree" add traffic/traffic_log.csv
    git -C "$tmpworktree" commit -m "fix: restore full traffic history"
    git -C "$tmpworktree" push origin HEAD:analytics

    git worktree remove "$tmpworktree" --force
    git branch -D "$branch"
    """

    print("=" * 55)
    print("NEXT STEPS")
    print("=" * 55)
    print()
    print("1. Verify traffic_log_recovered.csv looks correct.")
    print()
    print("2. Push it to the analytics branch(Paste&run below commands directly): or you can manually change the traffic_log.csv file with the traffic_log_recovered.csv file from github")
    print(final_actions)
    print()
    print("3. Apply the workflow fix, the new yaml file.. Run git actions maunally once and that's it.")
    print("Done, now it'll track data infinitely long. ")

if __name__ == "__main__":
    main()