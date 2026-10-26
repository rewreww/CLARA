"""Windows local service launcher. Runtime state and logs stay in .clara/.

One detached supervisor holds a Windows Job Object. Only processes it launches
are assigned to that job; closing it terminates those processes and descendants.
Stop requests are token-scoped files, never process-name or port-based kills.
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".clara"
STATE = RUNTIME / "run.json"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
URL = "http://localhost:3000"


class LauncherError(Exception):
    pass


class WindowsJob:
    """Kill-on-close ownership including children such as esbuild/notifier."""
    def __init__(self):
        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            error = ctypes.WinError(ctypes.get_last_error())
            process.kill()
            process.wait()
            raise error

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def process_identity(pid):
    """Windows creation time prevents a recycled PID from counting as our runner."""
    if not pid:
        return None
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        api.CloseHandle(handle)


def read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as exc:
        raise LauncherError("Cannot read .clara/run.json. Preserve it and inspect the launcher logs.") from exc


def write_state(state):
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    # Windows readers (status/start, antivirus, editors) may briefly hold a handle
    # without FILE_SHARE_DELETE. Keep the update atomic, but retry that contention.
    for attempt in range(50):
        try:
            os.replace(temporary, STATE)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.04)


def alive(state):
    expected = state.get("identity")
    return expected is not None and process_identity(state.get("pid")) == expected


def stop_path(run_id):
    # Never use arbitrary paths from saved state.
    if str(uuid.UUID(run_id)) != run_id:
        raise LauncherError("Invalid launcher run identifier.")
    return RUNTIME / f"stop-{run_id}"


@contextlib.contextmanager
def command_lock():
    import msvcrt
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / "command.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise LauncherError("Another CLARA start/stop command is in progress.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def port_open(port, host="127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def response(path):
    with HTTP.open("http://127.0.0.1:" + path, timeout=2) as result:
        return result.read()


def healthy(name):
    try:
        if name == "backend":
            return isinstance(json.loads(response("5000/api/patientdata/patients")).get("patients"), list)
        if name == "ml":
            return json.loads(response("8002/health")).get("model_loaded") is True
        if name == "llm":
            return json.loads(response("8001/health")).get("service") == "CLARA LLM"
        if name == "frontend":
            return b'id="root"' in response("3000/")
        if name == "backend-proxy":
            return isinstance(json.loads(response("3000/api/backend/patientdata/patients")).get("patients"), list)
        if name == "llm-proxy":
            return json.loads(response("3000/api/llm/health")).get("service") == "CLARA LLM"
        if name == "legacy":
            return "/chemistry-results" in json.loads(response("8000/openapi.json")).get("paths", {})
        if name == "ollama":
            return isinstance(json.loads(response("11434/api/tags")).get("models"), list)
    except (OSError, ValueError):
        pass
    return False


def configured_database():
    # Match WebApplication defaults followed by Program.cs's local JSON override.
    environment = os.getenv("DOTNET_ENVIRONMENT", os.getenv("ASPNETCORE_ENVIRONMENT", "Production"))
    connection = None
    for filename in ("appsettings.json", f"appsettings.{environment}.json"):
        path = ROOT / "backend" / filename
        if path.exists():
            connection = json.loads(path.read_text(encoding="utf-8-sig")).get("ConnectionStrings", {}).get("ClaraDatabase", connection)
    connection = os.getenv("ConnectionStrings__ClaraDatabase", connection)
    local = ROOT / "backend/appsettings.Development.local.json"
    if local.exists():
        connection = json.loads(local.read_text(encoding="utf-8-sig")).get("ConnectionStrings", {}).get("ClaraDatabase", connection)
    if not connection:
        raise LauncherError("Set ConnectionStrings__ClaraDatabase or backend/appsettings.Development.local.json before starting.")
    # Tokenize quoted connection-string values without printing or persisting them.
    fields = {}
    pattern = r'(?:^|;)\s*([^=;]+)\s*=\s*("(?:[^"]|"")*"|\'(?:[^\']|\'\')*\'|[^;]*)'
    for match in re.finditer(pattern, connection):
        fields[match[1].strip().lower()] = match[2].strip().strip("\"'")
    return fields.get("host", fields.get("server", "localhost")).split(",")[0], int(fields.get("port", "5432"))


def preflight(args):
    if sys.platform != "win32":
        raise LauncherError("This launcher targets Windows. Use the manual runbook on other platforms.")
    required = ["uvicorn", "fastapi", "dotenv", "chromadb", "joblib", "pandas", "sklearn", "xgboost"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        raise LauncherError("Missing Python dependencies: " + ", ".join(missing) + ". Install ai-services/requirements.txt in .venv.")
    from dotenv import load_dotenv
    load_dotenv(ROOT / "ai-services/llm_service/.env")
    for executable in ("dotnet", "node"):
        if not shutil.which(executable):
            raise LauncherError(f"{executable} is not on PATH. Follow docs/README.md first-time setup.")
    node_version = subprocess.check_output(["node", "--version"], text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
    version = tuple(int(part) for part in node_version.lstrip("v").split("."))
    if version < (22, 13, 0):
        raise LauncherError("Node 22.13 or newer is required by the current PDF preview dependency.")
    for relative in ("frontend/node_modules/vite/bin/vite.js", "ai-services/ml_service/model.pkl",
                     "ai-services/ml_service/model_meta.json", "ai-services/ml_service/column_config.json"):
        if not (ROOT / relative).is_file():
            raise LauncherError(f"Missing {relative}. Complete first-time setup; startup does not reinstall or retrain automatically.")
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in ("gemini", "groq", "ollama", "huggingface", "hf"):
        raise LauncherError(f"Unsupported LLM_PROVIDER: {provider}")
    key = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}.get(provider)
    if key and not os.getenv(key, "").strip():
        raise LauncherError(f"Set {key} in ai-services/llm_service/.env or your environment. Its value will not be logged.")
    host, port = configured_database()
    if not port_open(port, host):
        raise LauncherError(f"PostgreSQL is not reachable at {host}:{port}. Start your PostgreSQL service, then retry.")
    needs_ollama = args.with_ollama or provider == "ollama" or os.getenv("RAG_EMBEDDING_PROVIDER", "").lower() == "ollama"
    if needs_ollama and not healthy("ollama") and not shutil.which("ollama"):
        raise LauncherError("Ollama is required by your selected provider but is not installed/running.")
    return provider, needs_ollama


def service_specs(args, needs_ollama):
    python = str(ROOT / ".venv/Scripts/python.exe")
    specs = [
        ("backend", 5000, ROOT / "backend", ["dotnet", "bin/Debug/net8.0/CLARA.Backend.dll", "--urls", "http://localhost:5000"]),
        ("ml", 8002, ROOT / "ai-services/ml_service", [python, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8002"]),
        ("llm", 8001, ROOT / "ai-services/llm_service", [python, "-m", "uvicorn", "llm_client:app", "--host", "127.0.0.1", "--port", "8001"]),
    ]
    if args.legacy_parser:
        specs.append(("legacy", 8000, ROOT / "ai-services", [python, "-m", "uvicorn", "medical_text_api:app", "--host", "127.0.0.1", "--port", "8000"]))
    specs.append(("frontend", 3000, ROOT / "frontend", ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "3000", "--strictPort"]))
    if needs_ollama and not healthy("ollama"):
        specs.insert(0, ("ollama", 11434, ROOT, ["ollama", "serve"]))
    return specs


def verify_ports(specs):
    for name, port, _, _ in specs:
        if port_open(port) or port_open(port, "::1"):
            raise LauncherError(f"Port {port} ({name}) is already in use outside this launcher. Stop that service first; it will not be killed or adopted.")


def supervise(args):
    state = read_state()
    if state.get("run_id") != args.run_id:
        return 1
    state.update(pid=os.getpid(), identity=process_identity(os.getpid()))
    write_state(state)
    request = stop_path(args.run_id)
    log_dir = Path(state["logs"])
    job = WindowsJob()
    processes = []
    handles = []

    def checkpoint():
        if request.exists():
            raise InterruptedError("Stop requested.")
        for name, process in processes:
            if process.poll() is not None:
                raise LauncherError(f"{name} exited (code {process.returncode}). See {log_dir / (name + '.stderr.log')}")

    def launch(name, cwd, command):
        stdout = (log_dir / f"{name}.stdout.log").open("wb")
        stderr = (log_dir / f"{name}.stderr.log").open("wb")
        handles.extend([stdout, stderr])
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(process)
        return process

    try:
        provider, needs_ollama = preflight(args)
        specs = service_specs(args, needs_ollama)
        verify_ports(specs)
        state["message"] = "Building backend"
        write_state(state)
        build_command = ["dotnet", "build", "CLARA.Backend.csproj", "--nologo"]
        if (ROOT / "backend/obj/project.assets.json").exists():
            build_command.append("--no-restore")
        build = launch("build", ROOT / "backend", build_command)
        deadline = time.monotonic() + args.timeout
        while build.poll() is None:
            checkpoint()
            if time.monotonic() > deadline:
                raise LauncherError("Backend build timed out. See build logs.")
            time.sleep(0.25)
        if build.returncode:
            raise LauncherError("Backend build failed. See build.stdout.log and build.stderr.log.")
        for name, port, cwd, command in specs:
            checkpoint()
            # Recheck just before launch, in case something claimed the port during the build.
            verify_ports([(name, port, cwd, command)])
            state["message"] = f"Starting {name}"
            write_state(state)
            process = launch(name, cwd, command)
            processes.append((name, process))
            state["services"].append({"name": name, "pid": process.pid, "port": port})
            write_state(state)
            deadline = time.monotonic() + args.timeout
            while not healthy(name):
                checkpoint()
                if time.monotonic() > deadline:
                    raise LauncherError(f"{name} readiness timed out. See its logs in {log_dir}")
                time.sleep(0.5)
            checkpoint()
        # Vite may still be warming up after its HTML endpoint is available.
        # Verify the browser's actual API paths with the same readiness budget.
        for name in ("backend-proxy", "llm-proxy"):
            state["message"] = f"Checking {name}"
            write_state(state)
            deadline = time.monotonic() + args.timeout
            while not healthy(name):
                checkpoint()
                if time.monotonic() > deadline:
                    raise LauncherError(f"{name} readiness timed out. Check frontend.stderr.log and service logs.")
                time.sleep(0.5)
            checkpoint()
        state.update(phase="ready", message=f"CLARA is ready ({provider})")
        write_state(state)
        while True:
            checkpoint()
            time.sleep(0.5)
    except InterruptedError:
        state.update(phase="stopped", message="CLARA stopped.")
    except Exception as exc:
        state.update(phase="failed", message=str(exc))
    finally:
        job.close()
        for _, process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        for handle in handles:
            handle.close()
        request.unlink(missing_ok=True)
        write_state(state)
    return 0 if state["phase"] == "stopped" else 1


def start(args):
    with command_lock():
        state = read_state()
        if alive(state):
            if state.get("phase") == "ready" and all(healthy(s["name"]) for s in state["services"]):
                present = {s["name"] for s in state["services"]}
                if (args.legacy_parser and "legacy" not in present) or (args.with_ollama and not healthy("ollama")):
                    raise LauncherError("CLARA is already running. Stop it first to change optional services.")
                print(f"CLARA is already running: {URL}\nLogs: {state['logs']}")
                if not args.no_browser and not args.check:
                    webbrowser.open(URL)
                return 0
            raise LauncherError("A CLARA run is active but not ready. Use status-clara.ps1 and stop-clara.ps1 before restarting.")
        provider, needs_ollama = preflight(args)
        specs = service_specs(args, needs_ollama)
        verify_ports(specs)
        if args.check:
            print(f"Preflight passed. Provider: {provider}. PostgreSQL reachable. Required ports are available.")
            return 0
        run_id = str(uuid.uuid4())
        logs = RUNTIME / "logs" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + run_id[:8])
        logs.mkdir(parents=True)
        state = {"run_id": run_id, "pid": None, "identity": None, "phase": "starting",
                 "message": "Starting supervisor", "logs": str(logs), "services": [],
                 "started_at": datetime.now(timezone.utc).isoformat()}
        write_state(state)
        command = [sys.executable, str(Path(__file__).resolve()), "_supervise", "--run-id", run_id, "--timeout", str(args.timeout)]
        if args.legacy_parser:
            command.append("--legacy-parser")
        if args.with_ollama:
            command.append("--with-ollama")
        with (logs / "supervisor.log").open("wb") as log:
            runner = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                      creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        print(f"Starting CLARA. Logs: {logs}", flush=True)
        complete = False
        try:
            previous = None
            deadline = time.monotonic() + args.timeout * (len(specs) + 4)
            while time.monotonic() < deadline:
                state = read_state()
                if state.get("message") != previous:
                    print(state.get("message", ""), flush=True)
                    previous = state.get("message")
                if state.get("phase") == "ready":
                    if runner.poll() is not None:
                        raise LauncherError("Supervisor exited during startup. See supervisor.log.")
                    complete = True
                    print(f"Open {URL}\nStop with .\\stop-clara.ps1", flush=True)
                    if not args.no_browser:
                        webbrowser.open(URL)
                    return 0
                if state.get("phase") in ("failed", "stopped") or runner.poll() is not None:
                    raise LauncherError(f"Startup did not complete. See {logs}")
                time.sleep(0.5)
            raise LauncherError("Startup timed out.")
        finally:
            if not complete and runner.poll() is None:
                stop_path(run_id).touch()
                try:
                    runner.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    # A venv executable can be a redirector with a real Python
                    # child. Target only this still-live Popen tree, not a name
                    # or a PID loaded from disk; killing just the redirector
                    # could leave the supervisor and its job running.
                    if runner.poll() is None:
                        subprocess.run(["taskkill", "/PID", str(runner.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                        runner.wait(timeout=10)


def stop():
    with command_lock():
        state = read_state()
        if not alive(state):
            print("No launcher-managed CLARA run is active. Existing unrelated services were left alone.")
            return 0
        request = stop_path(state["run_id"])
        request.touch()
        print("Stopping CLARA's managed processes...", flush=True)
        deadline = time.monotonic() + 30
        while alive(state) and time.monotonic() < deadline:
            time.sleep(0.25)
        if alive(state):
            raise LauncherError("Stop is still pending. Check supervisor.log; no unrelated processes were killed.")
        request.unlink(missing_ok=True)
        print("CLARA stopped. PostgreSQL and externally started services were left running.")
        return 0


def status():
    state = read_state()
    if not alive(state):
        print("CLARA launcher is not running.")
        if state:
            print(f"Last result: {state.get('message')}\nLogs: {state.get('logs')}")
        return 1
    print(f"CLARA: {state['phase']}\nLogs: {state['logs']}")
    ready = state["phase"] == "ready"
    for service in state["services"]:
        ok = healthy(service["name"])
        ready = ready and ok
        print(f"  {service['name']}: {'ready' if ok else 'not ready'} (port {service['port']})")
    if ready:
        ready = healthy("backend-proxy") and healthy("llm-proxy")
        print(f"  frontend API proxies: {'ready' if ready else 'not ready'}")
    return 0 if ready else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status", "_supervise"))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--legacy-parser", action="store_true")
    parser.add_argument("--with-ollama", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        if sys.platform != "win32":
            raise LauncherError("This launcher requires Windows.")
        if args.action == "_supervise":
            return supervise(args)
        if args.action == "start":
            return start(args)
        return stop() if args.action == "stop" else status()
    except KeyboardInterrupt:
        print("\nStartup cancelled.")
        return 130
    except (LauncherError, OSError, ValueError) as exc:
        print(f"CLARA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
