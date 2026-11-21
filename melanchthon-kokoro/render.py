#!/usr/bin/env python3
"""Full Melanchthon authorial response (1552), working translation, Kokoro Michael review."""
from pathlib import Path
from kokoro_onnx import Kokoro
import subprocess, re, json, soundfile as sf, numpy as np, hashlib
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"output"
OUT.mkdir(exist_ok=True)
source=(ROOT/"narration.txt").read_text(encoding="utf-8").strip()
words=len(source.split())
if not 3500<=words<=4600: raise RuntimeError(f"Suspiciously short/incomplete historical source: {words}")
for required in ["Theological and Historical Disclaimer","To the Christian Reader","Philipp Melanchthon wishes God's grace","Philipp Melanchthon, signed in his own hand"]:
    if required not in source: raise RuntimeError(f"Missing part of full source: {required}")
if not source.endswith("Philipp Melanchthon, signed in his own hand."): raise RuntimeError("Historical text appears truncated")
parts=re.split(r'(?<=[.!?;:])\s+(?=[A-Z"“(])',source)
chunks=[]
buffer=""
for part in parts:
    while len(part)>420:
        n=part.rfind(" ",0,420)
        if n<155:n=420
        if buffer:chunks.append(buffer);buffer=""
        chunks.append(part[:n].strip());part=part[n:].strip()
    if len(buffer)+len(part)+1>420:
        if buffer:chunks.append(buffer)
        buffer=""
    buffer=(buffer+" "+part).strip()
if buffer:chunks.append(buffer)
if len(chunks)<40:raise RuntimeError("Not enough text chunks for full audiobook")
model=Kokoro(str(ROOT/"kokoro-v1.0.onnx"),str(ROOT/"voices-v1.0.bin"))
seg=OUT/"segments";seg.mkdir(exist_ok=True)
paths=[]
for i,chunk in enumerate(chunks,1):
    p=seg/f"{i:05d}.wav";paths.append(p)
    if not(p.exists() and p.stat().st_size>10000):
        audio,sr=model.create(chunk,voice="am_michael",speed=0.94,lang="en-us")
        arr=np.asarray(audio,dtype=np.float32)
        sf.write(p,np.concatenate([arr,np.zeros(int(sr*.28),dtype=np.float32)]),sr)
    if i%10==0 or i==len(chunks):print(f"Rendered {i}/{len(chunks)}",flush=True)
listing=OUT/"concat.txt";listing.write_text("".join("file '"+str(p.resolve())+"'\n" for p in paths))
final=OUT/"Melanchthon_1552_Justification_Full_English_Audiobook_REVIEW.mp3"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),"-c:a","libmp3lame","-b:a","128k",str(final)],check=True)
duration=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(final)],text=True).strip())
report={"work":"Answer to Andreas Osiander on the Justification of Man","author":"Philipp Melanchthon","date":1552,"scope":"Complete Melanchthon authorial German response; separate Latin appendices excluded","words":words,"chunks":len(chunks),"duration_seconds":duration,"mp3_bytes":final.stat().st_size,"voice":"am_michael","sha256":hashlib.sha256(final.read_bytes()).hexdigest(),"source_url":"https://books.google.com/books?id=EWA8AAAAcAAJ","quality":"WORKING MODERN ENGLISH TRANSLATION, REVIEW EDITION, NOT PEER REVIEWED"}
(OUT/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(OUT/"narration_source.txt").write_text(source,encoding="utf-8")
if duration<950 or duration>3500:raise RuntimeError(f"Unexpected audiobook length: {duration}")
print("COMPLETE AUDIOBOOK",json.dumps(report),flush=True)
