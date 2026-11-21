"""Offline regression tests: these tests NEVER modify a YouTube account."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from manage import (
    CHANNEL_ID, load_plan, make_video_patch, merge_description, safe_file,
    validate_title, apply_plan,
)


class ManageTests(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(validate_title("Justification by Faith"), "Justification by Faith")
        for bad in ("", "x" * 101, "<script>"):
            with self.assertRaises(ValueError):
                validate_title(bad)

    def test_append_exact_and_idempotent(self):
        original = "Historical work and theological disclaimer."
        addition = "THE GOSPEL\nChrist died and rose again.\nWrite to us."
        merged = merge_description(original, addition)
        self.assertEqual(merged, original + "\n\n" + addition)
        self.assertEqual(merge_description(merged, addition), merged)

    def test_no_truncation_or_overwrite(self):
        with self.assertRaisesRegex(ValueError, "No update was sent"):
            merge_description("A" * 4950, "B" * 100)
        self.assertEqual(merge_description("Keep the existing text", ""), "Keep the existing text")

    def test_reject_paths_outside_repo(self):
        with self.assertRaises(ValueError):
            safe_file("../../etc/passwd", (".txt",))
        with self.assertRaises(ValueError):
            safe_file("/etc/passwd", (".txt",))

    def test_video_patch_preserves_metadata_and_omits_status(self):
        source = {"snippet": {
            "channelId": CHANNEL_ID, "title": "Old", "description": "Historical info",
            "tags": ["faith", "reformation"], "categoryId": "27", "defaultLanguage": "en",
        }, "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
        patch = make_video_patch({"videoId": "hrTiAYYibaU", "title": "New"}, source)
        self.assertEqual(patch["snippet"]["description"], "Historical info")
        self.assertEqual(patch["snippet"]["tags"], ["faith", "reformation"])
        self.assertEqual(patch["snippet"]["categoryId"], "27")
        self.assertEqual(patch["snippet"]["defaultLanguage"], "en")
        self.assertNotIn("status", patch)

    def test_video_patch_rejects_wrong_channel(self):
        source = {"snippet": {
            "channelId": "UCother", "title": "Old", "description": "Text",
            "categoryId": "27",
        }}
        with self.assertRaisesRegex(ValueError, "not owned"):
            make_video_patch({"videoId": "hrTiAYYibaU", "title": "New"}, source)

    def test_manifest_explicit_channel_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plan.json"
            bad = {"expectedChannelId": "wrong",
                   "videos": [{"videoId": "hrTiAYYibaU", "title": "Changed"}]}
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan(p)
            bad["expectedChannelId"] = CHANNEL_ID
            bad["videos"].append(bad["videos"][0])
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_plan(p)
            bad["videos"] = bad["videos"][:1]
            p.write_text(json.dumps(bad), encoding="utf-8")
            self.assertEqual(len(load_plan(p)["videos"]), 1)

    def test_preview_does_not_write(self):
        resource = {"snippet": {
            "channelId": CHANNEL_ID, "title": "Old", "description": "Text",
            "categoryId": "27", "tags": []
        }, "status": {"privacyStatus": "public"}}
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {"items": [resource]}
        with patch("uploader.verify_channel"):
            report = apply_plan(youtube, {
                "videos": [{"videoId": "hrTiAYYibaU", "title": "New"}],
                "playlists": [],
            }, apply=False)
        self.assertFalse(report["applied"])
        self.assertTrue(report["videos"][0]["changeTitle"])
        youtube.videos.return_value.update.assert_not_called()
        youtube.thumbnails.return_value.set.assert_not_called()
        youtube.playlists.return_value.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
