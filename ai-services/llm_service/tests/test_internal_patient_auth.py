"""Local patient-service authentication must not leak to public model APIs."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mcp_tools


class InternalPatientAuthenticationTests(unittest.TestCase):
    def test_no_secret_in_legacy_mode(self):
        with patch.dict(os.environ, {"CLARA_INTERNAL_KEY": ""}):
            with patch.object(mcp_tools.requests, "get") as outgoing:
                mcp_tools.patient_service_get(mcp_tools.DATA_SERVICE_URL + "/Patient_12345678/mimic/context")
                self.assertEqual(outgoing.call_args.kwargs["headers"], {})

    def test_secret_only_for_loopback_patient_service(self):
        with patch.dict(os.environ, {"CLARA_INTERNAL_KEY": "unit-test-internal-key"}):
            with patch.object(mcp_tools.requests, "post") as outgoing:
                mcp_tools.patient_service_post(
                    mcp_tools.DATA_SERVICE_URL + "/vitals", json={"patient": "Patient_12345678"})
                self.assertEqual(outgoing.call_args.kwargs["headers"]["X-Clara-Internal-Key"],
                                 "unit-test-internal-key")

    def test_nonlocal_service_rejected_when_secret_present(self):
        with patch.dict(os.environ, {"CLARA_INTERNAL_KEY": "unit-test-internal-key"}):
            with patch.object(mcp_tools.requests, "get") as outgoing:
                with patch.object(mcp_tools, "DATA_SERVICE_URL", "https://example.invalid/patientdata"):
                    with self.assertRaises(ValueError):
                        mcp_tools.patient_service_get("https://example.invalid/patientdata/patients")
                outgoing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
