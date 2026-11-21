"""Offline checks: never contact Google and never upload anything."""
import json
import tempfile
import unittest
from pathlib import Path
from uploader import load_metadata, make_body

VALID = {
    "title": "Martin Luther — Gospel (1522)",
    "description": "The Gospel of salvation through faith in Jesus Christ alone.",
    "tags": ["Luther", "Gospel"],
    "categoryId": "27",
    "madeForKids": False,
    "containsSyntheticMedia": True,
}

class MetadataTests(unittest.TestCase):
    def check(self, obj):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "video.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            return load_metadata(path)

    def test_valid(self):
        meta = self.check(VALID)
        body = make_body(meta, "public")
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(body["status"]["containsSyntheticMedia"])

    def test_description_limit(self):
        obj = dict(VALID, description="x"*5001)
        with self.assertRaisesRegex(ValueError, "5,000"):
            self.check(obj)
        self.check(dict(VALID, description="x"*5000))

    def test_title_limit(self):
        with self.assertRaises(ValueError):
            self.check(dict(VALID, title="a"*101))

    def test_no_implicit_audience_setting(self):
        obj = dict(VALID)
        del obj["madeForKids"]
        with self.assertRaisesRegex(ValueError, "madeForKids"):
            self.check(obj)

    def test_no_invalid_visibility(self):
        with self.assertRaisesRegex(ValueError, "Visibility"):
            make_body(self.check(VALID), "PUBLIC")

    def test_untrusted_tags(self):
        with self.assertRaises(ValueError):
            self.check(dict(VALID, tags=["<script>"]))

    def test_approved_luther_metadata(self):
        path = Path(__file__).parent / "metadata" / "luther_1522.json"
        if path.is_file():
            meta = load_metadata(path)
            self.assertEqual(len(meta["description"]), 4588)
            self.assertIn("seekingthechrist114@gmail.com", meta["description"])
            self.assertIn("THE GOSPEL OF JESUS CHRIST", meta["description"])
            self.assertIn("HISTORICAL AND THEOLOGICAL DISCLAIMER", meta["description"])

if __name__ == "__main__":
    unittest.main()
