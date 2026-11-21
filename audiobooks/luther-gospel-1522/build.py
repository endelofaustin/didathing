#!/usr/bin/env python3
"""Kokoro narration of an independent modern-English translation of Luther's 1522 tract."""
import hashlib, json, re, subprocess, textwrap
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro import KPipeline

root = Path(__file__).resolve().parent
out = root / "output"
parts = out / "segments"
parts.mkdir(parents=True, exist_ok=True)
body = (root / "narration.txt").read_text(encoding="utf-8").strip()
assert body.startswith("What to Look for and Expect in the Gospels.")
assert body.endswith("Amen.")
paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
assert len(paragraphs) > 25, "Truncated translation"
pipeline = KPipeline(lang_code="a")
voice = "am_michael"
rate = 24000
files = []
def append(wav):
    p = parts / f"segment_{len(files):05d}.wav"
    sf.write(p, np.asarray(wav, dtype=np.float32), rate, subtype="PCM_16")
    files.append(p)
for i, para in enumerate(paragraphs, 1):
    print(f"Rendering paragraph {i}/{len(paragraphs)}", flush=True)
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", para):
        for chunk in textwrap.wrap(sentence, width=300, break_long_words=False, break_on_hyphens=False):
            if not chunk.strip(): continue
            n = 0
            for _, _, audio in pipeline(chunk, voice=voice, speed=1.0, split_pattern=r"\n+"):
                if audio is None or len(audio) < 1000: raise RuntimeError("Bad audio chunk: " + chunk[:80])
                append(audio)
                n += 1
            if n == 0: raise RuntimeError("Missing audio: " + chunk[:80])
            append(np.zeros(int(rate * .23), dtype=np.float32))
    append(np.zeros(int(rate * .30), dtype=np.float32))
assert len(files) >= 50
listing = out / "concat.txt"
listing.write_text("".join(f"file '{p.resolve()}'\n" for p in files))
mp3 = out / "luther_1522_gospel_kokoro_michael_full.mp3"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),"-ac","1","-ar","24000","-c:a","libmp3lame","-b:a","96k",str(mp3)],check=True)
result = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(mp3)],check=True,capture_output=True,text=True)
seconds=float(result.stdout.strip())
if seconds < 600: raise RuntimeError(f"Audio too short: {seconds}s")
manifest={"title":"What to Look for and Expect in the Gospels (1522)","author":"Martin Luther","translator":"New independent modern-English translation from the historical German","source":"https://www.glaubensstimme.de/doku.php?id=autoren:l:luther:e:ein_klein_unterricht","voice":voice,"engine":"Kokoro","word_count":len(body.split()),"paragraphs":len(paragraphs),"duration_seconds":seconds,"sha256_text":hashlib.sha256(body.encode()).hexdigest(),"sha256_mp3":hashlib.sha256(mp3.read_bytes()).hexdigest()}
(out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
(out/"narration.txt").write_text(body+"\n",encoding="utf-8")
print(json.dumps(manifest,indent=2))
