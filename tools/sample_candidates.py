"""Pick candidate arXiv papers accepted at a venue (by arXiv comment), no LLM/API cost.
Writes tools/candidates.json. Polite to arXiv (3s between requests)."""
import json, random, re, subprocess, time, urllib.parse, sys
import xml.etree.ElementTree as ET

VENUE = sys.argv[1] if len(sys.argv) > 1 else "ICML 2026"
CATS = ["cs.LG","cs.AI","cs.CL","cs.CV","cs.RO","cs.CR","cs.SE","cs.IR","cs.DC","cs.NE","cs.MA","cs.DB","cs.HC","cs.GT","cs.DS","cs.SD","cs.PL"]
NS = {"a":"http://www.w3.org/2005/Atom","x":"http://arxiv.org/schemas/atom"}

def fetch(search, n, start):
    qs = "search_query="+urllib.parse.quote(search)+f"&max_results={n}&start={start}&sortBy=submittedDate&sortOrder=descending"
    for i in range(5):
        r = subprocess.run(["curl","-sS","-m","90","-w","\n%{http_code}",f"https://export.arxiv.org/api/query?{qs}"],capture_output=True,text=True)
        body,_,code = r.stdout.rpartition("\n")
        if code == "200": return body
        time.sleep(6*(i+1))
    raise RuntimeError("arxiv api failing")

cands = {}
search = f'co:"{VENUE}" AND (' + " OR ".join(f"cat:{c}" for c in CATS) + ")"
for start in range(0, 800, 100):
    root = ET.fromstring(fetch(search, 100, start))
    ents = root.findall("a:entry", NS)
    if not ents: break
    for e in ents:
        aid = e.find("a:id", NS).text.rsplit("/abs/",1)[1]
        comment = (e.find("x:comment", NS).text or "") if e.find("x:comment", NS) is not None else ""
        cands[aid] = dict(
            id=aid,
            title=" ".join(e.find("a:title", NS).text.split()),
            published=e.find("a:published", NS).text,
            primary=e.find("x:primary_category", NS).attrib["term"],
            comment=" ".join(comment.split()),
        )
    time.sleep(3)

def accepted(c):
    t = c["comment"].lower()
    v = VENUE.lower()
    return v in t and any(k in t for k in ["accepted","to appear","camera","proceedings","appear"]) and not any(k in t for k in ["submitted to","under review","workshop"])

good = [c for c in cands.values() if accepted(c) and c["published"] >= "2025-09"]
print(len(cands), "fetched;", len(good), "look accepted")
random.Random(42).shuffle(good)
json.dump(good, open("candidates.json","w"), indent=1)
from collections import Counter
print(Counter(c["primary"] for c in good))
