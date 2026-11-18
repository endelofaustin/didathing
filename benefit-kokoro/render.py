#!/usr/bin/env python3
"""Complete free Kokoro-82M/ONNX narration of the 1543 Benefit of Christ's Death."""
from pathlib import Path
import hashlib, json, os, re, subprocess, time
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
SRC = BASE / "benefit_of_christs_death_audiobook_script.txt"
raw = SRC.read_text(encoding="utf-8").strip()
expected_chapters = [f"Chapter {i} " for i in range(1, 7)]
actual_chapters = re.findall(r"(?m)^Chapter ([1-6]) [—–-] ", raw)
assert actual_chapters == ["1", "2", "3", "4", "5", "6"], f"Missing or repeated chapters: {actual_chapters}"
assert len(raw) >= 105000 and len(raw.split()) >= 18500
assert raw.startswith("The Benefit of Christ") and raw.endswith("Amen.")
source_sha256 = hashlib.sha256(SRC.read_bytes()).hexdigest()
print(f"Manuscript: {len(raw)} characters, {len(raw.split())} words, source SHA {source_sha256}", flush=True)

# The first section includes the title and historical address to readers.
chapters = re.split(r"(?=^Chapter [1-6] [—–-] )", raw, flags=re.MULTILINE)
assert len(chapters) == 7, f"Expected introduction and six chapters; got {len(chapters)}"
chapter_titles = ["Introduction and To Christian Readers"]
for i, section in enumerate(chapters[1:], 1):
    chapter_titles.append(section.splitlines()[0].strip())
    assert section.startswith(f"Chapter {i} "), f"Wrong chapter order: {i}"
assert sum(len(s.split()) for s in chapters) == len(raw.split()), "Script integrity error"
print("Chapters: " + ", ".join(chapter_titles), flush=True)

def chunk_paragraph(paragraph, limit=245):
    # Preserve all words and punctuation, splitting primarily on sentence boundaries.
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“‘\'])', paragraph)
    pieces = []
    for sent in sentences:
        sent = sent.strip()
        while len(sent) > limit:
            candidates = [sent.rfind(c, 95, limit) for c in ("; ", ", ", ": ", " ")]
            k = max(candidates)
            if k < 80:
                k = sent.rfind(" ", 0, limit)
            if k < 1:
                raise RuntimeError("A single token exceeds Kokoro segment limit")
            pieces.append(sent[:k+1].strip())
            sent = sent[k+1:].strip()
        if sent:
            pieces.append(sent)
    out, current = [], ""
    for piece in pieces:
        if len(current) + len(piece) + 1 > limit and current:
            out.append(current)
            current = ""
        current = (current + " " + piece).strip()
    if current:
        out.append(current)
    assert all(0 < len(c) <= limit for c in out)
    # A whitespace-only normalization must match, proving no content lost in chunking.
    assert " ".join(" ".join(out).split()) == " ".join(paragraph.split()), "Chunking lost or altered source text"
    return out

model = Kokoro(str(BASE / "kokoro-v1.0.onnx"), str(BASE / "voices-v1.0.bin"))
voice = os.environ.get("BENEFIT_VOICE", "am_michael")
speed = float(os.environ.get("BENEFIT_SPEED", "0.94"))
sr_expected = 24000
segment_count = 0
chap_meta = []
start = time.monotonic()

for chapter_idx, section in enumerate(chapters):
    paragraphs = [p.replace("\n", " ").strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
    assert paragraphs, f"Chapter {chapter_idx} has no content"
    chapter_file = OUT / f"chapter_{chapter_idx:02d}.mp3"
    wav_file = OUT / f"chapter_{chapter_idx:02d}.wav"
    count = 0
    print(f"START {chapter_idx}/{len(chapters)-1}: {chapter_titles[chapter_idx]}, {len(section.split())} words", flush=True)
    with sf.SoundFile(str(wav_file), "w", samplerate=sr_expected, channels=1, subtype="PCM_16") as wav:
        for pi, paragraph in enumerate(paragraphs, 1):
            chunks = chunk_paragraph(paragraph)
            for si, chunk in enumerate(chunks):
                print(f"  Chapter {chapter_idx}; paragraph {pi}/{len(paragraphs)}; segment {si+1}/{len(chunks)}; chars={len(chunk)}", flush=True)
                audio, sr = model.create(chunk, voice=voice, speed=speed, lang="en-us")
                if sr != sr_expected:
                    raise RuntimeError(f"Unexpected Kokoro sample rate {sr}")
                audio = np.asarray(audio, dtype=np.float32).reshape(-1)
                if len(audio) < 2400 or not np.all(np.isfinite(audio)):
                    raise RuntimeError(f"Invalid speech for chapter {chapter_idx}, paragraph {pi}, segment {si}")
                wav.write(audio)
                count += 1
                segment_count += 1
                pause = 0.40 if si == len(chunks)-1 else 0.18
                wav.write(np.zeros(int(pause * sr), dtype=np.float32))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(wav_file), "-ac", "1", "-ar", "24000",
                    "-codec:a", "libmp3lame", "-b:a", "96k", str(chapter_file)], check=True)
    wav_file.unlink()
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                   "format=duration,size", "-of", "json", str(chapter_file)], text=True))
    seconds = float(probe["format"]["duration"])
    words = len(section.split())
    if seconds < words / 230 * 60:
        raise RuntimeError(f"Chapter {chapter_idx} suspiciously short: {seconds:.1f}s for {words} words")
    entry = {"chapter":chapter_idx,"title":chapter_titles[chapter_idx],"words":words,
             "paragraphs":len(paragraphs),"segments":count,"seconds":round(seconds,2),
             "bytes":chapter_file.stat().st_size}
    chap_meta.append(entry)
    print("FINISH CHAPTER: "+json.dumps(entry), flush=True)

# FFmpeg joins the complete chapters in order, without re-encoding.
concat_list = OUT / "chapters.txt"
concat_list.write_text("\n".join(f"file 'chapter_{i:02d}.mp3'" for i in range(7))+"\n")
mp3 = OUT / "The_Benefit_of_Christs_Death_COMPLETE_Kokoro_Michael.mp3"
subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error","-f","concat",
                "-safe","0","-i",str(concat_list),"-c:a","copy",str(mp3)],check=True)
probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
               "format=duration,size", "-of", "json", str(mp3)], text=True))
duration = float(probe["format"]["duration"])
summed = sum(c["seconds"] for c in chap_meta)
if abs(duration-summed)>10 or duration<5100 or duration>16000:
    raise RuntimeError(f"Combined audio duration invalid {duration:.1f}, sum {summed:.1f}")
if mp3.stat().st_size<55_000_000:
    raise RuntimeError(f"Combined MP3 suspiciously small {mp3.stat().st_size} bytes")
# Full-stream decode guarantees MP3 structure is complete.
subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(mp3),"-f","null","-"],check=True)
time_cursor = 0.
for entry in chap_meta:
    entry["start_seconds"] = round(time_cursor,2)
    time_cursor += entry["seconds"]
manifest = {"source_sha256":source_sha256, "script_characters":len(raw),"script_words":len(raw.split()),
            "all_six_chapters_verified":True, "text_end_checked":raw.endswith("Amen."),
            "voice":voice,"speed":speed,"engine":"Kokoro-82M ONNX (free/open source)",
            "speech_segments":segment_count,"chapters":chap_meta,
            "complete_mp3_seconds":round(duration,2),"complete_mp3_bytes":mp3.stat().st_size,
            "mp3_decoded_without_errors":True,"processing_seconds":round(time.monotonic()-start,1)}
(OUT/"validation.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("COMPLETE AUDIOBOOK VALIDATED:\n"+json.dumps(manifest,indent=2),flush=True)
