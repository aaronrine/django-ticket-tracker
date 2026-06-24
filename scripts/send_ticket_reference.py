#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request


TICKET_PATTERN = re.compile(r"(?:ticket[-_/ ]?|#)(\d+)", re.IGNORECASE)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def find_ticket_id(*texts: str) -> int | None:
    for text in texts:
        if not text:
            continue

        match = TICKET_PATTERN.search(text)
        if match:
            return int(match.group(1))

    return None


def main() -> int:
    api_url = os.environ.get(
        "TICKET_TRACKER_API_URL",
        "http://localhost:8000/tickets/integrations/ticket-references/",
    )
    token = os.environ.get("TICKET_TRACKER_TOKEN")

    if not token:
        print("TICKET_TRACKER_TOKEN is missing; skipping ticket reference link.")
        return 0

    commit_hash = git("rev-parse", "HEAD")
    short_hash = git("rev-parse", "--short", "HEAD")
    branch_name = git("branch", "--show-current")
    subject = git("log", "-1", "--pretty=%s")
    body = git("log", "-1", "--pretty=%b")
    author = git("log", "-1", "--pretty=%an <%ae>")

    ticket_id = find_ticket_id(branch_name, subject, body)

    if ticket_id is None:
        print("No ticket id found in branch name or commit message; skipping.")
        return 0

    repo_url = os.environ.get("TICKET_TRACKER_REPO_URL", "").rstrip("/")
    commit_url = f"{repo_url}/commit/{commit_hash}" if repo_url else ""

    payload = {
        "ticket_id": ticket_id,
        "kind": "commit",
        "provider": os.environ.get("TICKET_TRACKER_PROVIDER", "custom-git"),
        "external_id": commit_hash,
        "url": commit_url,
        "title": subject or f"Commit {short_hash}",
        "metadata": {
            "repo": repo_url,
            "branch": branch_name,
            "author": author,
            "short_hash": short_hash,
        },
    }

    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
            print(f"Linked commit {short_hash} to ticket {ticket_id}.")
            if response_body:
                print(response_body)
            return 0

    except urllib.error.HTTPError as error:
        print(f"Ticket reference API returned HTTP {error.code}.")
        print(error.read().decode("utf-8"))
        return 0

    except urllib.error.URLError as error:
        print(f"Could not reach ticket reference API: {error}")
        return 0


if __name__ == "__main__":
    sys.exit(main())