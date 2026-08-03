#!/usr/bin/env python3
"""Validate the generated scholarly video gallery before release."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
DESCRIPTION_RE = re.compile(r'<meta name="description" content="([^"]*)">')
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(root: Path) -> None:
    catalog_v1 = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
    catalog_v2 = json.loads((root / "data" / "catalog.v2.json").read_text(encoding="utf-8"))
    videos = catalog_v2["videos"]
    require(catalog_v1["schema"] == "zalizniak-video-catalog/1", "v1 schema changed")
    require(catalog_v2["schema"] == "zalizniak-video-catalog/2", "v2 schema changed")
    require(bool(videos), "catalog has no videos")
    require(len({v["accession"] for v in videos}) == len(videos), "duplicate accession")
    require(len({v["id"] for v in videos}) == len(videos), "duplicate YouTube id")
    require((root / "index.html").stat().st_size <= 250_000, "index exceeds 250 KB release budget")

    titles: set[str] = set()
    descriptions: set[str] = set()
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    for video in videos:
        accession = video["accession"]
        youtube_id = video["id"]
        canonical_path = f"v/{accession}/"
        alias_path = f"video/{youtube_id}/"
        require(video["path"] == canonical_path, f"bad v2 path for {accession}")
        require(video["legacy_path"] == alias_path, f"bad alias path for {accession}")
        detail_file = root / canonical_path / "index.html"
        alias_file = root / alias_path / "index.html"
        thumb_file = root / "assets" / "thumbs" / f"{accession}.jpg"
        require(detail_file.is_file(), f"missing canonical page {canonical_path}")
        require(alias_file.is_file(), f"missing alias page {alias_path}")
        require(thumb_file.is_file() and thumb_file.read_bytes()[:2] == b"\xff\xd8", f"bad thumbnail {accession}")

        detail = detail_file.read_text(encoding="utf-8")
        title = TITLE_RE.search(detail)
        description = DESCRIPTION_RE.search(detail)
        canonical = CANONICAL_RE.search(detail)
        json_ld = JSON_LD_RE.search(detail)
        require(bool(title and description and canonical and json_ld), f"incomplete SEO metadata for {accession}")
        require(title.group(1) not in titles, f"duplicate title for {accession}")
        require(description.group(1) not in descriptions, f"duplicate description for {accession}")
        titles.add(title.group(1))
        descriptions.add(description.group(1))
        expected_url = f"{catalog_v2['site']}/{canonical_path}"
        require(canonical.group(1) == expected_url, f"wrong canonical for {accession}")
        structured = json.loads(json_ld.group(1))
        require(structured.get("@type") == "VideoObject", f"wrong JSON-LD type for {accession}")
        require(structured.get("identifier") == accession, f"wrong JSON-LD accession for {accession}")
        require(expected_url in sitemap, f"sitemap missing {accession}")

        alias = alias_file.read_text(encoding="utf-8")
        require('content="noindex, follow"' in alias, f"alias is indexable for {accession}")
        require('<meta http-equiv="refresh"' in alias, f"alias has no refresh for {accession}")
        require(f'href="{expected_url}"' in alias, f"alias points elsewhere for {accession}")

    v1_by_id = {video["id"]: video for video in catalog_v1["videos"]}
    require(len(v1_by_id) == len(videos), "v1 video count differs from v2")
    for video in videos:
        require(v1_by_id[video["id"]]["path"] == video["legacy_path"], f"v1 path changed for {video['id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        validate(args.root)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    catalog = json.loads((args.root / "data" / "catalog.v2.json").read_text(encoding="utf-8"))
    print(f"OK: {len(catalog['videos'])} canonical pages, aliases, thumbnails and SEO records validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
