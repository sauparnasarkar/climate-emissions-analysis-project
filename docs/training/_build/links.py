import os, re, glob, sys
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, ArrayObject, TextStringObject, NullObject, BooleanObject

HERE=os.path.dirname(os.path.abspath(__file__)); S=os.path.join(HERE,'out'); MD=os.path.dirname(HERE)
RAW=S+'/raw'; HTML='file://'+S+'/html/'

def slug(t):
    t=re.sub(r'[`*]','',t.strip().lower()); t=re.sub(r'[^\w\s-]','',t); return re.sub(r'\s','-',t)
def norm(t): return re.sub(r'\s+',' ',re.sub(r'[`*]','',t)).strip().lower()

docs=sorted(os.path.relpath(p,RAW)[:-4] for p in glob.glob(RAW+'/**/*.pdf',recursive=True))
lines={}
pages={}   # doc -> list of normalized page text
heads={}   # doc -> {anchor: page}
for d in docs:
    r=PdfReader(f'{RAW}/{d}.pdf'); raw_txt=[(p.extract_text() or '') for p in r.pages]; pages[d]=[norm(t) for t in raw_txt]; lines[d]=[{norm(l) for l in t.splitlines()} for t in raw_txt]
    hs=[]; seen={}
    in_code=False
    for line in open(f'{MD}/{d}.md'):
        if line.startswith('```'): in_code=not in_code
        m=None if in_code else re.match(r'^#{1,6}\s+(.*)',line)
        if m: hs.append(m.group(1))
    cur=0; hm={}
    for h in hs:
        a=slug(h); n=seen.get(a,0); seen[a]=n+1
        key=a if n==0 else f'{a}-{n}'
        t=norm(h)
        found=False
        for i in range(cur,len(pages[d])):
            if t in lines[d][i]: cur=i; found=True; break
        if not found:
            for i in range(cur,len(pages[d])):
                if t in pages[d][i]: cur=i; break
        hm[key]=cur
    heads[d]=hm

missing=0; total=0
for d in docs:
    r=PdfReader(f'{RAW}/{d}.pdf'); w=PdfWriter(clone_from=r)
    for pg in w.pages:
        for a in (pg.get('/Annots') or []):
            a=a.get_object()
            act=a.get('/A')
            if a.get('/Subtype')=='/Link' and not act and a.get('/Dest') is not None and not isinstance(a['/Dest'],list):
                nm=str(a['/Dest']).lstrip('/')
                if nm in heads[d]:
                    a[NameObject('/Dest')]=ArrayObject([w.pages[heads[d][nm]].indirect_reference,NameObject('/Fit')]); total+=1
                else: print('NO ANCHOR',d,nm); missing+=1
                continue
            if a.get('/Subtype')!='/Link' or not act: continue
            act=act.get_object()
            uri=act.get('/URI')
            if not uri or not uri.startswith(HTML): continue
            rel=uri[len(HTML):]; path,_,frag=rel.partition('#')
            if path.endswith('.md'): tgt=path[:-3]
            elif path.endswith('.html'): tgt=path[:-5]
            else: continue
            total+=1
            if tgt not in heads: print('NO TARGET',d,uri); missing+=1; continue
            pi=heads[tgt].get(frag,0) if frag else 0
            if frag and frag not in heads[tgt]: print('NO ANCHOR',d,tgt,frag); missing+=1
            if tgt==d:
                dest=ArrayObject([w.pages[pi].indirect_reference,NameObject('/Fit')])
                new=DictionaryObject({NameObject('/S'):NameObject('/GoTo'),NameObject('/D'):dest})
            else:
                fp=os.path.relpath(tgt+'.pdf',os.path.dirname(d) or '.')
                fs=DictionaryObject({NameObject('/Type'):NameObject('/Filespec'),NameObject('/F'):TextStringObject(fp),NameObject('/UF'):TextStringObject(fp)})
                new=DictionaryObject({NameObject('/S'):NameObject('/GoToR'),NameObject('/F'):fs,NameObject('/D'):ArrayObject([NumberObject(pi),NameObject('/Fit')]),NameObject('/NewWindow'):BooleanObject(True)})
            a[NameObject('/A')]=new
    out=f'{MD}/{d}.pdf'
    with open(out,'wb') as f: w.write(f)
print('links rewritten',total,'problems',missing)
