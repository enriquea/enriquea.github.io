#!/usr/bin/env python3
"""Refresh data/publications.json from the public ORCID API.

Uses only the Python standard library. If ORCID cannot be reached, or returns
no works, the existing data file is left untouched so the site still builds.

Usage: python scripts/fetch_orcid.py
"""
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "publications.json"
API = "https://pub.orcid.org/v3.0/" + CONFIG["orcid"]
BATCH = 100  # ORCID bulk endpoint accepts up to 100 put-codes


def get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "personal-site-orcid-sync/1.0",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def val(node, *path):
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def doi_of(work):
    for ext in val(work, "external-ids", "external-id") or []:
        if (ext.get("external-id-type") or "").lower() == "doi":
            doi = ext.get("external-id-value") or ""
            return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I).lower()
    return None


def pmid_of(work):
    for ext in val(work, "external-ids", "external-id") or []:
        if (ext.get("external-id-type") or "").lower() == "pmid":
            return ext.get("external-id-value")
    return None


def to_record(work):
    title = val(work, "title", "title", "value") or "Untitled"
    year = val(work, "publication-date", "year", "value")
    authors = []
    for c in val(work, "contributors", "contributor") or []:
        name = val(c, "credit-name", "value")
        if name:
            authors.append(name)
    doi = doi_of(work)
    return {
        "title": title.strip().rstrip("."),
        "authors": authors,
        "journal": val(work, "journal-title", "value") or "",
        "year": int(year) if year and str(year).isdigit() else None,
        "doi": doi,
        "pmid": pmid_of(work),
        "url": (val(work, "url", "value") or (f"https://doi.org/{doi}" if doi else "")),
        "type": work.get("type") or "",
    }


def main():
    try:
        groups = get(API + "/works").get("group", [])
        # One preferred summary per group (ORCID already groups duplicates).
        codes = []
        for g in groups:
            summaries = g.get("work-summary") or []
            if summaries:
                best = max(summaries, key=lambda s: int(s.get("display-index") or 0))
                codes.append(str(best["put-code"]))
        works = []
        for i in range(0, len(codes), BATCH):
            bulk = get(API + "/works/" + ",".join(codes[i:i + BATCH]))
            for item in bulk.get("bulk", []):
                if item.get("work"):
                    works.append(to_record(item["work"]))
    except Exception as exc:  # network error, API change, etc.
        print(f"ORCID fetch failed, keeping existing data: {exc}", file=sys.stderr)
        return 0

    patterns = [re.compile(p, re.I) for p in CONFIG.get("exclude_title_patterns", [])]
    seen, clean = set(), []
    for w in works:
        if any(p.search(w["title"]) for p in patterns):
            continue
        key = w["doi"] or w["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(w)

    # Preprints: keep one only while no journal version of the same work exists.
    def norm(title):
        return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()

    PREPRINT_DOI = ("10.1101/", "10.64898/", "10.21203/", "10.48550/", "10.20944/", "10.2139/")
    for w in clean:
        if w["type"] == "preprint" or (w["doi"] or "").startswith(PREPRINT_DOI):
            w["type"] = "preprint"
    published = {norm(w["title"]) for w in clean if w["type"] != "preprint"}
    superseded = set(CONFIG.get("published_preprint_dois", []))
    clean = [w for w in clean if not (w["type"] == "preprint"
             and (norm(w["title"]) in published or (w["doi"] or "") in superseded))]

    if not clean:
        print("ORCID returned no works, keeping existing data.", file=sys.stderr)
        return 0

    clean.sort(key=lambda w: (w["year"] or 0, w["title"]), reverse=True)
    OUT.write_text(json.dumps({
        "source": f"ORCID {CONFIG['orcid']}",
        "updated": date.today().isoformat(),
        "works": clean,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(clean)} works to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
