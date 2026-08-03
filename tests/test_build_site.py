import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site
import sync_bookindex


def fixture_payload():
    return {
        "schema": "video_catalog_public/1",
        "version": 1,
        "source": {
            "sheet_url": "https://docs.google.com/spreadsheets/d/example",
            "sheet_gid": "0",
            "snapshot_file": "data/video_catalog_snapshot.json",
            "snapshot_at": "2026-08-03T00:00:00Z",
            "accession_registry": "data/video_accessions.json",
            "canonical_inputs": ["data/video_catalog_snapshot.json"],
            "editorial_file": "data/video_catalog_editorial.json",
        },
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


def fixture_v2_payload():
    payload = fixture_payload()
    payload["schema"] = "video_catalog_public/2"
    payload["version"] = 2
    payload["stats"]["reconciled_records"] = 0
    payload["reconciled_records"] = []
    payload["videos"][0].update({
        "contributors": [{"name": "А. А. Зализняк", "role": "lecturer"}],
        "date_recorded": "2008-05-12",
        "evidence": [
            {
                "label": "YouTube metadata",
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
                "supports": ["title_display"],
                "accessed_at": "2026-08-04",
            }
        ],
    })
    payload["videos"][0]["last_verified_at"] = "2026-08-04"
    return payload


def encoded_export(payload):
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    return raw


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

    def test_public_v2_maps_evidence_to_compact_provenance(self):
        records, meta = build_site.normalize_records(fixture_v2_payload())
        self.assertEqual(meta["schema"], "video_catalog_public/2")
        record = records[0]
        self.assertEqual(record["evidence"], record["provenance"])
        self.assertEqual(record["contributors"], [{"name": "А. А. Зализняк", "role": "lecturer"}])
        self.assertEqual(record["contributor_labels"], ["А. А. Зализняк, лектор"])
        self.assertEqual(build_site.v2_export(records, meta)["videos"][0]["contributors"][0]["role"], "lecturer")
        page = build_site.render_video(record)
        self.assertIn("YouTube metadata", page)
        self.assertIn("подтверждает: title_display", page)
        self.assertNotIn("{&quot;source&quot;", page)

    def test_missing_contributor_and_date_values_stay_unknown_or_omitted(self):
        payload = fixture_v2_payload()
        video = payload["videos"][0]
        video["contributors"] = []
        video["date_recorded"] = None
        records, _ = build_site.normalize_records(payload)
        page = build_site.render_video(records[0])
        self.assertNotIn("А. А. Зализняк", page)
        self.assertNotIn("2008-05-12", page)
        self.assertNotIn("<dt>Участники</dt>", page)
        self.assertIn("дата неизвестна", page)

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


class SyncTests(unittest.TestCase):
    def test_v2_raw_checksum_is_recorded_for_audit(self):
        raw = encoded_export(fixture_v2_payload())
        payload, checksum = sync_bookindex.validate_export(raw)
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit.json"
            sync_bookindex.write_audit(audit, payload, checksum, "fixture")
            stored = json.loads(audit.read_text(encoding="utf-8"))
        self.assertEqual(checksum, hashlib.sha256(raw).hexdigest())
        self.assertEqual(stored["sha256"], checksum)
        self.assertEqual(stored["records"], 1)

    def make_repository(self, parent: Path, payload: dict, name: str = "repo") -> Path:
        root = parent / name
        root.mkdir()
        records, meta = build_site.normalize_records(payload)
        thumbs = root / "assets" / "thumbs"
        thumbs.mkdir(parents=True)
        for record in records:
            (thumbs / f"{record['accession']}.jpg").write_bytes(b"\xff\xd8" + b"x" * 1200)
        build_site.write_site(records, meta, root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Tests"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
        return root

    def run_sync(self, root: Path, payload: dict, temp_parent: Path):
        raw = encoded_export(payload)
        artifact = root / ".sync-artifacts" / "bookindex-video-v2.patch"
        return sync_bookindex.sync(
            root,
            raw,
            artifact,
            quality_checks=lambda _: None,
            temp_parent=temp_parent,
        ), artifact

    def test_sync_no_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.make_repository(parent, fixture_v2_payload())
            before_catalog = (root / "data" / "catalog.v2.json").read_text(encoding="utf-8")
            temp_parent = parent / "temps"
            temp_parent.mkdir()
            changed, artifact = self.run_sync(root, fixture_v2_payload(), temp_parent)
            self.assertEqual(before_catalog, (root / "data" / "catalog.v2.json").read_text(encoding="utf-8"))
            self.assertEqual(changed, [])
            self.assertFalse(artifact.exists())
            self.assertEqual(list(temp_parent.iterdir()), [])

    def test_sync_valid_drift_writes_binary_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.make_repository(parent, fixture_v2_payload())
            review_root = self.make_repository(parent, fixture_v2_payload(), "review")
            changed_payload = fixture_v2_payload()
            changed_payload["videos"][0]["title_display"] = "Исправленное название"
            temp_parent = parent / "temps"
            temp_parent.mkdir()
            changed, artifact = self.run_sync(root, changed_payload, temp_parent)
            self.assertIn("index.html", changed)
            self.assertTrue(artifact.is_file())
            self.assertIn(b"diff --git", artifact.read_bytes())
            patch_check = subprocess.run(["git", "apply", "--check", "--binary", str(artifact)], cwd=review_root)
            self.assertEqual(patch_check.returncode, 0)
            self.assertIn("Исправленное название", (root / "index.html").read_text(encoding="utf-8"))
            self.assertEqual(list(temp_parent.iterdir()), [])

    def test_sync_fetches_only_missing_thumbnail_and_patch_carries_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.make_repository(parent, fixture_v2_payload())
            review_root = self.make_repository(parent, fixture_v2_payload(), "review")
            payload = fixture_v2_payload()
            second = json.loads(json.dumps(payload["videos"][0]))
            second.update({
                "accession": "018",
                "youtube_id": "lmnopqrstuv",
                "watch_url": "https://youtu.be/lmnopqrstuv",
                "title_source": "Вторая лекция",
                "title_display": "Вторая лекция",
            })
            second["evidence"][0]["url"] = "https://www.youtube.com/watch?v=lmnopqrstuv"
            payload["videos"].append(second)
            payload["stats"].update({"source_rows": 2, "videos": 2, "unique_youtube_ids": 2})
            fetched = []

            def fetch_missing(records, thumb_root):
                for record in records:
                    target = thumb_root / f"{record['accession']}.jpg"
                    if not target.exists():
                        fetched.append(record["accession"])
                        target.write_bytes(b"\xff\xd8" + bytes(range(256)) * 8)

            raw = encoded_export(payload)
            artifact = root / ".sync-artifacts" / "bookindex-video-v2.patch"
            temp_parent = parent / "temps"
            temp_parent.mkdir()
            with mock.patch.object(sync_bookindex.build_site, "fetch_thumbnails", fetch_missing):
                changed = sync_bookindex.sync(root, raw, artifact, quality_checks=lambda _: None, temp_parent=temp_parent)
            self.assertEqual(fetched, ["018"])
            self.assertIn("assets/thumbs", changed)
            self.assertIn(b"GIT binary patch", artifact.read_bytes())
            patch_check = subprocess.run(["git", "apply", "--check", "--binary", str(artifact)], cwd=review_root)
            self.assertEqual(patch_check.returncode, 0)

    def test_sync_rejects_malformed_export_without_tracked_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.make_repository(parent, fixture_v2_payload())
            before = (root / "index.html").read_bytes()
            temp_parent = parent / "temps"
            temp_parent.mkdir()
            with self.assertRaisesRegex(sync_bookindex.SyncError, "schema v2"):
                sync_bookindex.sync(root, b"{}", root / "drift.patch", quality_checks=lambda _: None, temp_parent=temp_parent)
            self.assertEqual((root / "index.html").read_bytes(), before)
            self.assertEqual(list(temp_parent.iterdir()), [])

    def test_sync_missing_thumbnail_has_accession_and_no_partial_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self.make_repository(parent, fixture_v2_payload())
            before = (root / "index.html").read_bytes()
            payload = fixture_v2_payload()
            payload["videos"][0]["accession"] = "018"
            raw = encoded_export(payload)
            temp_parent = parent / "temps"
            temp_parent.mkdir()
            with mock.patch.object(sync_bookindex.build_site, "fetch_thumbnails", lambda *_: None):
                with self.assertRaisesRegex(sync_bookindex.SyncError, "018"):
                    sync_bookindex.sync(root, raw, root / "drift.patch", quality_checks=lambda _: None, temp_parent=temp_parent)
            self.assertEqual((root / "index.html").read_bytes(), before)
            self.assertEqual(list(temp_parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
