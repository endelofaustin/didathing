#!/usr/bin/env python3
import urllib.request,urllib.parse,http.cookiejar,html,re,json,subprocess
from pathlib import Path
out=Path('source');out.mkdir(exist_ok=True)
log=[]
for edition,book in [('FullView_1552_A','EWA8AAAAcAAJ'),('FullView_1552_B','u3g8AAAAcAAJ'),('FullView_1552_C','vHg8AAAAcAAJ')]:
 cj=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
 url=f'https://books.google.com/books?id={book}&jscmd=SearchWithinVolume2&q=Osiandri'
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'})
 try:
  with opener.open(req,timeout=45) as r: content=r.read().decode('utf8','replace')
  (out/f'{edition}_reader.html').write_text(content)
  for ext in ('pdf','epub'):
   match=re.search(r'<a[^>]+id=["\x27]?'+ext+'_download["\x27]?[^>]+href=["\x27]([^"\x27]+)',content,re.I)
   if not match:print('no link',edition,ext,flush=True);continue
   link=html.unescape(match.group(1));print('found',edition,ext,link,flush=True)
   req=urllib.request.Request(link,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36','Referer':url,'Accept':'application/pdf,application/epub+zip,*/*'})
   row={'edition':edition,'format':ext,'link':link}
   try:
    with opener.open(req,timeout=100) as r:
     body=r.read(70*1024*1024);row['status']=r.status;row['content_type']=r.headers.get('Content-Type')
    row['bytes']=len(body);row['start']=body[:12].hex()
    if (ext=='pdf' and body.startswith(b'%PDF-')) or (ext=='epub' and body[:2]==b'PK'):
     name=out/f'{edition}.{ext}';name.write_bytes(body);row['result']='valid'
     if ext=='pdf':
      info=subprocess.run(['pdfinfo',str(name)],capture_output=True,text=True,timeout=20).stdout
      m=re.search(r'(?m)^Pages:\s*(\d+)',info);row['pages']=int(m.group(1)) if m else None
    else:
     row['result']='not_book';(out/f'{edition}_{ext}_response.txt').write_text(body[:2000].decode('utf8','replace'))
   except Exception as e:row['result']='failed';row['error']=str(e)
   log.append(row);print(row,flush=True)
  accessible=f'https://books.google.com/books?id={book}&jscmd=SearchWithinVolume2&q=Osiandri&hl=en&output=html_text'
  req=urllib.request.Request(accessible,headers={'User-Agent':'Mozilla/5.0','Referer':url})
  try:
   with opener.open(req,timeout=65) as r:body=r.read()
   (out/f'{edition}_accessible_text.html').write_bytes(body)
   print(edition,'accessible text bytes',len(body),flush=True)
  except Exception as e: print(edition,'accessible error',e,flush=True)
 except Exception as e:print(edition,'reader error',e,flush=True)
(out/'report.json').write_text(json.dumps(log,indent=2))
