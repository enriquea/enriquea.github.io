# Enrique Audain, personal website

A one-page research profile with a publication list that syncs from ORCID.
Plain HTML and CSS, built by a small Python script (standard library only).

## How it works

- `config.json`: name, position, bio, research interests, profile links, selected papers (by DOI).
- `data/publications.json`: publication list. Refreshed from the ORCID public API by `scripts/fetch_orcid.py`.
- `templates/`: page template and stylesheet.
- `scripts/build.py`: renders `_site/index.html`.
- `.github/workflows/deploy.yml`: on every push and every Monday, refreshes publications from ORCID, commits any change, builds, and deploys to GitHub Pages.

## Edit content

- Bio, position, interests, selected papers: edit `config.json`.
- Photo: add `assets/photo.jpg` and set `"photo": "assets/photo.jpg"` in `config.json`.
- Remove the draft banner and highlighting: set `"draft": false`.
- Missing paper: add it to your ORCID record (the site follows ORCID).

## Run locally

    python scripts/fetch_orcid.py   # optional, needs internet
    python scripts/build.py
    python -m http.server -d _site 8000

## Publish on GitHub Pages

1. Create a public repository named `enriquea.github.io` and push this folder to `main`.
2. In the repository: Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. The site appears at https://enriquea.github.io after the first workflow run.

## Custom domain later

Settings > Pages > Custom domain, enter the domain, then add a CNAME DNS record
pointing to `enriquea.github.io` (or A records for an apex domain). No rebuild needed.

## Other sections

- `data/collaborations.json`: institutions on the world map (name, city, coordinates, people, paper DOIs).
- `data/conferences.json`: talks and posters. Each item: `{"year": 2025, "type": "talk" | "poster", "title": "...", "event": "...", "location": "...", "url": "..."}`.
- `data/community.json`: open-source projects.
- Preprints: the ORCID sync keeps a preprint only while no journal version exists, and the page labels it "Preprint · not yet peer reviewed". Add `"role": "first" | "co-first" | "last"` to a work in `data/publications.json` to show an authorship badge.

## Design features (added 2026-11-25)

- `config.json`: `statement` (large line at the top), `threads` (the two research threads, with keywords used to tag new papers automatically), `career` (stations under the timeline; add `from`/`to` years to draw them on the axis).
- `data/paper_meta.json`: per-paper thread, authorship role, one-line summary and optional `image` for the selected-paper cards. Keyed by DOI, so it survives the ORCID sync.
- `data/coauthor_network.json`: all co-author cities for the interactive map.
- `templates/script.js`: theme switch, publication filters, section menu highlight, map interaction. No libraries.
- `scripts/fetch_github.py`: refreshes star counts for the software cards during the weekly run.
- Photo: save it as `assets/photo.jpg` and set `"photo": "assets/photo.jpg"` in `config.json`.
- "Print CV" uses the browser's print dialog with a compact print stylesheet.

## How the ORCID sync treats your list

The sync **merges**: it adds works from ORCID and fills gaps, but never removes an entry
that is already in `data/publications.json`. To add a paper ORCID lacks, add it to that file.
To hide a preprint that has since been published, add its DOI to `published_preprint_dois`
in `config.json` (this happens by itself when the journal version has the same title).
