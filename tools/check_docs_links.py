from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


LINK_PATTERN = re.compile(r"!??\[[^\]]+\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class BrokenLink:
    source: Path
    target: str
    reason: str


def slugify_heading(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[`*_\[\](){}.!?,:;\"'\\/]+", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def collect_markdown_files(docs_dir: Path) -> list[Path]:
    return sorted(p for p in docs_dir.rglob("*.md") if p.is_file())


def collect_headings(md_file: Path) -> set[str]:
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    content = md_file.read_text(encoding="utf-8", errors="ignore")

    for line in content.splitlines():
        match = HEADING_PATTERN.match(line.strip())
        if not match:
            continue

        base = slugify_heading(match.group(2))
        if not base:
            continue

        index = seen.get(base, 0)
        slug = base if index == 0 else f"{base}-{index}"
        seen[base] = index + 1
        slugs.add(slug)

    return slugs


def is_external_link(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.scheme in {"http", "https", "mailto", "tel", "data", "javascript"}


def parse_target(link: str) -> tuple[str, str]:
    decoded = unquote(link.strip())
    if "#" in decoded:
        target, anchor = decoded.split("#", 1)
    else:
        target, anchor = decoded, ""
    return target.strip(), anchor.strip()


def find_broken_links(root: Path, docs_dir: Path) -> tuple[int, list[BrokenLink]]:
    md_files = collect_markdown_files(docs_dir)
    headings = {p.resolve(): collect_headings(p) for p in md_files}

    checked = 0
    broken: list[BrokenLink] = []

    for md in md_files:
        content = md.read_text(encoding="utf-8", errors="ignore")

        for match in LINK_PATTERN.finditer(content):
            raw_link = match.group(1).strip()
            if not raw_link or raw_link.startswith("#") or is_external_link(raw_link):
                continue

            checked += 1
            target, anchor = parse_target(raw_link)
            target_path = (md.parent / target).resolve() if target else md.resolve()

            if not target_path.exists():
                broken.append(BrokenLink(md, raw_link, "file-not-found"))
                continue

            if anchor and target_path.suffix.lower() == ".md":
                anchor_slug = slugify_heading(anchor)
                if anchor_slug not in headings.get(target_path, set()):
                    broken.append(BrokenLink(md, raw_link, "anchor-not-found"))

    return checked, broken


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate markdown relative links and heading anchors under docs/."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root path (default: auto-detected).",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Docs directory relative to --root (default: docs).",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=100,
        help="Max number of broken links to print (default: 100).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = args.root.resolve()
    docs_dir = (root / args.docs_dir).resolve() if not args.docs_dir.is_absolute() else args.docs_dir.resolve()

    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"[ERROR] docs directory not found: {docs_dir}")
        return 2

    checked, broken = find_broken_links(root, docs_dir)

    print(f"docs_dir: {docs_dir}")
    print(f"links_checked: {checked}")
    print(f"broken_count: {len(broken)}")

    for item in broken[: max(0, args.max_errors)]:
        rel_source = item.source.resolve().relative_to(root)
        print(f"BROKEN {rel_source} -> {item.target} [{item.reason}]")

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
