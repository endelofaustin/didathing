#!/usr/bin/env python3
from pathlib import Path
import urllib.request, re, subprocess
ROOT=Path(__file__).resolve().parent
headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
for p in [28,35]:
    book="EWA8AAAAcAAJ"; url=f"https://books.google.com/books?id={book}&pg=PP{p}&jscmd=SearchWithinVolume2&q=Osiandri"
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=80) as r:
        html=r.read().decode('utf8','replace')
    m=re.findall(r'"pid":"PP'+str(p)+r'","src":"(.*?)"',html)
    assert m, f"Missing signed page: {p}"
    imgurl=m[-1].replace(r'\u0026','&').replace(r'\/','/')
    with urllib.request.urlopen(urllib.request.Request(imgurl,headers={**headers,'Referer':url}),timeout=80) as r:
        data=r.read()
    (ROOT/f"PP{p:03}.jpg").write_bytes(data)
    print("sample",p,len(data),flush=True)
    out=ROOT/f"PP{p:03}_german_print.txt"
    cmd=["kraken","-i",str(ROOT/f"PP{p:03}.jpg"),str(out),"segment","-bl","ocr","-m",str(ROOT/"german_print.mlmodel")]
    r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=210)
    print("RUN",r.returncode,r.stdout[-1200:],flush=True)
    if out.exists():
        text=out.read_text(encoding="utf8")
        print("OCR page",p,"chars",len(text),"sample",text[:2500],flush=True)
