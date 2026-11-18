#!/usr/bin/env python3
"""Narrate the complete 1535 Luther Galatians preface + marked 1538 addition.
Runs Kokoro ONNX locally on a free GitHub Actions runner; no paid voice APIs.
"""
from pathlib import Path
import re, json, os, subprocess, time
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
SRC = BASE / "galatians-preface-1535-1538.txt"
raw = SRC.read_text(encoding="utf-8").strip()
assert len(raw) > 12000, "Script was unexpectedly truncated"
assert "I can scarcely believe" in raw and "Addition to the Preface, from the revised edition of 1538." in raw
assert raw.endswith("who is blessed forever. Amen."), "Closing text is missing"
paragraphs = [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n", raw) if p.strip()]
assert len(paragraphs) > 20
print(f"Narrating {len(raw)} characters, {len(raw.split())} words, {len(paragraphs)} paragraphs", flush=True)

def cut_long(s, limit=245):
    while len(s) > limit:
        part = s[:limit + 1]
        candidates = [part.rfind(x, 100, limit) for x in ["; ", ", ", ": ", " "]]
        k = max(candidates)
        if k < 90:
            k = part.rfind(" ", 0, limit)
        if k < 1:
            k = limit
        yield s[:k+1].strip()
        s = s[k+1:].strip()
    if s:
        yield s

def segments(paragraph):
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\'\"“‘0-9])", paragraph)
    bits = []
    for sent in sentences:
        bits.extend(cut_long(sent.strip()))
    cur = ""
    for bit in bits:
        if len(cur) + len(bit) + 1 > 255 and cur:
            yield cur
            cur = ""
        cur = (cur + " " + bit).strip()
    if cur:
        yield cur

model = Kokoro(str(BASE / "kokoro-v1.0.onnx"), str(BASE / "voices-v1.0.bin"))
voice = os.environ.get("LUTHER_VOICE", "am_michael")
speed = float(os.environ.get("LUTHER_SPEED", "0.94"))
sample_rate = 24000
wav = OUT / "Martin_Luther_Galatians_Kokoro_Full.wav"
mp3 = OUT / "Martin_Luther_Galatians_Complete_Natural_Voice.mp3"
count = 0
start = time.monotonic()
with sf.SoundFile(str(wav), "w", samplerate=sample_rate, channels=1, subtype="PCM_16") as file:
    for pidx, paragraph in enumerate(paragraphs, 1):
        pieces = list(segments(paragraph))
        for sidx, piece in enumerate(pieces, 1):
            print(f"Paragraph {pidx}/{len(paragraphs)}, segment {sidx}/{len(pieces)}", flush=True)
            audio, sr = model.create(piece, voice=voice, speed=speed, lang="en-us")
            if sr != sample_rate:
                raise RuntimeError(f"Unexpected sample rate: {sr}")
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            if len(audio) < 5000:
                raise RuntimeError(f"Unexpectedly short speech at paragraph {pidx}, part {sidx}")
            file.write(audio)
            file.write(np.zeros(int((0.42 if sidx == len(pieces) else 0.15) * sr), dtype=np.float32))
            count += 1
print(f"Rendered {count} segments in {time.monotonic()-start:.1f} seconds", flush=True)
subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(wav),
    "-codec:a", "libmp3lame", "-b:a", "160k", str(mp3)], check=True)
probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(mp3)], text=True))
duration = float(probe["format"]["duration"])
if duration < 600 or duration > 2200:
    raise RuntimeError(f"Unexpected duration {duration:.1f}s for {len(raw.split())} words")
if mp3.stat().st_size < 9_000_000:
    raise RuntimeError(f"Unexpectedly small MP3 file: {mp3.stat().st_size} bytes")
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(mp3), "-f", "null", "-"], check=True)
metadata = dict(text_characters=len(raw), text_words=len(raw.split()), paragraphs=len(paragraphs),
    speech_segments=count, voice=voice, model="Kokoro-82M ONNX, offline, open-source",
    audio_seconds=round(duration, 2), audio_megabytes=round(mp3.stat().st_size/1_000_000,2),
    full_text_start_checked=True, full_text_end_checked=True, audio_decode_verified=True)
(OUT / "validation.json").write_text(json.dumps(metadata, indent=2))
print(json.dumps(metadata, indent=2), flush=True)
