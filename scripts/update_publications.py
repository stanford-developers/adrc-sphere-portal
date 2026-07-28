#!/usr/bin/env python3
"""Regenerate the Publications block in index.html from PubMed + NIH iCite.

Source of truth: papers whose PubMed grant list contains the Stanford ADRC center
grant **P30 AG066515** (either spacing). For each year we show the **top 5 by
citation count** (impact), using NIH's free iCite API for citations. The total
count is computed live.

Run by .github/workflows/update-publications.yml (weekly). Safe to run by hand:
    python scripts/update_publications.py
It only rewrites the region between the <!-- PUBLICATIONS:START --> / :END markers,
and never writes a partial/empty list (a PubMed/iCite outage is a no-op, exit 0).
"""
import urllib.request, urllib.parse, re, json, time, datetime, pathlib, sys
from collections import defaultdict

EMAIL = "statzihuai@gmail.com"
TOOL = "sphere-adrc-portal"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ICITE = "https://icite.od.nih.gov/api/pubs"
SERIAL = "AG066515"                 # grant serial for the Stanford ADRC P30
PER_YEAR = 5                        # top-cited papers shown per year
FIRST_YEAR = 2021                   # oldest year to display
INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"


def _get(url):
    last = None
    for _ in range(4):
        try:
            return urllib.request.urlopen(url, timeout=90).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(3)
    raise RuntimeError(f"request failed ({url.split('?')[0]}): {last}")


def eutils(path, params):
    return _get(EUTILS + path + "?" + urllib.parse.urlencode({**params, "tool": TOOL, "email": EMAIL}))


def esearch(term, retmax=0):
    return re.findall(r"<Id>(\d+)</Id>", eutils("/esearch.fcgi", {"db": "pubmed", "term": term, "retmax": retmax}))


def esummary(ids):
    return json.loads(eutils("/esummary.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))["result"]


def collect_p30():
    """{pmid: pub_year} for every paper genuinely tagged with the P30 grant (both spacings)."""
    ids = esearch(f"{SERIAL}[Grant Number]", retmax=2000)
    out = {}
    for i in range(0, len(ids), 180):
        xml = eutils("/efetch.fcgi", {"db": "pubmed", "id": ",".join(ids[i:i + 180]), "retmode": "xml"})
        for art in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            pm = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
            grants = re.findall(r"<GrantID>(.*?)</GrantID>", art)
            if not (pm and any(re.sub(r"\s", "", g) == "P30AG066515" for g in grants)):
                continue
            yr = re.search(r"<PubDate>.*?<Year>(\d{4})</Year>", art, re.S)
            if yr:
                out[pm.group(1)] = int(yr.group(1))
        time.sleep(0.4)
    return out


def citations(pmids):
    """{pmid: citation_count} from NIH iCite (free, no key)."""
    cc = {}
    for i in range(0, len(pmids), 200):
        try:
            data = json.loads(_get(f"{ICITE}?pmids={','.join(pmids[i:i + 200])}&fl=pmid,citation_count"))
        except Exception:
            data = {"data": []}
        for r in data.get("data", []):
            cc[str(r.get("pmid"))] = r.get("citation_count") or 0
        time.sleep(0.3)
    return cc


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


def build_block():
    papers = collect_p30()                       # {pmid: year}
    if not papers:
        raise RuntimeError("no P30 papers found")
    total = len(papers)
    cc = citations(list(papers))                 # {pmid: citation_count}
    by_year = defaultdict(list)
    for pmid, y in papers.items():
        by_year[y].append(pmid)

    year_now = datetime.date.today().year
    groups = []
    for y in range(year_now, FIRST_YEAR - 1, -1):
        ids = sorted(by_year.get(y, []), key=lambda p: cc.get(p, 0), reverse=True)
        if not ids:
            continue
        res = esummary(ids[: PER_YEAR + 6])       # a few extra to survive preprint filtering
        picks = []
        for u in [i for i in ids if i in res]:    # keep citation order
            r = res[u]
            if r.get("source", "").lower() in ("biorxiv", "medrxiv"):   # peer-reviewed only
                continue
            picks.append((u, r))
            if len(picks) >= PER_YEAR:
                break
        if picks:
            groups.append((y, picks))
        time.sleep(0.2)
    if not groups:
        raise RuntimeError("no displayable groups")

    body = []
    for y, picks in groups:
        body.append(YLABEL.format(y=y))
        cards = []
        for u, r in picks:
            cards.append(CARD.format(t=esc(r.get("title", "").rstrip(".")), a=esc(authors(r)),
                                     j=esc(jclean(r.get("fulljournalname") or r.get("source", ""))),
                                     y=y, p=u))
        body.append(GRP.format(c="".join(cards)))
    body = "\n          ".join(body)

    tot = f"{total:,}"
    link = f"https://pubmed.ncbi.nlm.nih.gov/?term={SERIAL}%5BGrant+Number%5D&amp;sort=date"
    intro = ('<p style="font-size:13.5px;color:var(--text-muted);margin-bottom:1.25rem;">'
             'Selected peer-reviewed publications acknowledging NIH/NIA grant '
             f'<strong>P30AG066515</strong> (the Stanford ADRC), grouped by year. The full list of '
             f'<strong>{tot}</strong> publications can be found '
             f'<a href="{link}" target="_blank" rel="noopener" '
             'style="color:var(--cardinal);text-decoration:none;">on PubMed &#8594;</a>.</p>')
    footer = ('<div style="text-align:center;padding:.5rem 0 0;">\n'
              f'            <a href="{link}" target="_blank" rel="noopener" '
              'style="color:var(--cardinal);font-size:13px;font-weight:500;text-decoration:none;">'
              f'See all {tot} publications on PubMed &#8594;</a>\n          </div>')
    return intro + "\n\n          " + body + "\n          " + footer


def main():
    try:
        block = build_block()
    except Exception as e:
        print(f"::warning::publications not updated ({e})")
        return 0  # graceful no-op on any PubMed/iCite failure
    text = INDEX.read_text()
    pat = re.compile(r"(<!-- PUBLICATIONS:START[^>]*-->).*?(<!-- PUBLICATIONS:END -->)", re.S)
    if not pat.search(text):
        print("::error::PUBLICATIONS markers not found in index.html")
        return 1
    new = pat.sub(lambda m: m.group(1) + "\n          " + block + "\n          " + m.group(2), text)
    if new != text:
        INDEX.write_text(new)
        print("publications updated")
    else:
        print("publications unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
