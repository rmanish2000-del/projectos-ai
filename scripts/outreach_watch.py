#!/usr/bin/env python3
"""Poll configured public GitHub threads and write new replies to Drive."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "outreach-threads.json"
DEFAULT_STATE = Path("/var/lib/projectos/outreach-seen.json")
DEFAULT_REPORTS = Path("/mnt/gdrive/AGENT-REPORTS")
IGNORE_AUTHOR = "rmanish2000-del"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H%M%S_%fZ")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def write_report(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    temporary = directory / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, target)
    return target


def fetch_comments(thread: dict) -> list[dict]:
    owner, repo, number = thread["owner"], thread["repo"], thread["issue"]
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments?per_page=100"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "projectos-outreach-watcher", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            snippet = response.read(500).decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {response.status}: {snippet}")
        value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, list):
            raise RuntimeError("HTTP 200 returned a non-list response")
        return value


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, seen: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen_ids": sorted(seen), "updated_at": now_utc().isoformat()}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def reply_body(thread: dict, comment: dict) -> str:
    repo = f"{thread['owner']}/{thread['repo']}"
    return (
        f"THREAD: https://github.com/{repo}/issues/{thread['issue']}\n"
        f"AUTHOR: {(comment.get('user') or {}).get('login', '?')}\n"
        f"PERMALINK: {comment.get('html_url', '')}\n"
        f"TIMESTAMP: {comment.get('created_at', '')}\n"
        f"COMMENT-ID: {comment.get('id', '')}\n\n"
        f"BODY-VERBATIM:\n{comment.get('body') or ''}\n"
    )


def failure_body(thread: dict, status: str, snippet: str) -> str:
    repo = f"{thread['owner']}/{thread['repo']}#{thread['issue']}"
    return f"THREAD: {repo}\nSTATUS: {status}\nRESPONSE-SNIPPET: {snippet[:500]}\n"


def run(config_path: Path, state_path: Path, reports_dir: Path) -> int:
    config = load_json(config_path, None)
    if not isinstance(config, dict) or not isinstance(config.get("threads"), list):
        print(f"invalid or missing config: {config_path}", file=sys.stderr)
        return 2
    seen = {int(value) for value in load_json(state_path, {"seen_ids": []}).get("seen_ids", [])}
    failures = 0
    written: list[Path] = []
    for thread in config["threads"]:
        try:
            comments = fetch_comments(thread)
        except urllib.error.HTTPError as error:
            snippet = error.read(500).decode("utf-8", errors="replace")
            name = f"OUTREACH-WATCH-FAILURE_{timestamp(now_utc())}.md"
            written.append(write_report(reports_dir, name, failure_body(thread, str(error.code), snippet)))
            failures += 1
            continue
        except Exception as error:
            name = f"OUTREACH-WATCH-FAILURE_{timestamp(now_utc())}.md"
            written.append(write_report(reports_dir, name, failure_body(thread, type(error).__name__, str(error))))
            failures += 1
            continue
        floor = int(thread.get("ignore_comment_ids_up_to") or 0)
        for comment in comments:
            comment_id = int(comment.get("id") or 0)
            author = ((comment.get("user") or {}).get("login") or "")
            if not comment_id or comment_id <= floor or comment_id in seen or author == IGNORE_AUTHOR:
                continue
            repo_name = safe_name(f"{thread['owner']}-{thread['repo']}")
            created = str(comment.get("created_at") or "unknown").replace(":", "-")
            name = f"OUTREACH-REPLY_{repo_name}_{thread['issue']}_{safe_name(created)}.md"
            written.append(write_report(reports_dir, name, reply_body(thread, comment)))
            seen.add(comment_id)
    save_state(state_path, seen)
    for path in written:
        print(path)
    print(f"done: replies_or_failures={len(written)} failures={failures} seen_total={len(seen)}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()
    return run(args.config, args.state, args.reports)


if __name__ == "__main__":
    raise SystemExit(main())
