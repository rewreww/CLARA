"""Launcher ownership and preflight regression tests; no CLARA services or DB writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("clara_launcher", Path(__file__).resolve().parents[1] / "clara_launcher.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_atomic_state_update_retries_windows_reader_contention(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "run.json"
            original_replace = launcher.os.replace
            calls = []

            def replace(source, target):
                calls.append(target)
                if len(calls) == 1:
                    raise PermissionError("Windows reader still has the file open")
                original_replace(source, target)

            with patch.object(launcher, "STATE", state_path), patch.object(launcher.os, "replace", side_effect=replace):
                launcher.write_state({"phase": "ready"})
                self.assertEqual(launcher.read_state(), {"phase": "ready"})
            self.assertEqual(len(calls), 2)

    def test_recycled_pid_does_not_count_as_owned(self):
        with patch.object(launcher, "process_identity", return_value=456):
            self.assertFalse(launcher.alive({"pid": 1, "identity": 123}))
            self.assertTrue(launcher.alive({"pid": 1, "identity": 456}))
            self.assertFalse(launcher.alive({"pid": 1}))

    def test_control_path_rejects_arbitrary_paths(self):
        for value in ("../../outside", "C:\\outside", ""):
            with self.assertRaises((ValueError, launcher.LauncherError)):
                launcher.stop_path(value)

    def test_foreign_listener_is_rejected_without_killing(self):
        with patch.object(launcher, "port_open", return_value=True):
            with self.assertRaisesRegex(launcher.LauncherError, "will not be killed or adopted"):
                launcher.verify_ports([("backend", 5000, Path("."), [])])

    def test_database_precedence_and_quoted_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "backend").mkdir()
            (root / "backend/appsettings.json").write_text(json.dumps({"ConnectionStrings": {
                "ClaraDatabase": "Host=base;Port=5432;Password='fake;Host=wrong'"
            }}))
            with patch.object(launcher, "ROOT", root), patch.dict("os.environ", {
                "ConnectionStrings__ClaraDatabase": "Host=environment;Port=5433",
                "DOTNET_ENVIRONMENT": "Audit"
            }):
                self.assertEqual(launcher.configured_database(), ("environment", 5433))
                (root / "backend/appsettings.Development.local.json").write_text(json.dumps({
                    "ConnectionStrings": {"ClaraDatabase": "Host=local;Port=5434;Password=\"fake;Host=wrong\""}
                }))
                self.assertEqual(launcher.configured_database(), ("local", 5434))

    def test_optional_services_do_not_adopt_external_ollama(self):
        args = argparse.Namespace(legacy_parser=False)
        with patch.object(launcher, "healthy", return_value=True):
            names = [s[0] for s in launcher.service_specs(args, True)]
            self.assertEqual(names, ["backend", "ml", "llm", "frontend"])
        args.legacy_parser = True
        with patch.object(launcher, "healthy", return_value=False):
            names = [s[0] for s in launcher.service_specs(args, True)]
            self.assertEqual(names, ["ollama", "backend", "ml", "llm", "legacy", "frontend"])

    @unittest.skipUnless(sys.platform == "win32", "Windows process ownership test")
    def test_job_closes_descendants_but_preserves_unrelated_process(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = Path(directory) / "go"
            child_info = Path(directory) / "child.json"
            code = (
                "import pathlib,subprocess,sys,time,json;"
                "gate=pathlib.Path(sys.argv[1]);"
                "\nwhile not gate.exists(): time.sleep(.05)\n"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "pathlib.Path(sys.argv[2]).write_text(json.dumps({'pid':child.pid}));"
                "time.sleep(60)"
            )
            job = launcher.WindowsJob()
            owned = subprocess.Popen([sys.executable, "-c", code, str(gate), str(child_info)],
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"],
                                         creationflags=subprocess.CREATE_NO_WINDOW)
            child_pid = None
            try:
                job.assign(owned)
                gate.touch()
                deadline = time.monotonic() + 10
                while not child_info.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                child_pid = json.loads(child_info.read_text())["pid"]
                child_identity = launcher.process_identity(child_pid)
                self.assertIsNotNone(child_identity)
                job.close()
                owned.wait(timeout=10)
                deadline = time.monotonic() + 10
                while launcher.process_identity(child_pid) == child_identity and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertIsNone(launcher.process_identity(child_pid))
                self.assertIsNone(unrelated.poll())
            finally:
                job.close()
                if owned.poll() is None:
                    owned.kill()
                owned.wait(timeout=10)
                unrelated.kill()
                unrelated.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
