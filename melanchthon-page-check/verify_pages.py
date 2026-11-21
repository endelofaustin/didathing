import urllib.request,urllib.parse,http.cookiejar,re,json,time
from pathlib import Path
out=Path("scans");out.mkdir(exist_ok=True)
bid="EWA8AAAAcAAJ"
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
audit=[]
for p in range(1,75):
    url=f"https://books.google.com/books?id={bid}&pg=PP{p}&jscmd=SearchWithinVolume2&q=Osiandri"
    row={"page":p}
    try:
        with opener.open(urllib.request.Request(url,headers=headers),timeout=45) as response:
            page=response.read().decode("utf-8","replace")
        matches=re.findall(r'"pid":"PP'+str(p)+r'","src":"(.*?)"',page)
        if not matches:
            row["result"]="no_signed_image";row["html_bytes"]=len(page)
        else:
            imgurl=matches[-1].replace(r'\u0026','&').replace(r'\/','/')
            row["image_url"]=imgurl
            req=urllib.request.Request(imgurl,headers={**headers,"Referer":url,"Accept":"image/avif,image/webp,image/*,*/*"})
            with opener.open(req,timeout=50) as response:
                data=response.read(10000000)
                row["image_type"]=response.headers.get("Content-Type","")
            row["bytes"]=len(data)
            if (data[:3]==b"\xff\xd8\xff" or data[:8]==b"\x89PNG\r\n\x1a\n") and len(data)>10000:
                (out/f"PP{p:03}.jpg").write_bytes(data);row["result"]="VALID_IMAGE"
            else:row["result"]="not_image";row["header"]=data[:40].decode("utf8","replace")
    except Exception as e:row["result"]="error";row["error"]=str(e)[:300]
    print(row,flush=True);audit.append(row);time.sleep(.4)
(out/"image_probe_report.json").write_text(json.dumps(audit,indent=2))

valid=sum(r['result']=='VALID_IMAGE' for r in audit)
print(f'COMPLETE PAGE RETRIEVAL: {valid}/{len(audit)} images; inspect all missing before translation',flush=True)
