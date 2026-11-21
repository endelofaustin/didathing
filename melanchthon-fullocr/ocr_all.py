#!/usr/bin/env python3
"""Historical OCR draft from scans: review before publication."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parent
IMG=ROOT/"images"
OUT=ROOT/"transcriptions"
OUT.mkdir(exist_ok=True)
all_text=[]; report=[]
for pp in range(27,54):
    img=IMG/f"PP{pp:03}.jpg"
    if not img.is_file():raise RuntimeError(f"Missing scan PP{pp:03}; stop transcription")
    out=OUT/f"PP{pp:03}.txt"
    args=["kraken","-i",str(img),str(out),"segment","-bl","ocr","-m",str(ROOT/"german_print.mlmodel")]
    cp=subprocess.run(args,text=True,capture_output=True,timeout=300)
    print(f"PP{pp:03}: return code {cp.returncode}: {cp.stdout[-120:]} {cp.stderr[-180:]}",flush=True)
    if cp.returncode or not out.is_file():raise RuntimeError(f"OCR failure: {pp}")
    text=out.read_text(encoding="utf8").strip()
    info={"page":pp,"chars":len(text),"words":len(text.split())}
    report.append(info);print(info,flush=True)
    if len(text)<250:raise RuntimeError(f"Suspiciously short OCR text: PP{pp:03} ({len(text)} chars)")
    all_text.append(f"\n\n======== ORIGINAL SCAN PP{pp:03} ========\n\n{text}")
(OUT/"all_pages_ocr_UNPROOFREAD.txt").write_text("".join(all_text).strip(),encoding="utf8")
(OUT/"ocr_report.json").write_text(json.dumps(report,indent=2))
print("COMPLETE OCR DRAFT PAGES",len(report),"WORDS",sum(x["words"] for x in report),flush=True)
