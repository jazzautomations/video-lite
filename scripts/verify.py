#!/usr/bin/env python3
"""Check a rendered MP4 and write a contact sheet: verify.py video.mp4 [--require-audio]."""
import argparse
import json
import os
import shutil
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("--require-audio", action="store_true")
    a = ap.parse_args()
    probe = shutil.which("ffprobe")
    if not probe:
        sys.exit("verify: falta o ffprobe")
    if not os.path.exists(a.video) or os.path.getsize(a.video) < 10000:
        sys.exit("FALHOU: %s não existe ou está vazio" % a.video)
    r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
                        "-of", "json", a.video], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("FALHOU: ffprobe não leu o arquivo: " + r.stderr.strip()[:300])
    info = json.loads(r.stdout)
    dur = float(info.get("format", {}).get("duration", 0))
    v = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    au = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    problems = []
    if not v:
        problems.append("sem trilha de vídeo")
    if a.require_audio and not au:
        problems.append("sem trilha de áudio")
    if dur < 2:
        problems.append("duração curta demais (%.1fs)" % dur)
    sheet = os.path.splitext(a.video)[0] + "-contact.png"
    if v and dur > 0:
        ff = shutil.which("ffmpeg") or "ffmpeg"
        if os.path.exists(sheet):
            os.remove(sheet)
        # keyframes only (x264 puts them on scene cuts): no full decode, ~10x faster on old machines
        k = subprocess.run([probe, "-v", "error", "-skip_frame", "nokey", "-select_streams", "v:0", "-count_frames",
                            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", a.video], capture_output=True, text=True)
        try:
            nkey = int(k.stdout.strip().split(",")[0])
        except ValueError:
            nkey = 0
        if nkey >= 6:
            every = max(1, -(-nkey // 9))
            subprocess.run([ff, "-y", "-loglevel", "error", "-skip_frame", "nokey", "-i", a.video, "-vf",
                            "select='not(mod(n\\,%d))',scale=320:-1,tile=3x3" % every, "-fps_mode", "vfr", "-frames:v", "1", sheet],
                           capture_output=True)
        if not os.path.exists(sheet):
            step = max(0.5, dur / 9)
            subprocess.run([ff, "-y", "-loglevel", "error", "-i", a.video, "-vf",
                            "fps=1/%.3f,scale=320:-1,tile=3x3" % step, "-frames:v", "1", sheet], capture_output=True)
    desc = "%.1fs, vídeo %s %sx%s, áudio %s" % (dur, v[0].get("codec_name") if v else "-", v[0].get("width") if v else "?",
                                                  v[0].get("height") if v else "?", au[0].get("codec_name") if au else "nenhum")
    if problems:
        sys.exit("FALHOU: " + "; ".join(problems) + " (" + desc + ")")
    print("ok: " + desc)
    if os.path.exists(sheet):
        print("folha de contato: " + sheet + " (abra/leia a imagem para conferir as cenas)")


if __name__ == "__main__":
    main()
