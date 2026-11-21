#!/usr/bin/env python3
"""John Owen (1677), complete 20-chapter Kokoro ONNX audiobook renderer.

Eight parts, each made from a non-overlapping range of contiguous speech chunks.
Source: public-domain original work transcribed by CCEL. This pipeline does not
redistribute CCEL's separately licensed PDF or their modern cover/layout.
"""
import json, os, re, subprocess, urllib.request
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)
PART = int(os.environ.get("OWEN_PART", "1"))
TOTAL = 8
assert 1 <= PART <= TOTAL
SOURCE_URL = "https://www.ccel.org/ccel/o/owen/just/cache/just.txt"
req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0 (public-domain audiobook historical research)"})
with urllib.request.urlopen(req, timeout=180) as r:
    raw = r.read().decode("utf-8", "replace").replace("\r", "")

start = re.search(r"(?m)^[ \t]*To the reader[ \t]*$", raw)
end = re.search(r"(?m)^[ \t]*Indexes[ \t]*$", raw)
if not start or not end or end.start() < start.end():
    raise RuntimeError("Cannot prove complete-text boundaries: refusing partial audiobook")
raw_book = raw[start.start():end.start()]
for roman in ("I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX"):
    if not re.search(r"(?m)^\s*(?:Chapter\s+)?" + roman + r"\.\s", raw_book):
        raise RuntimeError("A chapter heading is absent: " + roman)
# Reflow CCEL's hard-wrapped text. Remove typographical horizontal rules and isolated blank lines.
lines = [line.strip() for line in raw_book.splitlines()
         if line.strip() and not re.fullmatch(r"[_\-= ]{8,}", line.strip())]
body = re.sub(r"\s+", " ", " ".join(lines)).strip()
words = len(body.split())
if not 90000 < words < 350000:
    raise RuntimeError("Unexpected complete-book word count " + str(words))
print("Complete Owen original: words=", words, "chars=", len(body),flush=True)

def chunk_text(t, limit=405):
    sentences = re.split(r'(?<=[.!?;:])\s+(?=[A-Z0-9"“‘(])', t)
    chunks, buf = [], ""
    for sentence in sentences:
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            if cut < 150:
                cut = limit
            first, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(first)
        if len(buf) + len(sentence) + 1 > limit:
            if buf:
                chunks.append(buf)
            buf = ""
        buf = (buf + " " + sentence).strip()
    if buf:
        chunks.append(buf)
    return chunks

all_chunks = chunk_text(body)
all_len = sum(len(c.split()) for c in all_chunks)
if all_len != words:
    raise RuntimeError("Source lost words in speech chunking")
bounds = [(len(all_chunks)*i//TOTAL, len(all_chunks)*(i+1)//TOTAL) for i in range(TOTAL)]
s,e = bounds[PART-1]
assert e > s and bounds[0][0] == 0 and bounds[-1][1] == len(all_chunks)
assert all(bounds[i][1] == bounds[i+1][0] for i in range(TOTAL-1))
chunks = all_chunks[s:e]
part_text = " ".join(chunks)
(OUT / f"part_{PART:02d}_source.txt").write_text(part_text,encoding="utf-8")

VERSE = ("But without faith it is impossible to please him: for he that "
         "cometh to God must believe that he is, and that he is a rewarder "
         "of them that diligently seek him.")
INTRO = (
    "The Doctrine of Justification by Faith, through the Imputation of the "
    "Righteousness of Christ. By John Owen. Published in 1677. "
    "This is a historical theological treatise, narrated by an artificial voice. "
    "The text is presented for historical study and does not imply agreement "
    "with every opinion Owen held, including his positions on infant baptism "
    "and covenant theology. Saving righteousness is found only in Jesus "
    "Christ, received by grace through faith, not earned through works or "
    "conferred automatically through sacraments. "
    "Hebrews, chapter eleven, verse six. " + VERSE + " "
)
head = f"John Owen. The Doctrine of Justification by Faith. Part {PART} of {TOTAL}. "
if PART == 1:
    head = INTRO + head
speech_chunks = chunk_text(head) + chunks

def cover():
    w,h = 1280,720
    im = Image.new("RGB",(w,h),(18,26,39))
    d=ImageDraw.Draw(im)
    for y in range(h):
        tint=int(25*y/h)
        d.line((0,y,w,y),fill=(18+tint//2,27+tint//2,39+tint))
    gold=(222,178,111); cream=(252,239,217); light=(220,216,210)
    d.rectangle((27,27,w-27,h-27),outline=gold,width=3)
    d.rectangle((41,41,w-41,h-41),outline=gold,width=1)
    d.rectangle((116,150,142,545),fill=gold)
    d.rectangle((35,267,225,293),fill=gold)
    f="/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
    f2="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    big=ImageFont.truetype(f,49)
    med=ImageFont.truetype(f,26)
    small=ImageFont.truetype(f2,22)
    d.text((265,120),"THE DOCTRINE OF",font=big,fill=cream)
    d.text((265,193),"JUSTIFICATION BY FAITH",font=big,fill=cream)
    d.line((265,273,1180,273),fill=gold,width=3)
    d.text((265,303),"JOHN OWEN  |  COMPLETE AUDIOBOOK",font=small,fill=gold)
    d.text((265,348),f"PART {PART} OF {TOTAL}  •  KOKORO / MICHAEL",font=small,fill=light)
    d.text((265,414),"But without faith it is impossible to please him:",font=med,fill=cream)
    d.text((265,451),"for he that cometh to God must believe that he is,",font=med,fill=cream)
    d.text((265,488),"and that he is a rewarder of them that diligently",font=med,fill=cream)
    d.text((265,525),"seek him.",font=med,fill=cream)
    d.text((265,579),"HEBREWS 11:6 • KING JAMES VERSION",font=small,fill=gold)
    path=OUT/f"John_Owen_Part_{PART:02d}_cover.png"
    im.save(path)
    return path

cover_path=cover()
print("Synthesizing",len(speech_chunks),"chunks, source chunk range",s,e,flush=True)
kokoro = Kokoro(str(ROOT/"kokoro-v1.0.onnx"), str(ROOT/"voices-v1.0.bin"))
seg_dir=OUT/"segments"
seg_dir.mkdir(exist_ok=True)
paths=[]
for i,part in enumerate(speech_chunks,1):
    p=seg_dir/f"{i:05d}.wav"
    audio,sr=kokoro.create(part,voice="am_michael",speed=0.94,lang="en-us")
    data=np.asarray(audio,dtype=np.float32)
    if len(data)<1000:
        raise RuntimeError(f"Speech segment {i} is unexpectedly short")
    sf.write(p,np.concatenate([data,np.zeros(int(sr*0.30),dtype=np.float32)]),sr)
    paths.append(p)
    if i%25==0 or i==len(speech_chunks):
        print(f"Part {PART}/{TOTAL}: {i}/{len(speech_chunks)} segments",flush=True)

listing=OUT/"concat.txt"
listing.write_text("".join("file '"+str(p.resolve())+"'\n" for p in paths),encoding="utf-8")
base=f"John_Owen_Justification_Part_{PART:02d}_of_{TOTAL:02d}"
mp3=OUT/(base+".mp3")
subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(listing),"-c:a","libmp3lame","-b:a","96k",str(mp3)],check=True)
mp4=OUT/(base+".mp4")
subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error",
    "-loop","1","-framerate","2","-i",str(cover_path),"-i",str(mp3),
    "-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","ultrafast",
    "-tune","stillimage","-crf","32","-r","2","-pix_fmt","yuv420p",
    "-c:a","aac","-b:a","80k","-ar","44100","-ac","1",
    "-shortest","-movflags","+faststart",str(mp4)],check=True)
def duration(p):
    return float(subprocess.check_output(["ffprobe","-v","error",
      "-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)],text=True).strip())
mp3dur, mp4dur=duration(mp3),duration(mp4)
if not 1800<mp3dur<43000 or abs(mp3dur-mp4dur)>8:
    raise RuntimeError(f"Truncation or YouTube 12h limit risk: {mp3dur=}, {mp4dur=}")
if mp4.stat().st_size>295_000_000:
    raise RuntimeError("Video larger than vidIQ 299MB import limit: "+str(mp4.stat().st_size))
report={"title":"The Doctrine of Justification by Faith","author":"John Owen","part":PART,
    "total_parts":TOTAL,"source_url":SOURCE_URL,"source_word_count":words,
    "source_chunk_total":len(all_chunks),"part_chunk_start":s,"part_chunk_end":e,
    "part_words":len(part_text.split()),"synthetic_voice":"am_michael","speech_speed":0.94,
    "mp3_seconds":mp3dur,"mp4_seconds":mp4dur,"mp4_bytes":mp4.stat().st_size,
    "status":"AUTOMATED RENDER FOR REVIEW — requires listening and text verification before publishing"}
(OUT/(base+"_validation.json")).write_text(json.dumps(report,indent=2),encoding="utf-8")
print("DONE",json.dumps(report),flush=True)
