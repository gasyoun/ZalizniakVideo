import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site


def fixture_payload():
    return {
        "schema": "video_catalog_public/1",
        "version": 1,
        "built_at": "2026-08-03T00:00:00Z",
        "stats": {"source_rows": 1, "videos": 1, "unique_youtube_ids": 1, "unresolved_records": 0, "related_resources": 0},
        "videos": [
            {
                "accession": "017",
                "youtube_id": "abcdefghijk",
                "title_source": "Лекция — проверка",
                "title_display": "Лекция — проверка",
                "watch_url": "https://youtu.be/abcdefghijk",
                "duration_seconds": 3723,
                "topics": ["береста", "диалектология"],
                "type": "лекция",
                "purpose": "Новгородские чтения",
                "transcript_status": "automatic",
                "last_verified_at": "2026-08-03",
                "related_entities": [{"head": "Новгород"}],
            }
        ],
        "unresolved_records": [],
        "related_resources": [],
    }


class NormalizeTests(unittest.TestCase):
    def test_public_contract_maps_to_frozen_accession(self):
        records, meta = build_site.normalize_records(fixture_payload())
        self.assertEqual(meta["schema"], "video_catalog_public/1")
        self.assertEqual(records[0]["accession"], "017")
        self.assertEqual(records[0]["path"], "v/017/")
        self.assertEqual(records[0]["legacy_path"], "video/abcdefghijk/")
        self.assertEqual(records[0]["duration"], 3723)
        self.assertEqual(records[0]["title"], "Лекция — проверка")
        self.assertEqual(records[0]["url"], "https://youtu.be/abcdefghijk")
        self.assertEqual(records[0]["topics"], ["береста", "диалектология"])
        self.assertEqual(records[0]["series"], "Новгородские чтения")
        self.assertEqual(records[0]["last_verified_at"], "2026-08-03")

    def test_duplicate_accessions_fail(self):
        payload = fixture_payload()
        duplicate = dict(payload["videos"][0], youtube_id="lmnopqrstuv")
        payload["videos"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate accession"):
            build_site.normalize_records(payload)

    def test_v1_export_retains_schema_and_legacy_path(self):
        records, meta = build_site.normalize_records(fixture_payload())
        export = build_site.v1_export(records, meta)
        self.assertEqual(export["schema"], "zalizniak-video-catalog/1")
        self.assertEqual(export["videos"][0]["path"], "video/abcdefghijk/")
        self.assertEqual(
            set(export["videos"][0]),
            {"id", "title", "url", "path", "date", "duration", "theme", "stage", "collision", "titles_all", "related_entities"},
        )


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.record = build_site.normalize_records(fixture_payload())[0][0]

    def test_detail_has_click_to_load_player_and_video_seo(self):
        page = build_site.render_video(self.record)
        self.assertIn('data-load-player', page)
        self.assertNotIn('<iframe', page)
        self.assertIn('youtube-nocookie.com/embed/abcdefghijk', page)
        self.assertIn('<meta property="og:type" content="video.other">', page)
        self.assertIn('"@type":"VideoObject"', page)
        self.assertNotIn('"dateRecorded"', page)
        self.assertNotIn('"uploadDate"', page)
        self.assertNotIn("—", page)

    def test_index_has_all_url_synced_filters(self):
        page = build_site.render_index([self.record])
        for name in ("q", "topic", "type", "series", "year", "transcript"):
            self.assertIn(f'name="{name}"', page)
        self.assertIn('role="status"', page)
        self.assertIn('history.replaceState', page)
        self.assertIn('alt=""', page)

    def test_alias_is_noindex_and_canonical(self):
        page = build_site.render_alias(self.record)
        self.assertIn('content="noindex, follow"', page)
        self.assertIn('<meta http-equiv="refresh"', page)
        self.assertIn('/v/017/', page)


class BuildTests(unittest.TestCase):
    def test_build_is_deterministic_and_writes_both_routes(self):
        records, meta = build_site.normalize_records(fixture_payload())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thumbs = root / "assets" / "thumbs"
            thumbs.mkdir(parents=True)
            (thumbs / "017.jpg").write_bytes(b"\xff\xd8" + b"x" * 1200)
            build_site.validate(records, thumbs)
            build_site.write_site(records, meta, root)
            first = (root / "index.html").read_bytes()
            build_site.write_site(records, meta, root)
            self.assertEqual(first, (root / "index.html").read_bytes())
            self.assertTrue((root / "v" / "017" / "index.html").is_file())
            self.assertTrue((root / "video" / "abcdefghijk" / "index.html").is_file())
            self.assertEqual(json.loads((root / "data" / "catalog.v2.json").read_text(encoding="utf-8"))["videos"][0]["path"], "v/017/")

    def test_default_catalog_path_is_not_a_worktree_name(self):
        self.assertEqual(build_site.DEFAULT_PUBLIC_CATALOG.parent.parent.name, "BookIndex")
        self.assertNotIn("scholarly", str(build_site.DEFAULT_PUBLIC_CATALOG))


if __name__ == "__main__":
    unittest.main()
