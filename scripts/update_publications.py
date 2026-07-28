#!/usr/bin/env python3
"""Regenerate the Publications block in index.html from PubMed.

Source of truth: papers whose PubMed grant list contains the Stanford ADRC center
grant **P30 AG066515** (either spacing). We show a small recent selection per year
(no gaps) plus a link to the complete list; the total count is computed live.

Run by .github/workflows/update-publications.yml (weekly). Safe to run by hand:
    python scripts/update_publications.py
It only rewrites the region between the <!-- PUBLICATIONS:START --> / :END markers,
and never writes a partial/empty list (a PubMed outage is a no-op, exit 0).
"""
import urllib.request, urllib.parse, re, json, time, datetime, pathlib, sys

EMAIL = "statzihuai@gmail.com"
TOOL = "sphere-adrc-portal"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SERIAL = "AG066515"                 # grant serial for the Stanford ADRC P30
PER_YEAR = 4                        # recent papers shown per year
FIRST_YEAR = 2021                   # oldest year to display
INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"


def api(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode({**params, "tool": TOOL, "email": EMAIL})
    last = None
    for _ in range(4):
        try:
            return urllib.request.urlopen(url, timeout=90).read().decode("utf-8", "ignore")
        except Exception as e:  # transient NCBI hiccup
            last = e
            time.sleep(3)
    raise RuntimeError(f"NCBI request failed ({path}): {last}")


def esearch(term, retmax=0, sort=None):
    p = {"db": "pubmed", "term": term, "retmax": retmax}
    if sort:
        p["sort"] = sort
    return re.findall(r"<Id>(\d+)</Id>", api("/esearch.fcgi", p))


def esummary(ids):
    return json.loads(api("/esummary.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))["result"]


def is_p30(grant_ids):
    return any(re.sub(r"\s", "", g) == "P30AG066515" for g in grant_ids)


def total_p30_count():
    """Count papers genuinely tagged with the P30 grant (both spacings)."""
    ids = esearch(f"{SERIAL}[Grant Number]", retmax=2000)
    keep = set()
    for i in range(0, len(ids), 180):
        xml = api("/efetch.fcgi", {"db": "pubmed", "id": ",".join(ids[i:i + 180]), "retmode": "xml"})
        for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            pm = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
            grants = re.findall(r"<GrantID>(.*?)</GrantID>", art)
            if pm and is_p30(grants):
                keep.add(pm.group(1))
        time.sleep(0.4)
    return len(keep)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def authors(r):
    ns = [a["name"] for a in r.get("authors", []) if a.get("authtype") != "CollectiveName" and a.get("name")]
    return (", ".join(ns[:3]) + (", et al." if len(ns) > 3 else "")) if ns else "(consortium)"


def jclean(s):
    return (s or "").split(" : ")[0].strip()


CARD = ('<div style="background:var(--bg-white);border:1px solid var(--border);border-left:3px solid var(--cardinal);'
        'border-radius:0 var(--radius-md) var(--radius-md) 0;padding:.75rem 1.1rem;">'
        '<div style="font-weight:500;font-size:13px;color:var(--text-primary);margin-bottom:2px;">{t}</div>'
        '<div style="font-size:12px;color:var(--text-muted);">{a} &middot; <em>{j}</em> {y} &middot; '
        '<a href="https://pubmed.ncbi.nlm.nih.gov/{p}/" target="_blank" rel="noopener" '
        'style="color:var(--cardinal);text-decoration:none;">PMID:{p}</a></div></div>')
YLABEL = ('<div style="font-size:11.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;'
          'color:var(--text-muted);margin-bottom:.5rem;">{y}</div>')
GRP = '<div style="display:flex;flex-direction:column;gap:.5rem;margin-bottom:1rem;">{c}</div>'


def build_block(total):
    year_now = datetime.date.today().year
    groups = []
    seen = set()
    # Group by the PubMed *publication-date* year ([pdat]) — robust to epub-vs-print skew (the esummary
    # "pubdate" field can disagree with the indexed year, so we label by the query year, not that field).
    for y in range(year_now, FIRST_YEAR - 1, -1):
        ids = [i for i in esearch(f"{SERIAL}[Grant Number] AND {y}[pdat]", retmax=12, sort="pub_date") if i not in seen]
        if not ids:
            continue
        res = esummary(ids)
        picks = []
        for u in res.get("uids", []):
            if u in seen:
                continue
            r = res[u]
            if r.get("source", "").lower() in ("biorxiv", "medrxiv"):   # peer-reviewed only
                continue
            picks.append((u, r))
            seen.add(u)
            if len(picks) >= PER_YEAR:
                break
        if picks:
            groups.append((y, picks))
        time.sleep(0.3)
    if not groups:
        raise RuntimeError("no publications returned")

    body = []
    for y, picks in groups:
        body.append(YLABEL.format(y=y))
        cards = "".join(CARD.format(t=esc(r.get("title", "").rstrip(".")), a=esc(authors(r)),
                                    j=esc(jclean(r.get("fulljournalname") or r.get("source", ""))),
                                    y=y, p=u) for u, r in picks)
        body.append(GRP.format(c=cards))
    body = "\n          ".join(body)

    tot = f"{total:,}" if total else "many"
    link = f"https://pubmed.ncbi.nlm.nih.gov/?term={SERIAL}%5BGrant+Number%5D&amp;sort=date"
    intro = ('<p style="font-size:13.5px;color:var(--text-muted);margin-bottom:1.25rem;">'
             'A selection of recent peer-reviewed publications acknowledging NIH/NIA grant '
             f'<strong>P30AG066515</strong> (the Stanford ADRC) &mdash; <strong>{tot} total</strong>, '
             f'auto-compiled from PubMed. <a href="{link}" target="_blank" rel="noopener" '
             'style="color:var(--cardinal);text-decoration:none;">view the complete list on PubMed &#8594;</a></p>')
    footer = ('<div style="text-align:center;padding:.5rem 0 0;">\n'
              f'            <a href="{link}" target="_blank" rel="noopener" '
              'style="color:var(--cardinal);font-size:13px;font-weight:500;text-decoration:none;">'
              f'See all {tot} publications on PubMed &#8594;</a>\n          </div>')
    return intro + "\n\n          " + body + "\n          " + footer


def main():
    try:
        total = total_p30_count()
        block = build_block(total)
    except Exception as e:
        print(f"::warning::publications not updated ({e})")
        return 0  # graceful no-op on any PubMed failure
    text = INDEX.read_text()
    pat = re.compile(r"(<!-- PUBLICATIONS:START[^>]*-->).*?(<!-- PUBLICATIONS:END -->)", re.S)
    if not pat.search(text):
        print("::error::PUBLICATIONS markers not found in index.html")
        return 1
    new = pat.sub(lambda m: m.group(1) + "\n          " + block + "\n          " + m.group(2), text)
    if new != text:
        INDEX.write_text(new)
        print(f"publications updated (total={total})")
    else:
        print("publications unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
