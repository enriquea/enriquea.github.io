#!/usr/bin/env python3
"""Refresh data/publications.json from the public ORCID API.

Uses only the Python standard library. ORCID works are merged into the existing list: nothing curated is removed, and
if ORCID cannot be reached the data file is left untouched so the site still builds.

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

    merged = merge(json.loads(OUT.read_text(encoding="utf-8")).get("works", []) if OUT.exists() else [], works)
    if not merged:
        print("No works after merging, keeping existing data.", file=sys.stderr)
        return 0
    OUT.write_text(json.dumps({
        "source": f"ORCID {CONFIG['orcid']}, merged with curated entries",
        "updated": date.today().isoformat(),
        "works": merged,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(merged)} works to {OUT.relative_to(ROOT)}")
    return 0


PREPRINT_DOI = ("10.1101/", "10.64898/", "10.26434/", "10.21203/", "10.48550/", "10.20944/", "10.2139/")


def norm(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def preprint_server(doi):
    doi = doi or ""
    if doi.startswith("10.26434/"):
        return "ChemRxiv"
    if doi.startswith("10.48550/"):
        return "arXiv"
    if doi.startswith("10.21203/"):
        return "Research Square"
    if re.match(r"10\.(1101|64898)/\d{4}\.\d{2}\.\d{2}\.\d{8}$", doi):
        return "medRxiv"
    if doi.startswith(("10.1101/", "10.64898/")):
        return "bioRxiv"
    return "Preprint"


def merge(existing, incoming):
    """Add ORCID works to the existing list without losing anything curated.

    - A work already in the list (same DOI or same title) is kept; ORCID only fills
      gaps (a longer author list, a missing journal, PMID or link).
    - A work that is in the list but not in ORCID stays. ORCID records are often incomplete.
    - A preprint is dropped once a journal version of the same title is in the list,
      or its DOI is named in config.json "published_preprint_dois".
    """
    patterns = [re.compile(p, re.I) for p in CONFIG.get("exclude_title_patterns", [])]
    out = [dict(w) for w in existing]
    index = {}
    for w in out:
        if w.get("doi"):
            index[w["doi"].lower()] = w
        index.setdefault("t:" + norm(w["title"]) + ":" + str(w.get("type") == "preprint"), w)
    for w in incoming:
        if any(p.search(w["title"]) for p in patterns):
            continue
        if w["type"] == "preprint" or (w["doi"] or "").startswith(PREPRINT_DOI):
            w["type"] = "preprint"
            w["journal"] = w["journal"] or preprint_server(w["doi"])
        have = index.get((w["doi"] or "").lower()) if w["doi"] else None
        have = have or index.get("t:" + norm(w["title"]) + ":" + str(w["type"] == "preprint"))
        if have:
            if len(w["authors"]) > len(have.get("authors") or []):
                have["authors"] = w["authors"]
            for k in ("journal", "pmid", "url", "year", "doi"):
                if not have.get(k) and w.get(k):
                    have[k] = w[k]
        else:
            out.append(w)
            if w["doi"]:
                index[w["doi"]] = w
            index.setdefault("t:" + norm(w["title"]) + ":" + str(w["type"] == "preprint"), w)
    published = {norm(w["title"]) for w in out if w.get("type") != "preprint"}
    superseded = {d.lower() for d in CONFIG.get("published_preprint_dois", [])}
    out = [w for w in out if not (w.get("type") == "preprint"
           and (norm(w["title"]) in published or (w.get("doi") or "").lower() in superseded))]
    out.sort(key=lambda w: (w.get("year") or 0, w["title"]), reverse=True)
    return out


if __name__ == "__main__":
    sys.exit(main())
