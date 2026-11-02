"""Keep the existing protected demo tunnel online; run via Windows Task Scheduler."""
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from dotenv import dotenv_values
from clara_launcher import WindowsJob, alive, healthy, port_open, read_state

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.clara' / 'deployment'


def probe(client, url, key=None, expected=None):
    headers = {'X-Tunnel-Skip-AntiPhishing-Page': '1'}
    if key:
        headers['x-clara-gateway-key'] = key
    try:
        response = client.get(url, headers=headers)
        if response.status_code != 200:
            return False
        if expected is None:
            return True
        value = response.json().get(expected[0])
        return isinstance(value, expected[1]) if isinstance(expected[1], type) else value == expected[1]
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


class Child:
    """Own a Windows job, including venv redirector children. Never kill by port."""
    def __init__(self, name, command):
        self.name, self.command = name, command
        self.process = self.job = self.log = None
        self.last_start = 0

    def running(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.job:
            self.job.close()
            self.job = None
        if self.process:
            self.process.wait(timeout=15)
            self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def start(self):
        if self.running() or time.monotonic() - self.last_start < 60:
            return
        self.stop()
        path = RUNTIME / (self.name + '.log')
        if path.exists() and path.stat().st_size > 2_000_000:
            os.replace(path, path.with_suffix('.previous.log'))
        self.log = path.open('ab')
        self.job = WindowsJob()
        self.process = subprocess.Popen(
            self.command, cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=self.log, stderr=self.log, creationflags=subprocess.CREATE_NO_WINDOW)
        self.job.assign(self.process)
        self.last_start = time.monotonic()
        logging.info('Started %s', self.name)


def restart_due(failures, started, now):
    return failures >= 3 and now - started >= 120


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    lock = (RUNTIME / 'watchdog.lock').open('a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        return 0
    handler = RotatingFileHandler(RUNTIME / 'watchdog.log', maxBytes=1_000_000, backupCount=2)
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    config = json.loads((RUNTIME / 'watchdog.json').read_text(encoding='utf-8-sig'))
    values = dotenv_values(RUNTIME / 'vercel.env')
    key = dotenv_values(RUNTIME / 'gateway.env').get('CLARA_GATEWAY_KEY', '')
    if len(key) < 32 or values.get('CLARA_GATEWAY_KEY') != key:
        raise ValueError('Gateway configuration is missing or inconsistent.')
    public = values['CLARA_GATEWAY_URL'].rstrip('/')
    if not public.startswith('https://') or public != config['gateway_url'].rstrip('/'):
        raise ValueError('Saved tunnel URL does not match the verified watchdog configuration.')
    gateway = Child('gateway', [sys.executable, str(ROOT / 'scripts/demo_gateway.py')])
    tunnel = Child('tunnel', [config['devtunnel'], 'host', config['tunnel_id']])
    failures = {'gateway': 0, 'tunnel': 0}
    next_core = next_renew = 0
    previous = None
    logging.info('Demo watchdog started')
    try:
        with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
            while not (RUNTIME / 'watchdog.stop').exists():
                now = time.monotonic()
                # Start the normal launcher after login or a full managed-service exit.
                # An active/unhealthy launcher or an unrelated port owner is left alone.
                if now >= next_core:
                    next_core = now + 120
                    state = read_state()
                    if not alive(state) and not any(port_open(p) for p in (5000, 8001, 8002, 3000)):
                        logging.info('Starting local CLARA services')
                        with (RUNTIME / 'core-start.log').open('ab') as log:
                            try:
                                subprocess.run([sys.executable, str(ROOT / 'scripts/clara_launcher.py'),
                                                'start', '--no-browser'], cwd=ROOT, stdout=log, stderr=log,
                                               stdin=subprocess.DEVNULL, timeout=900,
                                               creationflags=subprocess.CREATE_NO_WINDOW, check=False)
                            except subprocess.TimeoutExpired:
                                logging.error('Local CLARA startup timed out')
                if now >= next_renew:
                    try:
                        result = subprocess.run([config['devtunnel'], 'update', config['tunnel_id'],
                                                 '--expiration', '30d'], stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                                timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
                        renewed = result.returncode == 0
                    except (OSError, subprocess.TimeoutExpired):
                        renewed = False
                    next_renew = time.monotonic() + (86400 if renewed else 300)
                    logging.info('Tunnel expiry renewal: %s', 'success' if renewed else 'retry pending')
                local_ok = probe(client, 'http://127.0.0.1:8765/health', key, ('status', 'gateway_ready'))
                failures['gateway'] = 0 if local_ok else failures['gateway'] + 1
                if not local_ok:
                    if gateway.running() and restart_due(failures['gateway'], gateway.last_start, time.monotonic()):
                        logging.warning('Restarting unresponsive owned gateway')
                        gateway.stop()
                    if not port_open(8765):
                        gateway.start()
                public_ok = probe(client, public + '/health', key, ('status', 'gateway_ready')) if local_ok else False
                failures['tunnel'] = 0 if public_ok or not local_ok else failures['tunnel'] + 1
                if local_ok and not public_ok:
                    if tunnel.running() and restart_due(failures['tunnel'], tunnel.last_start, time.monotonic()):
                        logging.warning('Reconnecting unresponsive owned tunnel')
                        tunnel.stop()
                    tunnel.start()
                online_ok = probe(client, config['vercel_url'].rstrip('/') + '/api/backend/patientdata/patients',
                                  expected=('patients', list)) if public_ok else False
                status = {'gateway': local_ok, 'tunnel': public_ok, 'vercel_api': online_ok,
                          'backend': healthy('backend'), 'llm': healthy('llm')}
                if status != previous:
                    logging.info('Health: %s', status)
                    previous = status
                (RUNTIME / 'watchdog-status.json').write_text(
                    json.dumps({'checked_at': time.time(), **status}, indent=2), encoding='utf-8')
                for _ in range(30):
                    if (RUNTIME / 'watchdog.stop').exists():
                        break
                    time.sleep(1)
    finally:
        tunnel.stop()
        gateway.stop()
        lock.close()
        logging.info('Demo watchdog stopped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
