import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from name_privacy import sanitize_name_text, sanitize_conversations


class NamePrivacyTests(unittest.TestCase):
    def test_names_removed_but_clinical_content_and_links_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.json"
            path.write_text(json.dumps({"names": ["EXAMPLE, ALEX"], "tokens": ["EXAMPLE", "ALEX"]}))
            with patch.dict(os.environ, {"NAME_REDACTION_DICTIONARY": str(path)}):
                original = [{"id": "session_123", "patientId": "00001", "title": "Alex's labs", "messages": [
                    {"role": "clara", "text": "EXAMPLE,\nALEX: creatinine 1.16 mg/dL on 2024-12-03.",
                     "sources": [{"source": "labs/report.pdf", "page": 1}]}]}]
                cleaned = sanitize_conversations(original)
                self.assertNotIn("ALEX", cleaned[0]["messages"][0]["text"])
                self.assertIn("creatinine 1.16 mg/dL on 2024-12-03.", cleaned[0]["messages"][0]["text"])
                self.assertEqual(cleaned[0]["id"], original[0]["id"])
                self.assertEqual(cleaned[0]["patientId"], "00001")
                self.assertEqual(cleaned[0]["messages"][0]["sources"], original[0]["messages"][0]["sources"])
                self.assertIn("EXAMPLE", original[0]["messages"][0]["text"])
                self.assertEqual(sanitize_name_text("examples and alexithymia"), "examples and alexithymia")


if __name__ == "__main__":
    unittest.main()
