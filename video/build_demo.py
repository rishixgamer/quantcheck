#!/usr/bin/env python3
"""Build the QuantCheck portfolio demo video on macOS.

The builder intentionally uses only repository assets, macOS Quick Look,
macOS `say`, and AVFoundation. It creates a narrated MP4, a VTT caption track,
the exact narration text, and a timestamped production manifest.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "video"
BUILD_DIR = VIDEO_DIR / "build"
ASSET_DIR = ROOT / "docs" / "assets"
WIDTH = 1920
HEIGHT = 1080


@dataclass
class Scene:
    number: int
    slug: str
    narration: str
    planned_seconds: float
    visual: str
    caption: str
    image: str = ""
    audio: str = ""
    audio_seconds: float = 0.0
    start_seconds: float = 0.0
    duration_seconds: float = 0.0


SCENES = [
    Scene(
        1,
        "hook",
        "A backtest can be mathematically correct and still be wrong if its data knew the future. QuantCheck audits the data behind quantitative research before the result is trusted.",
        12,
        "hook",
        "A backtest can be mathematically correct and still be wrong if its data knew the future. QuantCheck audits the data behind quantitative research before the result is trusted.",
    ),
    Scene(
        2,
        "point_in_time",
        "The issue is point-in-time truth. A reporting period ends March 31. The researcher decides on April 15. The actual filing arrives May 2. Those are three different dates.",
        15,
        "timeline",
        "The issue is point-in-time truth. A reporting period ends March 31. The researcher decides on April 15. The actual filing arrives May 2. Those are three different dates.",
    ),
    Scene(
        3,
        "fault",
        "If the filing is stamped as available on April 15, a future value becomes visible too early. The backtest can now use information that did not exist at the research cutoff.",
        13,
        "fault",
        "If the filing is stamped as available on April 15, a future value becomes visible too early. The backtest can now use information that did not exist at the research cutoff.",
    ),
    Scene(
        4,
        "consequence",
        "That changes the controlled research decision: an unavailable observation can enter the screen, alter a ranking, and make the historical result look better than the information set allowed.",
        14,
        "consequence",
        "That changes the controlled research decision: an unavailable observation can enter the screen, alter a ranking, and make the historical result look better than the information set allowed.",
    ),
    Scene(
        5,
        "boundary",
        "QuantCheck tests this by injecting a controlled fault, then passing only a sanitized audit snapshot to the detector. The detector cannot see the clean snapshot, the seed, the injector target, or the private manifest. Only after the audit is final does exact scoring compare findings with hidden truth.",
        21,
        "boundary",
        "QuantCheck tests this by injecting a controlled fault, then passing only a sanitized audit snapshot to the detector. The detector cannot see the clean snapshot, the seed, the injector target, or the private manifest. Only after the audit is final does exact scoring compare findings with hidden truth.",
    ),
    Scene(
        6,
        "fault_families",
        "The framework supports four narrow fault families: Look-Ahead Timestamp, Unit Drift, Duplicate Observations, and Revision Overwrite.",
        11,
        "families",
        "The framework supports four narrow fault families: Look-Ahead Timestamp, Unit Drift, Duplicate Observations, and Revision Overwrite.",
    ),
    Scene(
        7,
        "benchmark",
        "The rebuilt v0.1 evidence package contains 124 cases: 120 fault cases and four clean controls. Ninety-four cases succeeded. Thirty remained visible as structural no-eligible-target failures. None were incomplete.",
        19,
        "benchmark",
        "The rebuilt v0.1 evidence package contains 124 cases: 120 fault cases and four clean controls. Ninety-four cases succeeded. Thirty remained visible as structural no-eligible-target failures. None were incomplete.",
    ),
    Scene(
        8,
        "metrics",
        "Across successful scored cases, the saved benchmark recorded 130 injected faults and 208 findings: precision 0.625, recall 1.0, F1 0.769, and a false-positive rate of about 7.29 percent. The benchmark retained 78 strict cross-detector false-positive findings.",
        21,
        "dashboard",
        "Across successful scored cases, the saved benchmark recorded 130 injected faults and 208 findings: precision 0.625, recall 1.0, F1 0.769, and a false-positive rate of about 7.29 percent. The benchmark retained 78 strict cross-detector false-positive findings.",
    ),
    Scene(
        9,
        "limitation",
        "That limitation stays visible. In a controlled study on preserved SEC observations, all 120 manufactured faults were exactly matched, while Unit Drift also produced four correlated warnings on neighboring non-target records.",
        16,
        "substrate",
        "That limitation stays visible. In a controlled study on preserved SEC observations, all 120 manufactured faults were exactly matched, while Unit Drift also produced four correlated warnings on neighboring non-target records.",
    ),
    Scene(
        10,
        "real_data",
        "QuantCheck also ran a narrow real public-data study: 472 selected SEC Company Facts records from five issuers. Exact Duplicate found zero duplicate groups among 472 singleton fingerprints.",
        17,
        "real_data",
        "QuantCheck also ran a narrow real public-data study: 472 selected SEC Company Facts records from five issuers. Exact Duplicate found zero duplicate groups among 472 singleton fingerprints.",
    ),
    Scene(
        11,
        "applicability",
        "The other three detectors had zero eligible opportunities under this adapter’s data structure. That is evidence of real-source pipeline execution, not broad validation on natural SEC histories.",
        16,
        "applicability",
        "The other three detectors had zero eligible opportunities under this adapter’s data structure. That is evidence of real-source pipeline execution, not broad validation on natural SEC histories.",
    ),
    Scene(
        12,
        "ending",
        "QuantCheck asks a prior question: whether the data beneath a backtest, ranking, or research conclusion had the right information, at the right time, in the right form. That is the question behind QuantCheck.",
        15,
        "ending",
        "QuantCheck asks a prior question: whether the data beneath a backtest, ranking, or research conclusion had the right information, at the right time, in the right form. That is the question behind QuantCheck.",
    ),
]


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def text(x: int, y: int, value: str, size: int = 28, fill: str = "#ffffff", weight: int = 400, anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" font-family="Inter,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'


def multiline(x: int, y: int, lines: list[str], size: int = 28, fill: str = "#ffffff", weight: int = 400, leading: int = 38, anchor: str = "start") -> str:
    return "".join(text(x, y + i * leading, line, size, fill, weight, anchor) for i, line in enumerate(lines))


def panel(x: int, y: int, w: int, h: int, fill: str = "#162943", stroke: str = "#2e557f", radius: int = 20) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def doc(inner: str, background: str = "#0b1324") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" role="img"><rect width="1920" height="1080" fill="{background}"/>{inner}</svg>'''


def custom_svg(kind: str) -> str:
    if kind == "hook":
        chart = '<path d="M104 760 C260 700 300 820 470 690 S720 590 870 650 S1130 470 1270 520 S1480 270 1780 170" fill="none" stroke="#78e0d0" stroke-width="12" stroke-linecap="round"/>'
        future = '<path d="M1510 180 L1290 440" stroke="#ff8b7b" stroke-width="9" stroke-dasharray="18 16"/><path d="M1280 438 l35 -2 l-19 30" fill="#ff8b7b"/>'
        return doc(
            panel(70, 70, 1780, 940, "#0f1b2d", "#203b5f")
            + text(130, 190, "A backtest can be mathematically correct", 58, "#ffffff", 700)
            + text(130, 265, "and still be wrong if its data knew the future.", 58, "#ffca6b", 700)
            + text(132, 335, "QuantCheck audits the data behind quantitative research.", 28, "#b8c8df", 400)
            + chart
            + future
            + text(1550, 145, "FUTURE", 22, "#ff8b7b", 700, "middle")
            + text(1530, 870, "historical research timeline", 22, "#8fa7c3", 400, "middle")
            + text(132, 940, "Point-in-time integrity comes before performance claims.", 24, "#8fa7c3", 400),
        )
    if kind == "timeline":
        return doc(
            panel(70, 70, 1780, 940, "#f6f8fb", "#d6e0eb")
            + text(130, 190, "Point-in-time truth uses three different dates", 52, "#10243e", 700)
            + text(132, 245, "Period end, research date, and filing date are not interchangeable.", 25, "#52657c", 400)
            + '<line x1="220" y1="550" x2="1700" y2="550" stroke="#9db0c6" stroke-width="8"/>'
            + '<circle cx="380" cy="550" r="22" fill="#3b82f6"/><circle cx="960" cy="550" r="22" fill="#f59e0b"/><circle cx="1540" cy="550" r="22" fill="#16a085"/>'
            + text(380, 465, "REPORTING PERIOD", 19, "#3b82f6", 700, "middle")
            + text(380, 620, "March 31", 32, "#10243e", 700, "middle")
            + text(380, 658, "period ends", 22, "#52657c", 400, "middle")
            + text(960, 465, "RESEARCH DATE", 19, "#c37a00", 700, "middle")
            + text(960, 620, "April 15", 32, "#10243e", 700, "middle")
            + text(960, 658, "decision cutoff", 22, "#52657c", 400, "middle")
            + text(1540, 465, "ACTUAL FILING", 19, "#147a66", 700, "middle")
            + text(1540, 620, "May 2", 32, "#10243e", 700, "middle")
            + text(1540, 658, "publication / availability", 22, "#52657c", 400, "middle")
            + '<path d="M380 500 V390 H1540 V500" fill="none" stroke="#16a085" stroke-width="6"/>'
            + text(960, 360, "correct historical availability window", 24, "#147a66", 700, "middle")
            + text(132, 850, "The question is not when the value describes. It is when the researcher could know it.", 28, "#10243e", 600)
            + text(132, 918, "Controlled illustration — not an observed SEC defect.", 20, "#52657c", 400),
            "#eef2f7",
        )
    if kind == "fault":
        return doc(
            panel(70, 70, 1780, 940, "#0f1b2d", "#203b5f")
            + text(130, 180, "The fault: a future value becomes visible too early", 50, "#ffffff", 700)
            + text(132, 235, "Same reporting period. Wrong availability date.", 25, "#b8c8df", 400)
            + panel(130, 330, 760, 410, "#163a52", "#43b7ff")
            + text(180, 400, "CLEAN POINT-IN-TIME RECORD", 20, "#78e0d0", 700)
            + text(180, 475, "Period end", 24, "#c9d7e8", 400)
            + text(690, 475, "Mar 31", 24, "#ffffff", 700, "end")
            + text(180, 545, "Research date", 24, "#c9d7e8", 400)
            + text(690, 545, "Apr 15", 24, "#ffffff", 700, "end")
            + text(180, 615, "Available on", 24, "#c9d7e8", 400)
            + text(690, 615, "May 2", 24, "#78e0d0", 700, "end")
            + text(180, 690, "Value is unavailable at the cutoff", 23, "#b8c8df", 400)
            + panel(1030, 330, 760, 410, "#4b2b35", "#ff8b7b")
            + text(1080, 400, "CORRUPTED RECORD", 20, "#ffca6b", 700)
            + text(1080, 475, "Period end", 24, "#f7dfb0", 400)
            + text(1590, 475, "Mar 31", 24, "#ffffff", 700, "end")
            + text(1080, 545, "Research date", 24, "#f7dfb0", 400)
            + text(1590, 545, "Apr 15", 24, "#ffffff", 700, "end")
            + text(1080, 615, "Available on", 24, "#f7dfb0", 400)
            + text(1590, 615, "Apr 15", 24, "#ff8b7b", 700, "end")
            + text(1080, 690, "Future information crosses the boundary", 23, "#f7dfb0", 400)
            + text(960, 840, "LOOK-AHEAD LEAK", 28, "#ff8b7b", 700, "middle")
            + text(960, 895, "The data now knows the future.", 24, "#ffffff", 400, "middle"),
        )
    if kind == "consequence":
        return doc(
            panel(70, 70, 1780, 940, "#f6f8fb", "#d6e0eb")
            + text(130, 180, "The controlled research decision changes", 52, "#10243e", 700)
            + text(132, 235, "A single timestamp can change what enters the historical screen.", 25, "#52657c", 400)
            + panel(130, 330, 760, 480, "#ffffff", "#d6e0eb")
            + text(180, 405, "CLEAN DATA", 20, "#147a66", 700)
            + text(180, 470, "April 15 cutoff", 25, "#10243e", 700)
            + text(180, 525, "March-quarter value", 25, "#52657c", 400)
            + text(180, 580, "UNAVAILABLE", 28, "#c34d3d", 700)
            + text(180, 655, "Ranking", 21, "#52657c", 400)
            + '<rect x="180" y="685" width="250" height="22" rx="11" fill="#9db0c6"/><rect x="180" y="725" width="180" height="22" rx="11" fill="#c7d4e1"/>'
            + panel(1030, 330, 760, 480, "#fff8f0", "#ffca6b")
            + text(1080, 405, "CORRUPTED DATA", 20, "#c37a00", 700)
            + text(1080, 470, "April 15 cutoff", 25, "#10243e", 700)
            + text(1080, 525, "March-quarter value", 25, "#52657c", 400)
            + text(1080, 580, "AVAILABLE TOO EARLY", 28, "#c34d3d", 700)
            + text(1080, 655, "Ranking", 21, "#52657c", 400)
            + '<rect x="1080" y="685" width="420" height="22" rx="11" fill="#16a085"/><rect x="1080" y="725" width="260" height="22" rx="11" fill="#7ecfc1"/>'
            + text(960, 900, "CONTROLLED OUTPUT CHANGES", 26, "#10243e", 700, "middle"),
            "#eef2f7",
        )
    if kind == "families":
        colors = ["#3b82f6", "#16a085", "#f59e0b", "#ef6c55"]
        titles = ["LOOK-AHEAD\nTIMESTAMP", "UNIT\nDRIFT", "DUPLICATE\nOBSERVATIONS", "REVISION\nOVERWRITE"]
        icons = ["↶", "×1000", "≡≡", "↔"]
        inner = panel(70, 70, 1780, 940, "#0f1b2d", "#203b5f")
        inner += text(130, 180, "Four supported fault families", 54, "#ffffff", 700)
        inner += text(132, 235, "Each family has a controlled injector, an independent detector, and exact scoring.", 25, "#b8c8df", 400)
        for i, (color, title, icon) in enumerate(zip(colors, titles, icons)):
            x = 130 + i * 420
            inner += panel(x, 360, 360, 400, "#162943", color)
            inner += text(x + 180, 485, icon, 58, color, 700, "middle")
            title_lines = title.split("\n")
            inner += multiline(x + 180, 575, title_lines, 24, "#ffffff", 700, 36, "middle")
            inner += text(x + 180, 705, ["future visibility", "scale semantics", "repeated facts", "later vintage"][i], 19, "#b8c8df", 400, "middle")
        return doc(inner)
    if kind == "real_data":
        return doc(
            panel(70, 70, 1780, 940, "#0f1b2d", "#203b5f")
            + text(130, 180, "Narrow real public-data exposure", 54, "#ffffff", 700)
            + text(132, 235, "SEC Company Facts · five issuers · one end-of-day cutoff", 25, "#b8c8df", 400)
            + panel(130, 340, 520, 390, "#1d3d63", "#43b7ff")
            + text(180, 420, "SELECTED RECORDS", 20, "#78e0d0", 700)
            + text(180, 535, "472", 92, "#ffffff", 700)
            + text(180, 600, "180 Assets", 24, "#c9d7e8", 400)
            + text(180, 640, "292 NetIncomeLoss", 24, "#c9d7e8", 400)
            + panel(700, 340, 520, 390, "#294036", "#78e0d0")
            + text(750, 420, "EXACT DUPLICATE", 20, "#a9f4e2", 700)
            + text(750, 535, "0", 92, "#ffffff", 700)
            + text(750, 600, "findings", 24, "#d1eee5", 400)
            + text(750, 640, "472 singleton fingerprints", 24, "#d1eee5", 400)
            + panel(1270, 340, 520, 390, "#3d4a61", "#8fa7c3")
            + text(1320, 420, "COHORT", 20, "#c8d6e8", 700)
            + multiline(1320, 525, ["Apple", "Microsoft", "Alphabet", "Amazon", "JPMorgan"], 27, "#ffffff", 600, 40)
            + text(130, 870, "This demonstrates real-source ingestion and execution—not broad natural-data validation.", 26, "#ffca6b", 700),
        )
    if kind == "applicability":
        rows = [
            ("Look-Ahead Timestamp", "0", "NOT APPLICABLE", "#c37a00"),
            ("Revision Overwrite", "0", "NOT APPLICABLE", "#c37a00"),
            ("Unit Drift", "0", "NOT APPLICABLE", "#c37a00"),
            ("Exact Duplicate", "472", "APPLICABLE · 0 findings", "#147a66"),
        ]
        inner = panel(70, 70, 1780, 940, "#f6f8fb", "#d6e0eb")
        inner += text(130, 180, "Applicability is part of the result", 52, "#10243e", 700)
        inner += text(132, 235, "A zero finding count is not a detector validation result when there were no eligible opportunities.", 25, "#52657c", 400)
        inner += text(180, 355, "DETECTOR", 19, "#52657c", 700)
        inner += text(850, 355, "OPPORTUNITIES", 19, "#52657c", 700)
        inner += text(1120, 355, "INTERPRETATION", 19, "#52657c", 700)
        for i, (name, count, status, color) in enumerate(rows):
            y = 430 + i * 110
            inner += '<line x1="150" y1="%d" x2="1770" y2="%d" stroke="#d6e0eb" stroke-width="2"/>' % (y - 48, y - 48)
            inner += text(180, y, name, 24, "#10243e", 600)
            inner += text(850, y, count, 28, "#10243e", 700)
            inner += text(1120, y, status, 23, color, 700)
        inner += text(132, 930, "No common 472-record denominator for all four detectors.", 25, "#c34d3d", 700)
        return doc(inner, "#eef2f7")
    if kind == "ending":
        return doc(
            panel(70, 70, 1780, 940, "#0f1b2d", "#203b5f")
            + text(130, 210, "QuantCheck", 72, "#ffffff", 700)
            + text(134, 285, "Audit the data behind quantitative research.", 36, "#78e0d0", 600)
            + '<line x1="135" y1="360" x2="1785" y2="360" stroke="#2f557d" stroke-width="3"/>'
            + text(135, 490, "Did the data have the right information", 42, "#ffffff", 600)
            + text(135, 560, "at the right time", 42, "#ffca6b", 600)
            + text(135, 630, "in the right form?", 42, "#78e0d0", 600)
            + text(135, 790, "Before trusting a backtest, ranking, or research conclusion,", 27, "#b8c8df", 400)
            + text(135, 835, "ask whether the data that produced it deserved to be trusted.", 27, "#b8c8df", 400)
            + text(1785, 950, "DETERMINISTIC · POINT-IN-TIME · EVIDENCE-LED", 19, "#8fa7c3", 700, "end"),
        )
    raise ValueError(kind)


def embedded_asset(kind: str) -> str:
    mapping = {
        "boundary": ASSET_DIR / "quantcheck-hero.svg",
        "benchmark": ASSET_DIR / "benchmark-results.svg",
        "dashboard": ASSET_DIR / "demo-dashboard.svg",
        "substrate": ASSET_DIR / "real-substrate-results.svg",
    }
    source = mapping[kind]
    source_text = source.read_text(encoding="utf-8")
    match = re.search(r'viewBox="([^"]+)"', source_text)
    if not match:
        raise RuntimeError(f"asset has no viewBox: {source}")
    vb = match.group(1).split()
    sw, sh = float(vb[2]), float(vb[3])
    inner = source_text[source_text.find(">") + 1 : source_text.rfind("</svg>")]
    scale = min(1680 / sw, 830 / sh)
    x = (1920 - sw * scale) / 2
    y = 170 + (830 - sh * scale) / 2
    return doc(
        panel(70, 70, 1780, 940, "#f6f8fb", "#d6e0eb")
        + f'<g transform="translate({x:.2f},{y:.2f}) scale({scale:.6f})">{inner}</g>',
        "#eef2f7",
    )


def write_slides() -> None:
    svg_dir = BUILD_DIR / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        content = custom_svg(scene.visual) if scene.visual in {"hook", "timeline", "fault", "consequence", "families", "real_data", "applicability", "ending"} else embedded_asset(scene.visual)
        path = svg_dir / f"{scene.number:02d}-{scene.slug}.svg"
        path.write_text(content, encoding="utf-8")


def render_pngs() -> None:
    svg_dir = BUILD_DIR / "svg"
    png_dir = BUILD_DIR / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        svg_path = svg_dir / f"{scene.number:02d}-{scene.slug}.svg"
        subprocess.run(["qlmanage", "-t", "-s", str(WIDTH), "-o", str(png_dir), str(svg_path)], check=True, stdout=subprocess.DEVNULL)
        rendered = png_dir / f"{svg_path.name}.png"
        cropped = png_dir / f"{scene.number:02d}-{scene.slug}.png"
        subprocess.run(["sips", "--cropToHeightWidth", str(HEIGHT), str(WIDTH), str(rendered), "--out", str(cropped)], check=True, stdout=subprocess.DEVNULL)
        rendered.unlink(missing_ok=True)
        scene.image = str(cropped)


def afinfo_duration(path: Path) -> float:
    result = subprocess.run(["afinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"estimated duration:\s*([0-9.]+)", result.stdout)
    if not match:
        raise RuntimeError(f"could not read duration for {path}")
    return float(match.group(1))


def make_audio() -> None:
    audio_dir = BUILD_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        path = audio_dir / f"{scene.number:02d}-{scene.slug}.aiff"
        subprocess.run(["say", "-v", "Samantha", "-r", "150", "-o", str(path), scene.narration], check=True)
        scene.audio = str(path)
        scene.audio_seconds = afinfo_duration(path)

    # Give every scene room to breathe, while keeping the final cut in the requested range.
    total_audio = sum(scene.audio_seconds for scene in SCENES)
    # The narration itself is already close to the requested window. Add only
    # enough breathing room to reach roughly 2:56, never enough to exceed 3:00.
    total_pad = max(0.0, 176.0 - total_audio)
    pad_each = total_pad / len(SCENES)
    cursor = 0.0
    for scene in SCENES:
        scene.start_seconds = cursor
        scene.duration_seconds = scene.audio_seconds + pad_each
        cursor += scene.duration_seconds


def write_captions_and_manifest() -> Path:
    manifest_path = BUILD_DIR / "manifest.json"
    manifest_path.write_text(json.dumps([asdict(scene) for scene in SCENES], indent=2), encoding="utf-8")
    narration = "\n\n".join(f"[{scene.number:02d}] {scene.narration}" for scene in SCENES)
    (VIDEO_DIR / "narration.txt").write_text(narration + "\n", encoding="utf-8")

    def ts(seconds: float) -> str:
        whole = int(seconds)
        millis = int(round((seconds - whole) * 1000))
        if millis == 1000:
            whole += 1
            millis = 0
        h, rem = divmod(whole, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"

    vtt = ["WEBVTT", ""]
    for scene in SCENES:
        vtt.extend([f"{ts(scene.start_seconds)} --> {ts(scene.start_seconds + scene.duration_seconds)}", scene.caption, ""])
    (VIDEO_DIR / "captions.vtt").write_text("\n".join(vtt), encoding="utf-8")
    return manifest_path


def compile_and_run_swift(manifest_path: Path) -> None:
    swift_path = BUILD_DIR / "assemble_video.swift"
    binary_path = BUILD_DIR / "assemble_video"
    swift_path.write_text(SWIFT_SOURCE, encoding="utf-8")
    subprocess.run(["swiftc", str(swift_path), "-o", str(binary_path), "-framework", "AVFoundation", "-framework", "AppKit", "-framework", "CoreGraphics"], check=True)
    output = VIDEO_DIR / "QuantCheck_demo.mp4"
    subprocess.run([str(binary_path), str(manifest_path), str(output)], check=True)


SWIFT_SOURCE = r'''
import Foundation
import AVFoundation
import AppKit
import ImageIO
import CoreVideo
import CoreGraphics

struct Scene: Decodable {
    let number: Int
    let slug: String
    let narration: String
    let planned_seconds: Double
    let visual: String
    let caption: String
    let image: String
    let audio: String
    let audio_seconds: Double
    let start_seconds: Double
    let duration_seconds: Double
}

enum BuildError: Error { case badArguments, noImage, pixelCreate, contextCreate, sampleCreate, appendFailed, noVideoTrack, noAudioTrack, exportFailed }

func imageFor(_ path: String) throws -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { throw BuildError.noImage }
    return image
}

func appendPixelBuffer(_ image: CGImage, to input: AVAssetWriterInput, writer: AVAssetWriter, at time: CMTime) throws {
    var buffer: CVPixelBuffer?
    let attrs: [String: Any] = [kCVPixelBufferIOSurfacePropertiesKey as String: [:]]
    guard CVPixelBufferCreate(nil, 1920, 1080, kCVPixelFormatType_32BGRA, attrs as CFDictionary, &buffer) == kCVReturnSuccess, let pixel = buffer else { throw BuildError.pixelCreate }
    CVPixelBufferLockBaseAddress(pixel, [])
    defer { CVPixelBufferUnlockBaseAddress(pixel, []) }
    let width = CVPixelBufferGetWidth(pixel)
    let height = CVPixelBufferGetHeight(pixel)
    let bytesPerRow = CVPixelBufferGetBytesPerRow(pixel)
    guard let base = CVPixelBufferGetBaseAddress(pixel) else { throw BuildError.noImage }
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    guard let context = CGContext(data: base, width: width, height: height, bitsPerComponent: 8, bytesPerRow: bytesPerRow, space: colorSpace, bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue) else { throw BuildError.contextCreate }
    context.setFillColor(NSColor.black.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.interpolationQuality = .high
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    var format: CMVideoFormatDescription?
    guard CMVideoFormatDescriptionCreateForImageBuffer(allocator: kCFAllocatorDefault, imageBuffer: pixel, formatDescriptionOut: &format) == noErr, let formatDescription = format else { throw BuildError.contextCreate }
    var timing = CMSampleTimingInfo(duration: CMTime(value: 1, timescale: 30), presentationTimeStamp: time, decodeTimeStamp: .invalid)
    var sample: CMSampleBuffer?
    guard CMSampleBufferCreateReadyWithImageBuffer(allocator: kCFAllocatorDefault, imageBuffer: pixel, formatDescription: formatDescription, sampleTiming: &timing, sampleBufferOut: &sample) == noErr, let sampleBuffer = sample else { throw BuildError.sampleCreate }
    while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.002) }
    if !input.append(sampleBuffer) { fputs("append failed: \(String(describing: writer.error))\n", stderr); throw BuildError.appendFailed }
}

func makeVideo(_ scenes: [Scene], url: URL) throws {
    if FileManager.default.fileExists(atPath: url.path) { try FileManager.default.removeItem(at: url) }
    let writer = try AVAssetWriter(outputURL: url, fileType: .mov)
    let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: 1920, AVVideoHeightKey: 1080, AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 8_000_000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel]]
    let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
    input.expectsMediaDataInRealTime = false
    let attrs: [String: Any] = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA, kCVPixelBufferWidthKey as String: 1920, kCVPixelBufferHeightKey as String: 1080]
    writer.add(input)
    writer.startWriting()
    writer.startSession(atSourceTime: .zero)
    var frameNumber: Int64 = 0
    let fps = 30.0
    for scene in scenes {
        let image = try imageFor(scene.image)
        let frames = Int((scene.duration_seconds * fps).rounded())
        for _ in 0..<frames {
            try appendPixelBuffer(image, to: input, writer: writer, at: CMTime(value: frameNumber, timescale: 30))
            frameNumber += 1
        }
    }
    input.markAsFinished()
    let sem = DispatchSemaphore(value: 0)
    writer.finishWriting { sem.signal() }
    sem.wait()
    if writer.status != .completed { throw writer.error ?? BuildError.exportFailed }
}

func mux(_ scenes: [Scene], videoURL: URL, outputURL: URL) throws {
    let composition = AVMutableComposition()
    let videoAsset = AVURLAsset(url: videoURL)
    guard let sourceVideo = videoAsset.tracks(withMediaType: .video).first else { throw BuildError.noVideoTrack }
    let videoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
    try videoTrack.insertTimeRange(CMTimeRange(start: .zero, duration: videoAsset.duration), of: sourceVideo, at: .zero)
    let audioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
    for scene in scenes {
        let asset = AVURLAsset(url: URL(fileURLWithPath: scene.audio))
        guard let sourceAudio = asset.tracks(withMediaType: .audio).first else { throw BuildError.noAudioTrack }
        let duration = CMTime(seconds: scene.audio_seconds, preferredTimescale: 600)
        try audioTrack.insertTimeRange(CMTimeRange(start: .zero, duration: duration), of: sourceAudio, at: CMTime(seconds: scene.start_seconds, preferredTimescale: 600))
    }
    if FileManager.default.fileExists(atPath: outputURL.path) { try FileManager.default.removeItem(at: outputURL) }
    guard let exporter = AVAssetExportSession(asset: composition, presetName: AVAssetExportPresetHighestQuality) else { throw BuildError.exportFailed }
    exporter.outputURL = outputURL
    exporter.outputFileType = .mp4
    exporter.shouldOptimizeForNetworkUse = true
    let sem = DispatchSemaphore(value: 0)
    exporter.exportAsynchronously { sem.signal() }
    sem.wait()
    if exporter.status != .completed { throw exporter.error ?? BuildError.exportFailed }
}

guard CommandLine.arguments.count == 3 else { throw BuildError.badArguments }
let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let data = try Data(contentsOf: manifestURL)
let scenes = try JSONDecoder().decode([Scene].self, from: data)
let silentURL = manifestURL.deletingLastPathComponent().appendingPathComponent("silent_video.mov")
try makeVideo(scenes, url: silentURL)
try mux(scenes, videoURL: silentURL, outputURL: outputURL)
print(outputURL.path)
'''


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("This builder uses macOS Quick Look, say, and AVFoundation.")
    if not shutil.which("swiftc"):
        raise SystemExit("swiftc is required")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    write_slides()
    render_pngs()
    make_audio()
    manifest = write_captions_and_manifest()
    compile_and_run_swift(manifest)
    print(f"Built {VIDEO_DIR / 'QuantCheck_demo.mp4'}")
    print(f"Duration target: {sum(scene.duration_seconds for scene in SCENES):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
