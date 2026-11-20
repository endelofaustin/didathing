#!/usr/bin/env python3
"""Kokoro ONNX Michael rendering of full Zwingli translation, REVIEW ONLY."""
from pathlib import Path
from kokoro_onnx import Kokoro
import numpy as np, soundfile as sf, subprocess, re, json

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"output"
OUT.mkdir(exist_ok=True)
source=(ROOT/"narration.txt").read_text(encoding="utf8").strip()
assert source.startswith("Huldrych Zwingli. A Remonstrance to Fridolin Lindauer")
assert "Grace and peace from God the Father" in source
assert "if you would rather belong to Christ than to men" in source
words=len(source.split())
if not 3700<=words<=4400: raise RuntimeError(f"Unexpectedly incomplete narration: {words} words")
sentences=re.split(r'(?<=[.!?;:])\s+(?=[A-Z"“(])',source)
chunks=[]
buffer=""
for sentence in sentences:
    while len(sentence)>420:
        n=sentence.rfind(" ",0,420)
        if n<160:n=420
        if buffer:chunks.append(buffer);buffer=""
        chunks.append(sentence[:n].strip())
        sentence=sentence[n:].strip()
    if len(buffer)+len(sentence)+1>420:
        if buffer:chunks.append(buffer)
        buffer=""
    buffer=(buffer+" "+sentence).strip()
if buffer:chunks.append(buffer)
if len(chunks)<40:raise RuntimeError("Suspiciously low number of chunks")
kokoro=Kokoro(str(ROOT/"kokoro-v1.0.onnx"),str(ROOT/"voices-v1.0.bin"))
SEG=OUT/"segments"
SEG.mkdir(exist_ok=True)
segments=[]
for i,chunk in enumerate(chunks,1):
    p=SEG/f"{i:05d}.wav";segments.append(p)
    if not(p.exists() and p.stat().st_size>10000):
        audio,sr=kokoro.create(chunk,voice="am_michael",speed=0.94,lang="en-us")
        audio=np.asarray(audio,dtype=np.float32)
        sf.write(p,np.concatenate([audio,np.zeros(int(sr*.30),dtype=np.float32)]),sr)
    if i%10==0 or i==len(chunks):print(f"Rendered {i}/{len(chunks)} chunks",flush=True)
listing=OUT/"concat.txt"
listing.write_text("".join("file '"+str(p.resolve())+"'\n" for p in segments))
final=OUT/"Zwingli_1524_Grace_Through_Christ_FULL_REVIEW.mp3"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),"-c:a","libmp3lame","-b:a","128k",str(final)],check=True)
duration=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(final)],text=True).strip())
report={"work":"A Remonstrance to Fridolin Lindauer","author":"Huldrych Zwingli","date":"1524-10-20","words":words,"chunks":len(chunks),"duration_seconds":duration,"mp3_bytes":final.stat().st_size,"voice":"am_michael","source":"https://doi.org/10.3931/e-rara-69367","quality":"DRAFT TRANSLATION / AUDIO FOR USER REVIEW; DO NOT PUBLISH"}
(OUT/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf8")
(OUT/"narration_source.txt").write_text(source,encoding="utf8")
if duration<950 or duration>4000:raise RuntimeError(f"Unexpected audiobook duration: {duration:.0f} s")
print("COMPLETED:",json.dumps(report),flush=True)
