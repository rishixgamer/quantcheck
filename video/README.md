# QuantCheck demo video

This directory contains the finished portfolio cut and its editable production
inputs. The current render is a 1920×1080 MP4, 175.97 seconds (2:56), with a
neutral macOS Samantha voice, burned-in slide text, and a matching VTT caption
track.

Files:

- `QuantCheck_demo.mp4` — finished narrated video.
- `captions.vtt` — scene-level captions for embedding or replacement.
- `narration.txt` — exact spoken narration.
- `PRODUCTION_PACKAGE.md` — timestamped shot list, onscreen text, visual assets,
  recording checklist, retake checklist, shortened cut, and portfolio copy.
- `build_demo.py` — reproducible local builder using the repository assets,
  macOS Quick Look, `say`, and AVFoundation.

Regenerate with:

```text
python3 video/build_demo.py
```

The video deliberately avoids installation walkthroughs, source scrolling, and
terminal footage. Benchmark metrics are labelled as saved fixture evidence;
the SEC study is labelled as narrow pipeline exposure rather than broad natural-
data detector validation.
