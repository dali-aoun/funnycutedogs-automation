import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_meta import problems

GOOD_SHORT = {
    "title": "Rex Saw The Rain", "script": "One paw out. Retreat.", "keywords": ["doberman"],
    "description": "Fun.\nhttps://funnycutedogs.com/go/dogtraining\nSome links are affiliate links.",
}


def check(meta, kind="short", clips=False):
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        if clips:
            (d / "own_clips").mkdir()
            (d / "own_clips" / "a.mp4").write_bytes(b"")
        return problems(d, kind)


class CheckMeta(unittest.TestCase):
    def test_good_short_passes(self):
        self.assertEqual(check(GOOD_SHORT), [])

    def test_missing_disclosure_fails(self):
        meta = {**GOOD_SHORT, "description": "See https://funnycutedogs.com/go/dogtraining"}
        self.assertTrue(any("disclosure" in p for p in check(meta)))

    def test_long_script_too_short_fails(self):
        self.assertTrue(any("60 s" in p for p in check({**GOOD_SHORT, "script": "word " * 50}, kind="long")))

    def test_own_clips_without_files_fails(self):
        self.assertTrue(any("own_clips" in p for p in check({**GOOD_SHORT, "ownClips": True})))
        self.assertEqual(check({**GOOD_SHORT, "ownClips": True}, clips=True), [])

    def test_ai_video_needs_label(self):
        self.assertTrue(any("aigenerated" in p for p in check({**GOOD_SHORT, "aiGenerated": True})))


if __name__ == "__main__":
    unittest.main()
