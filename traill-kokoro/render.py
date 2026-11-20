#!/usr/bin/env python3
"""Produce review copy of public-domain Robert Traill from historic OCR with Kokoro ONNX."""
import json, re, subprocess, urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
url = "https://www.digitalpuritan.net/Digital%20Puritan%20Resources/Traill,%20Robert/Select%20Practical%20Writings.txt.html"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (audiobook research; public domain transcription)"})
with urllib.request.urlopen(req, timeout=120) as resp:
    html = resp.read().decode("utf-8", "replace")
soup = BeautifulSoup(html, "html.parser")
for tag in soup(["script", "style", "nav", "footer", "header"]): tag.decompose()
pre = soup.find("pre")
raw = pre.get_text("\n") if pre else soup.get_text("\n")
raw = raw.replace("\r", "")
# The 1845 selected-writings edition contains an index mention and then the actual title.
matches = list(re.finditer(r"A\s+VINDICATION\s+OF\s+THE\s+PROTESTANT\s+DOCTRINE", raw, re.I))
if not matches: raise RuntimeError("Original work heading not found; refusing partial audiobook.")
start = matches[-1].start()
ends = list(re.finditer(r"London\s*,?\s*Sept\.?\s*1\.?\s*1691", raw[start:], re.I))
if not ends: raise RuntimeError("Original work's 1691 closing date missing; refusing incomplete audiobook.")
end = start + ends[0].end()
source = raw[start:end]
# Historic scan OCR: reconstruct end-of-line hyphenation and strip obvious scanned page headers.
source = re.sub(r"(?<=\w)-\s*\n\s*(?=[a-z])", "", source)
source = re.sub(r"\n\s*(?:\d{1,3}\s+)?(?:JUSTIFICATION VINDICATED FROM|THE CHARGE OF ANTINOMIANISM\.)\s*\d{0,3}\s*\n", "\n", source, flags=re.I)
source = re.sub(r"(?m)^\s*\d{2,3}\s*$", "", source)
source = re.sub(r"\s+", " ", source).strip()
words = len(source.split())
(OUT / "historical_ocr_source.txt").write_text(source, encoding="utf-8")
print("Extracted historical text words:", words, "first:", source[:170], "last:", source[-180:], flush=True)
if not 8500 <= words <= 26000: raise RuntimeError(f"Suspicious text length: {words}; refuse incomplete or extra works")
# Text is an unproofread historical OCR review copy, not a publication master.
intro = ("Robert Traill. A Vindication of the Protestant Doctrine Concerning Justification, "
         "and of Its Preachers and Professors, from the Unjust Charge of Antinomianism. "
         "First published in 1692. Historical edition, provisional narration for review. ")
text = intro + source
sentences = re.split(r"(?<=[.!?;:])\s+(?=[A-Z\"'(])", text)
chunks, chunk = [], ""
for s in sentences:
    while len(s) > 430:
        point = s.rfind(" ", 0, 430)
        if point < 150: point = 430
        first, s = s[:point].strip(), s[point:].strip()
        if chunk: chunks.append(chunk); chunk = ""
        chunks.append(first)
    if len(chunk) + len(s) + 1 > 430:
        if chunk: chunks.append(chunk)
        chunk = ""
    chunk = (chunk + " " + s).strip()
if chunk: chunks.append(chunk)
if not chunks: raise RuntimeError("No text chunks")
kokoro = Kokoro(str(ROOT/"kokoro-v1.0.onnx"), str(ROOT/"voices-v1.0.bin"))
SEG = OUT/"segments"
SEG.mkdir(exist_ok=True)
paths = []
for i, chunk in enumerate(chunks, 1):
    path = SEG/f"{i:05d}.wav"
    paths.append(path)
    if not (path.exists() and path.stat().st_size > 5000):
        audio, sr = kokoro.create(chunk, voice="am_michael", speed=0.94, lang="en-us")
        audio = np.asarray(audio, dtype=np.float32)
        sf.write(path, np.concatenate([audio, np.zeros(int(sr*.30), dtype=np.float32)]), sr)
    if i%20 == 0 or i == len(chunks): print(f"Rendered {i}/{len(chunks)}", flush=True)
listing = OUT/"concat.txt"
listing.write_text("".join("file '"+str(p.resolve())+"'\n" for p in paths), encoding="utf-8")
final = OUT/"Robert_Traill_Justification_Vindicated_REVIEW.mp3"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),"-c:a","libmp3lame","-b:a","128k",str(final)],check=True)
duration = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(final)],text=True).strip())
report = {"work":"Justification Vindicated","author":"Robert Traill","words":words,"chunks":len(chunks),"duration_seconds":duration,"mp3_bytes":final.stat().st_size,"voice":"am_michael","source_url":url,"quality":"UNPROOFREAD OCR; review required; not ready for publishing"}
(OUT/"validation.json").write_text(json.dumps(report,indent=2))
if duration < 3600: raise RuntimeError("Suspiciously short audiobook")
print("Completed provisional audiobook",json.dumps(report),flush=True)
