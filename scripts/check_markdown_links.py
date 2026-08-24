"""Validate links in tracked Markdown files without requiring network access."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

INLINE_LINK = re.compile(r"\[[^\]\n]*\]\(\s*(<[^>\n]*>|[^\s)\n]+)")
REFERENCE_DEFINITION = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|[^\s]+)", re.MULTILINE)
FENCE = re.compile(r"^[ \t]{0,3}(``+|~~~+).*$", re.MULTILINE)


def _repository_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _tracked_markdown(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / relative for relative in result.stdout.decode("utf-8").split("\0") if relative]


def _without_fenced_code(markdown: str) -> str:
    """Blank fenced blocks while preserving offsets and line numbers."""

    chars = list(markdown)
    opening: tuple[str, int] | None = None
    for match in FENCE.finditer(markdown):
        marker = match.group(1)[0]
        if opening is None:
            opening = (marker, match.start())
        elif marker == opening[0]:
            for index in range(opening[1], match.end()):
                if chars[index] != "\n":
                    chars[index] = " "
            opening = None
    if opening is not None:
        for index in range(opening[1], len(chars)):
            if chars[index] != "\n":
                chars[index] = " "
    return "".join(chars)


def _target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.strip()


def _check_target(root: Path, source: Path, raw_target: str) -> str | None:
    target = _target(raw_target)
    if not target or target.startswith("#"):
        return None

    parsed = urlsplit(target)
    if parsed.scheme:
        if parsed.scheme in {"https", "mailto"}:
            return None
        return f"unsupported URL scheme {parsed.scheme!r}"
    if parsed.netloc:
        return "network-relative URLs are not allowed; use HTTPS"

    relative = unquote(parsed.path)
    if not relative:
        return None
    if relative.startswith("/"):
        return "absolute filesystem paths are not allowed"

    candidate = (source.parent / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return "relative link escapes the repository"
    if not candidate.exists():
        return f"target does not exist: {relative!r}"
    return None


def check_file(root: Path, path: Path) -> list[str]:
    try:
        markdown = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return [f"{path.relative_to(root)}: cannot decode as UTF-8: {error}"]

    searchable = _without_fenced_code(markdown)
    matches = list(INLINE_LINK.finditer(searchable))
    matches.extend(REFERENCE_DEFINITION.finditer(searchable))
    failures: list[str] = []
    for match in matches:
        raw_target = match.group(1)
        failure = _check_target(root, path, raw_target)
        if failure:
            line = searchable.count("\n", 0, match.start()) + 1
            failures.append(f"{path.relative_to(root)}:{line}: {failure} ({_target(raw_target)})")
    return failures


def main() -> int:
    try:
        root = _repository_root()
        files = _tracked_markdown(root)
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        print(f"MARKDOWN_LINKS_ERROR: {error}", file=sys.stderr)
        return 1

    failures = [failure for path in files for failure in check_file(root, path)]
    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"MARKDOWN_LINKS_FAILED ({len(failures)} issue(s))", file=sys.stderr)
        return 1
    print(f"MARKDOWN_LINKS_OK ({len(files)} tracked Markdown files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
