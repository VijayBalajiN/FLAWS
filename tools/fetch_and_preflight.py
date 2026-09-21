"""Download arXiv LaTeX sources for candidate papers and PREFLIGHT them with zero LLM cost.

A candidate is accepted only if, with the pipeline's own functions:
  * a LaTeX source exists and yields a sane combined.tex (size-bounded, has document body),
  * the UNMODIFIED paper compiles to a PDF via src.utils.latex_to_pdf.compile_latex,
    has no unresolved refs, and compresses with ghostscript.
So later LaTeX/tool errors cannot come from a paper that was never buildable.
"""
import gzip, io, json, os, re, shutil, subprocess, sys, tarfile, time
sys.path.insert(0, os.getcwd())
from src.utils.latex_to_pdf import (combine_latex_sources, compile_latex,
                                    check_pdf_for_unresolved_references, compress_pdf_ghostscript)
import fitz
from tools.latex_preflight import missing_packages, first_latex_error

QUOTA = {"cs.LG": 6, "cs.CV": 3, "cs.AI": 3, "cs.CL": 3, "cs.CR": 2, "cs.RO": 1, "cs.SE": 1, "cs.MA": 1}
MAX_COMBINED = 220_000   # chars; bounds tokens per API call
MIN_COMBINED = 30_000
STATE = "tools/preflight_state.json"
state = json.load(open(STATE)) if os.path.exists(STATE) else {}
cands = json.load(open("tools/candidates.json"))
os.makedirs("data/papers", exist_ok=True); os.makedirs("data/_dl", exist_ok=True)

def folder_of(aid): return "arxiv_" + aid.split("v")[0].replace(".", "_").replace("/", "_")

def download(aid):
    out = f"data/_dl/{folder_of(aid)}.bin"
    r = subprocess.run(["curl","-sSL","-f","-m","180","--max-filesize","30000000","-A","curl/8.7.1","-o",out,
                        f"https://arxiv.org/e-print/{aid.split('v')[0]}"], capture_output=True, text=True)
    time.sleep(3)
    return out if r.returncode == 0 and os.path.getsize(out) > 0 else None

def extract(binpath, dest):
    os.makedirs(dest, exist_ok=True)
    data = open(binpath,"rb").read()
    if data[:4] == b"%PDF": return "pdf-only"
    try:
        if tarfile.is_tarfile(binpath):
            with tarfile.open(binpath) as t:
                for m in t.getmembers():   # no path traversal / links
                    if m.name.startswith(("/","..")) or ".." in m.name.split("/") or m.issym() or m.islnk(): continue
                    t.extract(m, dest)
            return "ok"
        txt = gzip.decompress(data)
        open(os.path.join(dest,"main.tex"),"wb").write(txt); return "ok"
    except Exception as e:
        return f"extract-fail:{e}"

def evaluate(c):
    aid, folder = c["id"], folder_of(c["id"])
    dest = f"data/papers/{folder}"
    bin_ = download(aid)
    if not bin_: return "download-failed"
    st = extract(bin_, dest)
    os.remove(bin_)
    if st != "ok": return st
    texs = [p for p in __import__("glob").glob(dest+"/**/*.tex", recursive=True)]
    if not texs: return "no-tex"
    try: comb = combine_latex_sources(dest)
    except Exception as e: return f"combine-fail:{e}"
    t = open(comb, errors="ignore").read()
    if "\\begin{document}" not in t or "\\end{document}" not in t: return "combined-no-body"
    if len(re.findall(r"\\section", t)) < 3: return "combined-few-sections"
    if not (MIN_COMBINED <= len(t) <= MAX_COMBINED): return f"size-out-of-range:{len(t)}"
    if re.search(r"\{minted\}|pythontex|\\write18|\\immediate\\write", t): return "needs-shell-escape"
    absent = missing_packages(t, dest)
    if absent: return "missing-packages:" + ",".join(absent)
    des = f"/data/_preflight/{folder}"
    os.makedirs(des.lstrip("/"), exist_ok=True)
    pre_tex = f"{des.lstrip('/')}/altered_pre.tex"
    shutil.copy(comb, pre_tex)
    pdf = compile_latex(paper=folder, des=des, main_tex=pre_tex)
    if not os.path.exists(pdf): return "compile-failed:" + first_latex_error(f"{des.lstrip('/')}/latex_compilation_log.txt")[:120]
    if len(fitz.open(pdf)) < 4: return "pdf-too-short"
    if not check_pdf_for_unresolved_references(pdf): return "unresolved-refs"
    try: compress_pdf_ghostscript(pdf, pdf.replace(".pdf","_small.pdf"))
    except Exception as e: return f"gs-failed:{e}"
    return "ACCEPT"

def main():
    order = sorted(cands, key=lambda c: 0)  # already shuffled with seed 42
    got = {k: sum(1 for v in state.values() if v["status"]=="ACCEPT" and v["primary"]==k) for k in QUOTA}
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9   # max candidates to try this invocation
    tried = 0
    for c in order:
        if c["primary"] not in QUOTA or c["id"] in state: continue
        if got[c["primary"]] >= QUOTA[c["primary"]]: continue
        if tried >= limit: break
        tried += 1
        s = evaluate(c)
        folder = folder_of(c["id"])
        state[c["id"]] = dict(c, status=s, folder=folder)
        if s == "ACCEPT": got[c["primary"]] += 1
        else:
            shutil.rmtree(f"data/papers/{folder}", ignore_errors=True)
            shutil.rmtree(f"data/_preflight/{folder}", ignore_errors=True)
        json.dump(state, open(STATE,"w"), indent=1)
        print(f"[{sum(got.values())}/{sum(QUOTA.values())}] {c['id']} {c['primary']} -> {s} | {c['title'][:60]}", flush=True)
        if sum(got.values()) >= sum(QUOTA.values()): break
    print("quota status:", got)
if __name__ == "__main__":
    main()
