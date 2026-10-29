import fitz, glob, os, re, json
paths = sorted(glob.glob(os.path.expanduser("~/Downloads/*.pdf")))
strict=[]
for p in paths:
    try:
        d=fitz.open(p)
        cat=d.pdf_catalog()
        st=d.xref_get_key(cat,"StructTreeRoot")[1]
        # count StructElem objects
        nelem=0
        if st not in ("null",None):
            try:
                x=int(st.split()[0]); nelem=1
                seen=set(); stack=[x]
                while stack and nelem<20000:
                    cur=stack.pop()
                    if cur in seen: continue
                    seen.add(cur)
                    k=d.xref_get_key(cur,"K")
                    if k[0]=="array":
                        for tok in re.findall(r'(\d+) 0 R',k[1]): stack.append(int(tok))
                        nelem+=len(re.findall(r'(\d+) 0 R',k[1]))
                    elif k[0]=="xref": stack.append(int(k[1].split()[0]))
            except Exception: pass
        has_lang = d.xref_get_key(cat,"Lang")[1] not in ("null",None)
        strict.append(dict(f=os.path.basename(p)[:44], pages=d.page_count, struct_elems=nelem,
                           lang=has_lang, toc=len(d.get_toc())))
        d.close()
    except Exception as e:
        strict.append(dict(f=os.path.basename(p)[:44], err=str(e)[:50]))
json.dump(strict,open("research/tags.json","w"),indent=1,ensure_ascii=False)
ok=[s for s in strict if "err" not in s]
print(f"total={len(strict)} ok={len(ok)}")
for th in (0,1,10,50):
    print(f"  files with >{th} StructElem: {sum(1 for s in ok if s['struct_elems']>th)}/{len(ok)}")
print(f"  with /Lang: {sum(1 for s in ok if s['lang'])}/{len(ok)}")
print("  best tagged:", [(s['f'],s['struct_elems']) for s in sorted(ok,key=lambda s:-s['struct_elems'])[:5]])
