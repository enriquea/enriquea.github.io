#!/usr/bin/env python3
"""Build the static site into _site/ from config.json, data/*.json and
templates/. Standard library only.

Usage: python scripts/build.py
"""
import html
import json
import re
import shutil
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
MAX_AUTHORS = 8  # longer author lists are shortened around the site owner's name
ROLE_LABEL = {"first": "First author", "co-first": "Co-first author", "last": "Senior author"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def read_json(name, default):
    p = ROOT / "data" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def is_me(name, cfg):
    n = name.lower().replace(".", "").strip()
    return any(n == m.lower().replace(".", "").strip() for m in cfg["author_match"])


def authors_html(authors, cfg):
    if not authors:
        return ""
    names = list(authors)
    if len(names) > MAX_AUTHORS:
        mine = next((i for i, a in enumerate(names) if is_me(a, cfg)), None)
        head = names[:3]
        if mine is not None and mine >= 3:
            head = names[:3] + ["…", names[mine]]
        names = head + ["…", names[-1]] if names[-1] not in head else head
    out = [f"<b>{esc(a)}</b>" if is_me(a, cfg) else esc(a) for a in names]
    return ", ".join(out).replace(", et al.", " et al.")


def enrich(works, cfg):
    """Attach thread, role and summary from data/paper_meta.json (or guess the thread)."""
    meta = read_json("paper_meta.json", {"papers": {}})["papers"]
    threads = cfg.get("threads", {})
    for w in works:
        m = meta.get((w.get("doi") or "").lower(), {})
        for k in ("role", "summary", "image"):
            if m.get(k):
                w[k] = m[k]
        thread = m.get("thread")
        if not thread:
            title = w["title"].lower()
            thread = next((t for t, d in threads.items() if any(k in title for k in d.get("keywords", []))), "")
        w["thread"] = thread
    return works


def tags_html(w, cfg):
    tags = []
    t = cfg.get("threads", {}).get(w.get("thread"))
    if t:
        tags.append(f'<span class="tag th th-{esc(w["thread"])}">{esc(t["short"])}</span>')
    if w.get("type") == "review":
        tags.append('<span class="tag">Review</span>')
    if w.get("type") == "preprint":
        tags.append('<span class="tag pre">Preprint · not yet peer reviewed</span>')
    if w.get("role") in ROLE_LABEL:
        tags.append(f'<span class="tag role">{ROLE_LABEL[w["role"]]}</span>')
    return "".join(tags)


def pub_url(w):
    return w.get("url") or (f"https://doi.org/{w['doi']}" if w.get("doi") else "")


def pub_html(w, cfg, indent="          "):
    doi, url = w.get("doi"), pub_url(w)
    title = esc(w["title"])
    title = f'<a href="{esc(url)}">{title}</a>' if url else title
    parts = [f'<span class="t">{title}</span>']
    a = authors_html(w.get("authors"), cfg)
    if a:
        parts.append(f'<span class="a">{a}</span>')
    venue = f'<span class="journal">{esc(w.get("journal"))}</span>' if w.get("journal") else ""
    parts.append(f'<span class="v">{venue}{tags_html(w, cfg)}</span>')
    ids = []
    if doi:
        ids.append(f'<a href="https://doi.org/{esc(doi)}">doi:{esc(doi)}</a>')
    if w.get("pmid"):
        ids.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{esc(w["pmid"])}/">PMID {esc(w["pmid"])}</a>')
    if ids:
        parts.append(f'<span class="ids">{"".join(ids)}</span>')
    data = (f' data-thread="{esc(w.get("thread"))}" data-pre="{int(w.get("type") == "preprint")}"'
            f' data-lead="{int(w.get("role") in ROLE_LABEL)}"')
    return f'{indent}<li class="pub th-{esc(w.get("thread"))}"{data}>{"".join(parts)}</li>'


def card_html(w, cfg, ph):
    url = pub_url(w)
    img = f'<img class="fig" src="{esc(w["image"])}" alt="">' if w.get("image") else ""
    summary = f'<p class="sum">{ph(esc(w["summary"]))}</p>' if w.get("summary") else ""
    return (f'        <li class="card th-{esc(w.get("thread"))}">{img}'
            f'<span class="v"><span class="journal">{esc(w.get("journal"))}</span><span class="yr">{esc(w.get("year"))}</span></span>'
            f'<a class="t" href="{esc(url)}">{esc(w["title"])}</a>{summary}'
            f'<span class="a">{authors_html(w.get("authors"), cfg)}</span>'
            f'<span class="v">{tags_html(w, cfg)}</span></li>')


def path_html(cfg, this_year):
    """Career path: one line. Places sit above it, degrees and research visits below it.
    On narrow screens the same list reads as a vertical timeline."""
    career = [c for c in cfg.get("career", []) if c.get("from")]
    if not career:
        return ""
    y0 = min([c["from"] for c in career] + [e["year"] for e in cfg.get("education", [])])
    y1 = this_year + 1
    span = y1 - y0

    def pct(y):
        return f"{100 * (y - y0) / span:.2f}%"

    ev = []
    for e in cfg.get("education", []):
        ev.append((e["year"], 0, f'<li class="ev deg" style="--a:{pct(e["year"])}">'
                   f'<span class="when">{e["year"]}</span><b>{esc(e["degree"])}</b><span class="sub">{esc(e.get("place"))}</span></li>'))
    for c in career:
        when = c.get("when") or f'{c["from"]}–{c.get("to") or "present"}'
        if c.get("kind") == "visit":
            a = c["from"] + (0.5 if c.get("to") == c["from"] else 0)
            w = max((c.get("to") or c["from"]) - c["from"], 0.3)
            ev.append((c["from"], 2, f'<li class="ev vis" style="--a:{pct(a)};--w:{100 * w / span:.2f}%">'
                       f'<span class="when">{esc(when)}</span><b>{esc(c["place"])}</b><span class="sub">{esc(c.get("org"))}</span></li>'))
        else:
            to = c.get("to") or y1
            ev.append((c["from"], 1, f'<li class="ev pos{"" if c.get("to") else " now"}" style="--a:{pct(c["from"])};--w:{100 * (to - c["from"]) / span:.2f}%">'
                       f'<span class="when">{esc(when)}</span><b>{esc(c["place"])}</b><span class="sub">{esc(c.get("org"))}</span></li>'))
    ev.sort(key=lambda e: (e[0], e[1]))
    rows = {y: i + 1 for i, y in enumerate(sorted({e[0] for e in ev}))}  # events of the same year share a row
    items = [e[2].replace('style="', f'style="--r:{rows[e[0]]};', 1) for e in ev]
    return '<ol class="path">\n        ' + "\n        ".join(items) + '\n      </ol>'


def map_parts(collab, net):
    """Interactive world map: every co-author city, with lines to first/senior-author cities."""
    world = json.loads((ROOT / "templates" / "world.json").read_text(encoding="utf-8"))
    W, H, top = world["width"], world["height"], world["lat_max"]

    def xy(lat, lon):
        return round((lon + 180) / 360 * W, 1), round((top - lat) / 360 * W, 1)

    cities = OrderedDict()
    for c in (net or {}).get("cities", []):
        cities[c["city"]] = {"city": c["city"], "country": c["country"], "lat": c["lat"], "lon": c["lon"],
                             "works": c["works"], "inst": [i["name"] for i in c["institutions"]], "people": [], "lead": 0}
    places = sorted(collab["places"], key=lambda p: (-len(p.get("papers", [])), p["city"]))
    for p in places:
        c = cities.setdefault(p["city"], {"city": p["city"], "country": p["country"], "lat": p["lat"], "lon": p["lon"],
                                          "works": len(p.get("papers", [])), "inst": [p["institution"]], "people": [], "lead": 0})
        c["people"] = p.get("people", [])
        c["lead"] = len(p.get("papers", []))

    hx, hy = xy(collab["home"]["lat"], collab["home"]["lon"])
    arcs, dots, js = [], [], []
    ordered = sorted(cities.values(), key=lambda c: (c["lead"] > 0, c["works"]))  # lead cities drawn last, on top
    for i, c in enumerate(ordered):
        x, y = xy(c["lat"], c["lon"])
        if c["lead"]:
            r = 3.4 + 1.2 * min(c["lead"], 6) ** 0.5
            mx, my = (x + hx) / 2, (y + hy) / 2 - 0.22 * abs(x - hx) - 6
            arcs.append(f'<path class="arc" pathLength="1" d="M{hx},{hy} Q{mx:.1f},{my:.1f} {x},{y}"/>')
        else:
            r = 2.0 + 0.8 * min(c["works"], 12) ** 0.5
        dots.append(f'<circle class="{"dot" if c["lead"] else "net"}" data-i="{i}" cx="{x}" cy="{y}" r="{r:.1f}"/>')
        js.append({"x": x, "y": y, "c": c["city"], "k": c["country"], "n": c["works"], "i": c["inst"], "p": c["people"]})
    svg = (f'<svg id="map" class="map" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="World map of the {len(ordered)} cities where co-authors work">'
           f'<path class="land" d="{world["land"]}"/>{"".join(arcs)}{"".join(dots)}'
           f'<circle class="home" cx="{hx}" cy="{hy}" r="5"/><circle id="map-ring" class="ring" r="9" cx="-99" cy="-99"/></svg>')

    lead_rows = "\n".join(
        f'        <li><span class="ci">{esc(p["city"])}, {esc(p["country"])}</span>'
        f'<span class="inst">{esc(p["institution"])}</span><span class="ppl">{esc(", ".join(p.get("people", [])))}</span></li>'
        for p in places)

    net_html = ""
    if net:
        topn = max(c["works"] for c in net["countries"])
        bars = "".join(
            f'<li><span class="cn">{esc(c["country"])}</span><span class="bar"><span style="width:{100 * c["works"] / topn:.0f}%"></span></span>'
            f'<span class="cv">{c["works"]}</span></li>' for c in net["countries"])
        by_country = OrderedDict()
        for c in sorted(net["cities"], key=lambda c: (-c["works"], c["city"])):
            by_country.setdefault(c["country"], []).append(c)
        order = [c["country"] for c in net["countries"] if c["country"] in by_country]
        detail = "".join(
            f'<div class="nc"><h4>{esc(co)}</h4><ul>' + "".join(
                f'<li><b>{esc(c["city"])}</b> {esc(", ".join(i["name"] for i in c["institutions"]))}</li>' for c in by_country[co])
            + '</ul></div>' for co in order)
        n_inst = sum(len(c["institutions"]) for c in net["cities"])
        net_html = (f'<h3 class="sub">Co-authors by country</h3><ol class="bars">{bars}</ol>'
                    f'<p class="fine">{esc(net["note"])} Source: {esc(net["source"])}, {esc(net["retrieved"])}.</p>'
                    f'<details class="netlist"><summary>All {len(net["cities"])} cities and {n_inst} institutions</summary><div class="ncs">{detail}</div></details>')
    stats = {"countries": len(net["countries"]) if net else len({p["country"] for p in places}), "cities": len(ordered)}
    return svg, json.dumps(js, ensure_ascii=False, separators=(",", ":")), lead_rows, net_html, stats


def conferences_html(conf):
    rows = []
    items = conf.get("items", [])
    dated = any(c.get("year") for c in items)
    for c in sorted(items, key=lambda c: c.get("year") or 0, reverse=True):  # stable: undated keep file order
        title = esc(c["title"])
        if c.get("url"):
            title = f'<a href="{esc(c["url"])}">{title}</a>'
        where = ", ".join(esc(x) for x in (c.get("event"), c.get("location")) if x)
        kind = esc((c.get("type") or "").capitalize())
        year = f'<span class="year-label">{esc(c.get("year") or "")}</span>' if dated else ""
        rows.append(f'        <li class="conf{"" if dated else " ny"}">{year}'
                    f'<span class="kind k-{esc(c.get("type"))}">{kind}</span>'
                    f'<span class="ct"><span class="t">{title}</span><span class="v">{where}</span></span></li>')
    return "\n".join(rows)


def community_html(comm):
    rows = []
    for p in comm.get("projects", []):
        owner, _, name = p["name"].partition("/")
        meta = []
        if p.get("language"):
            meta.append(f'<span class="lang">{esc(p["language"])}</span>')
        if p.get("stars"):
            meta.append(f'<span class="stars" title="GitHub stars">★ {esc(p["stars"])}</span>')
        if p.get("role"):
            meta.append(f'<span>{esc(p["role"])}</span>')
        rows.append(f'        <li class="repo"><a class="pn" href="{esc(p["url"])}"><span class="ow">{esc(owner)}/</span>{esc(name)}</a>'
                    f'<span class="pd">{esc(p.get("description"))}</span><span class="pm">{"".join(meta)}</span></li>')
    return "\n".join(rows)


def initials(name):
    return "".join(p[0] for p in name.split()[:2]).upper()


def build():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    data = read_json("publications.json", {"works": []})
    works = enrich(data["works"], cfg)
    draft = cfg.get("draft")

    def ph(text):  # placeholder highlight while in draft
        return f'<span class="ph">{text}</span>' if draft else text

    by_year = OrderedDict()
    for w in sorted(works, key=lambda w: (w.get("year") or 0), reverse=True):
        by_year.setdefault(w.get("year") or "Undated", []).append(w)
    groups = []
    for y, ws in by_year.items():
        items = "\n".join(pub_html(w, cfg) for w in ws)
        groups.append(f'      <div class="year-group" id="y{esc(y)}">\n        <div class="year-label">{esc(y)}</div>\n'
                      f'        <ol class="pubs">\n{items}\n        </ol>\n      </div>')

    by_doi = {(w.get("doi") or "").lower(): w for w in works}
    selected = [by_doi[d.lower()] for d in cfg.get("selected_dois", []) if d.lower() in by_doi]

    years = [y for y in by_year if isinstance(y, int)]
    source = "ORCID" if data.get("source", "").startswith("ORCID") else "PubMed"
    n_pre = sum(1 for w in works if w.get("type") == "preprint")

    collab = read_json("collaborations.json", None)
    net = read_json("coauthor_network.json", None)
    map_svg, map_json, lead_rows, net_html, mstats = map_parts(collab, net) if collab else ("", "[]", "", "", {"countries": 0, "cities": 0})

    threads = cfg.get("threads", {})
    counts = {t: sum(1 for w in works if w.get("thread") == t) for t in threads}
    filters = [f'<button type="button" class="chip" data-f="all" aria-pressed="true">All <span>{len(works)}</span></button>']
    for t, d in threads.items():
        filters.append(f'<button type="button" class="chip th-{esc(t)}" data-f="thread:{esc(t)}" aria-pressed="false">'
                       f'<i class="sw"></i>{esc(d["label"])} <span>{counts[t]}</span></button>')
    n_lead = sum(1 for w in works if w.get("role") in ROLE_LABEL)
    if n_lead:
        filters.append(f'<button type="button" class="chip" data-f="lead" aria-pressed="false">First or senior author <span>{n_lead}</span></button>')
    if n_pre:
        filters.append(f'<button type="button" class="chip" data-f="pre" aria-pressed="false">Preprints <span>{n_pre}</span></button>')
    legend = "".join(f'<span class="lg th-{esc(t)}"><i class="sw"></i>{esc(d["label"])}</span>' for t, d in threads.items())
    legend += '<span class="lg pre"><i class="sw"></i>Preprint</span>' if n_pre else ""

    stats = [(len(works), "publications"), (mstats["countries"], "co-author countries"),
             (max(years) - min(years) + 1 if years else 0, f"years publishing, since {min(years)}" if years else "years")]
    stats_html = "".join(f'<div class="stat"><b>{n}</b><span>{esc(l)}</span></div>' for n, l in stats)

    photo = (f'<img class="photo" src="{esc(cfg["photo"])}" alt="Portrait of {esc(cfg["name"])}">' if cfg.get("photo") else
             f'<div class="photo" role="img" aria-label="Photo placeholder">{initials(cfg["name"])}</div>')
    keys = {"ORCID": "iD", "Google Scholar": "GS", "GitHub": "GH", "ResearchGate": "RG", "LinkedIn": "in"}
    links = [f'      <li><a href="{esc(u)}"><span class="k">{keys.get(k, "→")}</span><span>{esc(k)}</span></a></li>'
             for k, u in cfg["links"].items()]
    contact = ""
    if cfg.get("emails"):
        contact = ('<div class="contact"><h2>Contact</h2><ul>' + "".join(
            f'<li><a href="mailto:{esc(e)}">{esc(e)}</a></li>' for e in cfg["emails"]) + '</ul></div>')

    conf_rows = conferences_html(read_json("conferences.json", {"items": []}))
    if not conf_rows and draft:
        conf_rows = '        <li class="empty">' + ph("No talks or posters listed yet. Add them to data/conferences.json.") + '</li>'
    comm = read_json("community.json", {"projects": []})

    values = {
        "CSS": (ROOT / "templates" / "style.css").read_text(encoding="utf-8"),
        "JS": (ROOT / "templates" / "script.js").read_text(encoding="utf-8"),
        "DRAFT_BANNER": ('<div class="draft">Draft preview. Highlighted text is a placeholder for Enrique to confirm or rewrite.</div>' if draft else ""),
        "NAME": esc(cfg["name"]),
        "POSITION_TEXT": esc(cfg["position"]),
        "POSITION": esc(cfg["position"]),
        "AFFILIATION": esc(cfg["affiliation"]),
        "ORCID": esc(cfg["orcid"]),
        "PHOTO": photo,
        "LINKS": "\n".join(links),
        "CONTACT": contact,
        "STATEMENT": "“" + esc(cfg.get("statement", "")) + "”",
        "BIO": "\n".join(f"      <p>{ph(esc(p))}</p>" for p in cfg["bio"]),
        "INTERESTS": "\n".join(f"        <li>{esc(i)}</li>" for i in cfg["interests"]),
        "TIMELINE": path_html(cfg, int(str(data.get("updated") or "2026")[:4])),
        "LEGEND": legend,
        "SELECTED": "\n".join(card_html(w, cfg, ph) for w in selected),
        "FILTERS": "".join(filters),
        "PUBCOUNT": f"From {source}, updated {esc(data.get('updated'))}",
        "PUBLICATIONS": "\n".join(groups),
        "MAP": map_svg,
        "MAP_DATA": map_json.replace("</", "<\\/"),
        "MAP_SUMMARY": f'Co-authors in {mstats["countries"]} countries and {mstats["cities"]} cities',
        "LEAD_ROWS": lead_rows,
        "NETWORK": net_html,
        "CONFERENCES": conf_rows,
        "COMMUNITY": community_html(comm),
        "COMMUNITY_INTRO": esc(comm.get("intro", "")),
        "SITE_URL": esc(cfg.get("site_url", "")),
        "JSONLD": json.dumps({
            "@context": "https://schema.org", "@type": "Person", "name": cfg["name"],
            "jobTitle": cfg["position"], "url": cfg.get("site_url", ""),
            "affiliation": {"@type": "Organization", "name": cfg["affiliation"]},
            "identifier": "https://orcid.org/" + cfg["orcid"],
            "sameAs": list(cfg["links"].values()),
            "knowsAbout": cfg.get("interests", []),
        }, ensure_ascii=False).replace("</", "<\\/"),
        "FOOTER": f'© {esc(cfg["name"])} · Publications sync from <a href="{esc(cfg["links"]["ORCID"])}">ORCID</a> · Last updated {esc(data.get("updated"))}',
    }
    page = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    if not conf_rows:  # nothing to show yet: leave the section and its menu entry out
        page = re.sub(r'\s*<section id="conferences">.*?</section>', "", page, flags=re.S)
        page = re.sub(r'\s*<a href="#conferences">[^<]*</a>', "", page)
    for k, v in values.items():
        page = page.replace("{{" + k + "}}", v)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "index.html").write_text(page, encoding="utf-8")
    if (ROOT / "assets").exists():
        shutil.copytree(ROOT / "assets", OUT / "assets")
    (OUT / ".nojekyll").write_text("")
    site = cfg.get("site_url", "").rstrip("/")
    if site:  # help search engines find and understand the page
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n")
        (OUT / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f'  <url><loc>{site}/</loc><lastmod>{esc(data.get("updated"))}</lastmod></url>\n</urlset>\n')
    print(f"Built {OUT / 'index.html'} with {len(works)} publications")


if __name__ == "__main__":
    build()
