#!/usr/bin/env python3
"""Refresh star counts in data/community.json from the GitHub API.
Leaves the file untouched on any error. Standard library only."""
import json
import sys
import urllib.request
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "community.json"


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    changed = False
    for p in data.get("projects", []):
        try:
            req = urllib.request.Request("https://api.github.com/repos/" + p["name"],
                                         headers={"User-Agent": "personal-site-sync/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                info = json.load(r)
            stars, lang = info.get("stargazers_count"), info.get("language")
            if stars is not None and stars != p.get("stars"):
                p["stars"], changed = stars, True
            if lang and not p.get("language"):
                p["language"], changed = lang, True
        except Exception as exc:
            print(f"skip {p['name']}: {exc}", file=sys.stderr)
    if changed:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
