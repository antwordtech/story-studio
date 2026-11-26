"""Subtitles (ASS) + FFmpeg assembly into a vertical Short."""
import json, sys, subprocess

story = json.load(open(sys.argv[1]))
tl = json.load(open(sys.argv[2]))
frames, audio, out = sys.argv[3], sys.argv[4], sys.argv[5]


def ts(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


ass = ["[Script Info]", "PlayResX: 1080", "PlayResY: 1920", "",
       "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
       "Style: D,DejaVu Sans,62,&H00FFFFFF,&H00000000,&H80000000,1,5,2,2,70,70,330",
       "Style: T,DejaVu Sans,78,&H0000D7FF,&H00000000,&H80000000,1,6,3,8,60,60,140",
       "", "[Events]", "Format: Layer, Start, End, Style, Text"]
ass.append(f"Dialogue: 0,{ts(0)},{ts(2.6)},T,{story['title'].upper()}")
for ln in tl["lines"]:
    ch = story["characters"][ln["who"]]
    name = f"{{\\c{ch['color']}}}{ch['name']}{{\\c&H00FFFFFF}}\\N" if ch["name"] else f"{{\\c{ch['color']}}}"
    ass.append(f"Dialogue: 0,{ts(ln['start'])},{ts(ln['end'] + 0.2)},D,{name}{ln['text']}")
open("subs.ass", "w").write("\n".join(ass) + "\n")

subprocess.run(["ffmpeg", "-y", "-framerate", str(tl["fps"]), "-i", f"{frames}/%05d.png", "-i", audio,
                "-vf", "scale=1080:1920:flags=lanczos,ass=subs.ass", "-c:v", "libx264", "-preset", "slow",
                "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", out], check=True)
