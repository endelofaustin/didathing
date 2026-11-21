import urllib.request,re,json
from pathlib import Path
out=Path("probe");out.mkdir(exist_ok=True)
for label,bookid in (("42pp","90ZoAAAAcAAJ"),("30pp","QEllAAAAcAAJ")):
    u=f"https://books.google.com/books?id={bookid}&jscmd=SearchWithinVolume2&q=Osiandri"
    try:
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=50) as r:data=r.read().decode("utf8","replace")
        (out/f"{label}.html").write_text(data)
        lines=[]
        for pattern in ("pageImageUrl","pageImage","download","printsec","pageList","pageInfo","viewability","fullview","preview","bibkeys","token","gbs","PDF","_page","pagenum","book_info"):
            for m in list(re.finditer(pattern,data,re.I))[:12]:
                lines.append([pattern,data[max(0,m.start()-220):m.end()+220]])
        (out/f"{label}_contexts.json").write_text(json.dumps(lines,indent=2,ensure_ascii=False))
        print(label,"bytes",len(data),"context matches",len(lines),flush=True)
    except Exception as e:print("ERROR",label,e,flush=True)
