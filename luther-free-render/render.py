#!/usr/bin/env python3
"""Free Kokoro-82M offline neural narration for Luther's 1545 preface."""
from pathlib import Path
import re, json, os, subprocess, time, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE=Path(__file__).resolve().parent
OUT=BASE/"output"
OUT.mkdir(exist_ok=True)
SRC=BASE/"luther-preface-1545.txt"
raw=SRC.read_text(encoding="utf-8")
assert "Martin Luther sends greetings" in raw and "5 March 1545" in raw and len(raw)>18000
paragraphs=[p.strip().replace("\n"," ") for p in raw.split("\n\n") if p.strip()]
assert len(paragraphs)>=30

def cut_long(s,limit=250):
    while len(s)>limit:
        part=s[:limit+1]
        candidates=[part.rfind(x,120,limit) for x in ["; ",", ",": "," "]]
        k=max(candidates)
        if k<120: k=part.rfind(" ", 0, limit)
        if k<1: k=limit
        # Include punctuation on the left; remove spaces at seam.
        yield s[:k+1].strip()
        s=s[k+1:].strip()
    if s: yield s

def segments(p):
    sentences=re.split(r"(?<=[.!?])\s+(?=[A-Z\'\"“‘0-9])", p)
    bits=[]
    for s in sentences: bits.extend(cut_long(s.strip()))
    cur=""
    for bit in bits:
        if len(cur)+len(bit)+1>260 and cur:
            yield cur; cur=""
        cur=(cur+" "+bit).strip()
    if cur: yield cur

model=Kokoro(str(BASE/"kokoro-v1.0.onnx"), str(BASE/"voices-v1.0.bin"))
voice=os.environ.get("LUTHER_VOICE","am_michael")
speed=float(os.environ.get("LUTHER_SPEED","0.94"))
outwav=OUT/"Martin_Luther_1545_Kokoro_Natural_Voice.wav"
# Kokoro v1.0 outputs 24kHz waveform.
sample_rate=24000
sentence_pause=0.20
paragraph_pause=0.50
count=0
start=time.time()
with sf.SoundFile(str(outwav), mode="w", samplerate=sample_rate, channels=1, subtype="PCM_16") as f:
    for p_idx,p in enumerate(paragraphs,1):
        parts=list(segments(p))
        for c_idx,chunk in enumerate(parts,1):
            print(f"Paragraph {p_idx}/{len(paragraphs)} segment {c_idx}/{len(parts)}: {len(chunk)} chars",flush=True)
            audio,sr=model.create(chunk,voice=voice,speed=speed,lang="en-us")
            if sr!=sample_rate:
                raise RuntimeError(f"Unexpected sample rate {sr} for {chunk[:50]}")
            audio=np.asarray(audio,dtype=np.float32)
            if audio.ndim!=1: audio=audio.reshape(-1)
            if len(audio)<8000: raise RuntimeError("Unexpectedly short generated speech")
            f.write(audio)
            count+=1
            gap=paragraph_pause if c_idx==len(parts) else sentence_pause
            f.write(np.zeros(int(gap*sample_rate),dtype=np.float32))
print("Generated", count, "speech segments over",len(paragraphs),"paragraphs in",round(time.time()-start,1),"seconds",flush=True)
subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error","-i",str(outwav),"-codec:a","libmp3lame","-b:a","192k",str(OUT/"Martin_Luther_1545_Natural_Voice_Full.mp3")],check=True)
mp3=OUT/"Martin_Luther_1545_Natural_Voice_Full.mp3"
probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration,size","-of","json",str(mp3)],text=True))
duration=float(probe["format"]["duration"])
print("Full narration seconds:",duration,flush=True)
if duration<780: raise RuntimeError("Audio too short for complete 3,355-word preface")
image=BASE/"cover.png"
if not image.is_file() or image.stat().st_size<20000: raise RuntimeError("Missing cover image")
video=OUT/"Martin_Luther_Preface_1545_Natural_Voice_YouTube.mp4"
subprocess.run(["ffmpeg","-nostdin","-y","-hide_banner","-loglevel","error","-loop","1","-framerate","1","-i",str(image),"-i",str(mp3),
                "-vf","fps=24,scale=1280:720:flags=lanczos","-c:v","libx264","-preset","veryfast","-tune","stillimage",
                "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(video)],check=True)
vprobe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(video)],text=True))
video_duration=float(vprobe["format"]["duration"])
streams=[s["codec_type"] for s in vprobe["streams"]]
if abs(video_duration-duration)>3 or "audio" not in streams or "video" not in streams: raise RuntimeError("Incomplete MP4 or missing stream")
# Decode through FFmpeg to ensure no truncation/corruption.
subprocess.run(["ffmpeg","-v","error","-i",str(video),"-f","null","-"],check=True)
manifest={"text_characters":len(raw),"text_words":len(raw.split()),"paragraphs":len(paragraphs),
          "speech_segments":count,"voice":voice,"model":"Kokoro-82M (Apache-2.0)",
          "audio_seconds":duration,"video_seconds":video_duration,
          "audio_bytes":mp3.stat().st_size,"video_bytes":video.stat().st_size,
          "has_audio_and_video":True,"validation":"ffprobe and ffmpeg full decode passed"}
(OUT/"validation.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps(manifest,indent=2),flush=True)
