# QuantCheck demo video

This directory contains editable production inputs for an optional portfolio
cut. The generated MP4 is not committed to the public source tree; release
assets are described in [the archive manifest](../docs/ARTIFACT_ARCHIVE.md).

Files:

- `captions.vtt` — scene-level captions for embedding or replacement.
- `narration.txt` — exact spoken narration.
- `PRODUCTION_PACKAGE.md` — timestamped shot list, onscreen text, visual assets,
  recording checklist, retake checklist, shortened cut, and portfolio copy.
- `build_demo.py` — reproducible local builder using the repository assets,
  macOS Quick Look, `say`, and AVFoundation.

Regenerate locally with:

```text
python3 video/build_demo.py
```

The video deliberately avoids installation walkthroughs, source scrolling, and
terminal footage. Benchmark metrics are labelled as saved fixture evidence;
the SEC study is labelled as narrow pipeline exposure rather than broad natural-
data detector validation.
