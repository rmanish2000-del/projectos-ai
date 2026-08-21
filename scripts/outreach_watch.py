#!/usr/bin/env python3
"""Outreach reply watcher — public GitHub reads only; notify via issue on this repo.

No secrets beyond GITHUB_TOKEN for creating issues on rmanish2000-del/projectos-ai.
Never writes to third-party repos. Never summarises reply bodies.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "outreach-threads.json"
STATE_PATH = ROOT / "state" / "outreach-seen.json"
OWN_REPO = os.environ.get("GITHUB_REPOSITORY", "rmanish2000-del/projectos-ai")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
IGNORE_AUTHOR = "rmanish2000-del"
PROOF_FORCE_ID = os.environ.get("PROOF_FORCE_COMMENT_ID", "").strip()


def http_json(url: str, method: str = "GET", body: dict | None = None, auth: bool = False):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "projectos-outreach-watcher",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if auth:
        if not TOKEN:
            raise RuntimeError("GITHUB_TOKEN required for authenticated calls")
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        snippet = e.read().decode("utf-8", errors="replace")[:500]
        return e.code, {"_error": True, "status": e.code, "snippet": snippet}


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(seen: set[int]) -> None:
    payload = {
        "seen_ids": sorted(seen),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_failure_issue(status: int, detail: str) -> None:
    title = "WATCHER FAILURE"
    # Find existing open failure issue
    q = f"repo:{OWN_REPO} is:issue is:open in:title \"{title}\""
    code, data = http_json(
        f"https://api.github.com/search/issues?q={urllib.request.quote(q)}",
        auth=True,
    )
    body = (
        f"**Outreach reply watcher poll failure**\n\n"
        f"- status: `{status}`\n"
        f"- detail:\n```\n{detail}\n```\n"
        f"- time: {datetime.now(timezone.utc).isoformat()}\n"
    )
    if code == 200 and data and data.get("items"):
        issue_number = data["items"][0]["number"]
        http_json(
            f"https://api.github.com/repos/{OWN_REPO}/issues/{issue_number}/comments",
            method="POST",
            body={"body": body},
            auth=True,
        )
        print(f"Updated WATCHER FAILURE issue #{issue_number}")
        return
    code2, created = http_json(
        f"https://api.github.com/repos/{OWN_REPO}/issues",
        method="POST",
        body={"title": title, "body": body},
        auth=True,
    )
    if code2 in (200, 201) and created and "number" in created:
        print(f"Opened WATCHER FAILURE issue #{created['number']}")
    else:
        print(f"Could not open failure issue: {code2} {created}", file=sys.stderr)


def open_reply_issue(thread: dict, comment: dict) -> str | None:
    login = comment.get("user", {}).get("login", "?")
    repo_label = f"{thread['owner']}/{thread['repo']}#{thread['issue']}"
    title = f"REPLY: {login} on {repo_label}"
    body = (
        f"**Thread:** `{repo_label}`\n"
        f"**Author:** `{login}`\n"
        f"**Comment id:** `{comment.get('id')}`\n"
        f"**Created:** `{comment.get('created_at')}`\n"
        f"**Permalink:** {comment.get('html_url')}\n\n"
        f"---\n\n"
        f"### Full comment (verbatim)\n\n"
        f"{comment.get('body', '')}\n"
    )
    code, created = http_json(
        f"https://api.github.com/repos/{OWN_REPO}/issues",
        method="POST",
        body={"title": title, "body": body},
        auth=True,
    )
    if code in (200, 201) and created and "html_url" in created:
        print(f"Opened {created['html_url']}")
        return created["html_url"]
    print(f"Failed to open reply issue: {code} {created}", file=sys.stderr)
    ensure_failure_issue(code, str(created))
    return None


def poll_thread(thread: dict, seen: set[int]) -> list[dict]:
    owner, repo, num = thread["owner"], thread["repo"], thread["issue"]
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{num}/comments?per_page=100"
    code, data = http_json(url, auth=False)
    if code == 403 and isinstance(data, dict) and data.get("_error"):
        ensure_failure_issue(403, f"rate-limit or forbidden on {owner}/{repo}#{num}: {data.get('snippet')}")
        return []
    if code != 200 or not isinstance(data, list):
        ensure_failure_issue(code, f"poll {owner}/{repo}#{num}: {data}")
        return []
    floor = thread.get("ignore_comment_ids_up_to") or 0
    new_comments = []
    for c in data:
        cid = int(c.get("id", 0))
        if floor and cid <= int(floor):
            continue
        author = (c.get("user") or {}).get("login") or ""
        if author == IGNORE_AUTHOR:
            continue
        if PROOF_FORCE_ID and str(cid) == PROOF_FORCE_ID:
            # Force-treat as new for acceptance proof even if already in state
            new_comments.append(c)
            continue
        if cid in seen:
            continue
        new_comments.append(c)
    return new_comments


def main() -> int:
    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        print("config/outreach-threads.json missing", file=sys.stderr)
        return 2
    global IGNORE_AUTHOR
    IGNORE_AUTHOR = cfg.get("ignore_author") or IGNORE_AUTHOR
    state = load_json(STATE_PATH, {"seen_ids": []})
    seen = set(int(x) for x in state.get("seen_ids", []))

    opened = 0
    for thread in cfg.get("threads", []):
        for comment in poll_thread(thread, seen):
            url = open_reply_issue(thread, comment)
            if url:
                opened += 1
            seen.add(int(comment["id"]))

    save_state(seen)
    print(f"done: opened={opened} seen_total={len(seen)}")
    for u in cfg.get("unwatchable", []):
        print(f"UNWATCHABLE: {u.get('source')}: {u.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
