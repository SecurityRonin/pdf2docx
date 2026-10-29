import fitz, glob, os, re, json, collections
paths = sorted(glob.glob(os.path.expanduser("~/Downloads/*.pdf")))[:80]
rows=[]
num_re = re.compile(r'^\s*(?:(\d+(?:\.\d+)*)[.)]?\s+|([ivxlcIVXLC]+[.)])\s+|[•▪◦‣·∙]\s*|[-–—]\s+|[a-z][.)]\s+|[A-Z][.)]\s+|\(\w+\)\s+)')
for p in paths:
    try:
        d=fitz.open(p)
        tagged = bool(d.get_toc() or (d.pdf_catalog() and d.xref_get_key(d.pdf_catalog(),"StructTreeRoot")[1]!="null"))
        toc = len(d.get_toc())
        sizes=collections.Counter(); fonts=collections.Counter(); nb=0; nlines=0
        numlines=0; sample=[]
        for pno in range(min(6,d.page_count)):
            pg=d[pno]
            for b in pg.get_text("dict")["blocks"]:
                if b["type"]!=0: continue
                for l in b["lines"]:
                    nlines+=1
                    txt="".join(s["text"] for s in l["spans"]).strip()
                    if not txt: continue
                    if num_re.match(txt):
                        numlines+=1
                        if len(sample)<3: sample.append(txt[:60])
                    for s in l["spans"]:
                        if s["text"].strip():
                            sizes[round(s["size"],1)]+=len(s["text"]); fonts[s["font"]]+=len(s["text"])
        body = sizes.most_common(1)[0][0] if sizes else 0
        uniq=len(sizes)
        rows.append(dict(file=os.path.basename(p)[:40], pages=d.page_count, tagged=tagged, toc=toc,
                         sizes=uniq, body=body, numlines=numlines, nlines=nlines, sample=sample))
        d.close()
    except Exception as e:
        rows.append(dict(file=os.path.basename(p)[:40], err=str(e)[:60]))
json.dump(rows, open("research/census.json","w"), ensure_ascii=False, indent=1)
ok=[r for r in rows if "err" not in r]
print(f"files={len(rows)} ok={len(ok)}")
print(f"tagged(toc or StructTreeRoot)={sum(r['tagged'] for r in ok)}/{len(ok)}")
print(f"with TOC={sum(1 for r in ok if r['toc']>0)}/{len(ok)}")
print(f"median distinct font sizes={sorted(r['sizes'] for r in ok)[len(ok)//2]}")
print(f"files with <=3 distinct sizes={sum(1 for r in ok if r['sizes']<=3)}/{len(ok)}")
print(f"files with >=6 distinct sizes={sum(1 for r in ok if r['sizes']>=6)}/{len(ok)}")
print(f"files with numbering-like lines={sum(1 for r in ok if r['numlines']>0)}/{len(ok)}")
for r in sorted(ok,key=lambda r:-r['numlines'])[:6]:
    print(f"  {r['file']:42s} num={r['numlines']:3d}/{r['nlines']:4d} sizes={r['sizes']} {r['sample'][:2]}")
