import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "outreach_watch", Path(__file__).parents[1] / "scripts" / "outreach_watch.py"
)
watch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(watch)


class OutreachWatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = root / "threads.json"
        self.state = root / "state.json"
        self.reports = root / "reports"
        self.config.write_text(json.dumps({"threads": [{"owner": "acme", "repo": "tools", "issue": 7, "ignore_comment_ids_up_to": 10}]}))

    def tearDown(self):
        self.temp.cleanup()

    def test_writes_verbatim_reply_and_persists_seen_id(self):
        comments = [
            {"id": 11, "user": {"login": "alice"}, "body": "Exact **reply**\nline two", "html_url": "https://example/11", "created_at": "2026-08-22T01:00:00Z"},
            {"id": 12, "user": {"login": watch.IGNORE_AUTHOR}, "body": "ours"},
        ]
        with patch.object(watch, "fetch_comments", return_value=comments):
            self.assertEqual(watch.run(self.config, self.state, self.reports), 0)
        files = list(self.reports.glob("OUTREACH-REPLY_*.md"))
        self.assertEqual(len(files), 1)
        self.assertIn("Exact **reply**\nline two", files[0].read_text())
        self.assertEqual(json.loads(self.state.read_text())["seen_ids"], [11])

    def test_poll_failure_writes_drive_failure_file(self):
        with patch.object(watch, "fetch_comments", side_effect=TimeoutError("slow network")):
            self.assertEqual(watch.run(self.config, self.state, self.reports), 1)
        failure = next(self.reports.glob("OUTREACH-WATCH-FAILURE_*.md"))
        self.assertIn("slow network", failure.read_text())


if __name__ == "__main__":
    unittest.main()
