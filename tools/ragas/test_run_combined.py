"""Offline smoke tests for the RAGAS combined progress log. No API calls."""
import json
import tempfile
import unittest
from pathlib import Path

from run_combined import state, METRICS

class RagasCombinedTests(unittest.TestCase):
    def test_preserves_existing_nemotron_score_and_uses_groq_for_missing_metric(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "capture.jsonl"
            nemotron = root / "nemotron.jsonl"
            groq = root / "groq.jsonl"
            capture.write_text(json.dumps({
                "id": "Q001", "status": "completed", "ragas_ready": True,
                "retrieved_contexts": ["source"]
            }) + "\n", encoding="utf-8")
            nemotron.write_text(json.dumps({
                "id": "Q001", "metric": "context_recall", "status": "scored",
                "score": 0.5, "provider": "openrouter", "model": "nemotron"
            }) + "\n", encoding="utf-8")
            groq.write_text("\n".join([
                json.dumps({"id": "Q001", "metric": "context_recall", "status": "scored",
                            "score": 1.0, "provider": "groq", "model": "gpt-oss-20b"}),
                json.dumps({"id": "Q001", "metric": "context_precision", "status": "failed",
                            "error": "429", "provider": "groq", "model": "gpt-oss-20b"}),
                json.dumps({"id": "Q001", "metric": "context_precision", "status": "scored",
                            "score": 0.75, "provider": "groq", "model": "gpt-oss-120b"})
            ]) + "\n", encoding="utf-8")
            captured, latest, scored = state(capture, nemotron, groq)
            self.assertIn("Q001", captured)
            self.assertEqual(len(scored), 2)
            self.assertEqual(scored[("Q001", "context_recall")]["score"], 0.5)
            self.assertEqual(scored[("Q001", "context_precision")]["score"], 0.75)
            self.assertEqual(scored[("Q001", "context_precision")]["model"], "gpt-oss-120b")

if __name__ == "__main__":
    unittest.main()
