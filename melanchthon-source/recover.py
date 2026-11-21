#!/usr/bin/env python3
"""Try public-domain Google Books 1552 scans. NEVER accept a catalog page as a PDF."""
import json, re, urllib.request, urllib.parse, subprocess, time, hashlib
from pathlib import Path
out=Path("source_checks");out.mkdir(exist_ok=True)
books={"Neuber_1552_42pp":"90ZoAAAAcAAJ","Kreutzer_1552_30pp":"QEllAAAAcAAJ"}
headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept":"application/pdf,text/html;q=0.8,*/*;q=0.6"}
results=[]
for name,bid in books.items():
    urls=[
     "https://books.google.com/books/download/Antwort_auff_das_Buch_A_Osiandri_von_der_rechtfertigung_des_menschen.pdf?id="+bid+"&output=pdf",
     "https://books.google.com/books?vid="+bid+"&output=pdf",
     "https://books.google.com/books?id="+bid+"&printsec=frontcover&output=pdf",
     "https://books.google.com/books?id="+bid+"&jscmd=SearchWithinVolume2&q=Osiandri",
     "https://www.google.com/books/edition/_/"+bid+"?hl=en&gbpv=1",
    ]
    for i,url in enumerate(urls,1):
        row={"edition":name,"method":i,"url":url}
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=65) as r:
                data=r.read(90000000)
                row["status"]=r.status;row["final_url"]=r.url;row["content_type"]=r.headers.get("Content-Type","")
            row["bytes"]=len(data)
            if data.startswith(b"%PDF-") and len(data)>50000:
                fn=out/(name+".pdf");fn.write_bytes(data);row["sha256"]=hashlib.sha256(data).hexdigest()
                info=subprocess.run(["pdfinfo",str(fn)],capture_output=True,text=True)
                m=re.search(r"(?m)^Pages:\s*(\d+)",info.stdout)
                row["pages"]=int(m.group(1)) if m else None
                row["result"]="valid_pdf" if row["pages"] and row["pages"]>=25 else "needs_verification"
                print("PDF FOUND",row,flush=True)
                results.append(row)
                break
            else:
                row["result"]="not_pdf";row["sample"]=data[:150].decode("utf8","replace")
        except Exception as ex:row["result"]="error";row["error"]=str(ex)[:300]
        results.append(row);print(row,flush=True)
        time.sleep(1)
(out/"source_retrieval_report.json").write_text(json.dumps(results,indent=2))
if not any(x.get("result")=="valid_pdf" for x in results):
    print("SOURCE BLOCKED: no complete PDF. No audio/video should be published.",flush=True)
