"""Generate character voices with Kokoro (free, offline) and a timeline for Blender."""
import json, sys, os
import numpy as np
import soundfile as sf
from kokoro import KPipeline

FPS = 24
SR = 24000
story = json.load(open(sys.argv[1]))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)

pipe = KPipeline(lang_code="a")
LEAD, GAP, TAIL = 0.6, 0.35, 1.2
t = LEAD
mix = [np.zeros(int(LEAD * SR), dtype=np.float32)]
timeline = {"fps": FPS, "lines": []}

for i, line in enumerate(story["lines"]):
    voice = story["characters"][line["who"]]["voice"]
    chunks = [a.numpy() if hasattr(a, "numpy") else np.asarray(a) for _, _, a in pipe(line["text"], voice=voice, speed=0.95)]
    audio = np.concatenate(chunks).astype(np.float32)
    sf.write(f"{out}/line{i:02d}.wav", audio, SR)
    dur = len(audio) / SR
    spf = SR // FPS
    env = [float(np.sqrt(np.mean(audio[k:k + spf] ** 2))) for k in range(0, len(audio), spf)]
    peak = max(env) or 1.0
    env = [min(1.0, e / (peak * 0.7)) for e in env]
    timeline["lines"].append({**line, "start": t, "end": t + dur, "env": env})
    mix.append(audio)
    gap = GAP + (0.5 if i + 1 < len(story["lines"]) and story["lines"][i + 1]["who"] == "narrator" else 0)
    mix.append(np.zeros(int(gap * SR), dtype=np.float32))
    t += dur + gap

mix.append(np.zeros(int(TAIL * SR), dtype=np.float32))
full = np.concatenate(mix)
sf.write(f"{out}/dialogue.wav", full, SR)
timeline["duration"] = len(full) / SR
timeline["frames"] = int(timeline["duration"] * FPS) + 1
json.dump(timeline, open(f"{out}/timeline.json", "w"), indent=1)
print("duration", timeline["duration"], "frames", timeline["frames"])
