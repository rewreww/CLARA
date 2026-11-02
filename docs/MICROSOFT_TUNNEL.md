# Current demo setup: Microsoft Dev Tunnels + Vercel

This replaces the ngrok setup in VERCEL_DEMO.md. Do not install ngrok or disable
antivirus protections. The gateway key remains enabled; respondent sign-in has been
removed. Anyone with the Vercel link can access the demo after the agreement modal.
The agreement is a UI acknowledgment, not API authentication.

## Current connection

The gateway is running on `127.0.0.1:8765`. The current public URL is:
`https://jh62xh37-8765.asse.devtunnels.ms`.

The private `.clara/deployment/vercel.env` has been updated to use this URL.
No password or gateway key has changed.

The saved tunnel ID is `jolly-fog-g03v56m.asse`. Reuse this tunnel to preserve
the URL configured in Vercel. Do not run `devtunnel host -p 8765` without an ID:
that creates a new temporary tunnel and can break the deployed URL.

As of October 31, 2026, the Windows scheduled task **CLARA Demo Watchdog** runs
the gateway and this tunnel in the background. It checks health every roughly
30 seconds (plus request timeouts), restarts its failed processes, renews tunnel
expiration daily, and starts CLARA after login if its service ports are free.
It checks the actual Vercel patient API too, without logging response contents.
Three failed checks and at
least two minutes of runtime are required before restarting an unresponsive
process. It does not terminate unrelated processes or restart an active but
unhealthy CLARA launcher; inspect the local service logs in that case.

Plugged-in idle sleep, hibernation, and lid-close sleep are disabled on the
configured power plan. Display timeout and battery settings are unchanged.
Keep the laptop plugged in, ventilated, connected to the internet, and signed
in to Windows. Locking Windows or turning the screen off is fine. Explicitly
selecting Sleep, signing out, shutting down, or losing power/internet still
interrupts the service. After reboot, sign in so the task can resume. A local
tunnel cannot serve requests while its host is asleep.

## Finish on Vercel

1. Commit and push the reviewed changes, including `frontend/middleware.js`,
   `frontend/vercel.json`, package files and the agreement update.
2. Import the Git repository into Vercel. Set Root Directory to `frontend`,
   Framework to Vite, Node.js to 22.x, Install Command to `npm ci`, Build Command
   to `npm run build`, Output Directory to `dist`.
3. Copy the variables from `.clara/deployment/vercel.env` into Vercel's
   Production environment variables. Do not commit the private file.
4. Deploy. If the project already exists, update the variables and redeploy the
   latest pushed commit. Preview deployments require their own variable scope.
5. Open the Production URL in a private browser window. It should show the CLARA
   agreement directly. If Vercel asks for a team login, check Production Deployment
   Protection. `CLARA_DEMO_USERNAME` and `CLARA_DEMO_PASSWORD` are no longer used
   and can be removed from Vercel. Keep the other four variables.
6. Verify patients, chat, and PDFs on a phone using mobile data before distributing
   the Vercel link. Share only that link, never the gateway key or Microsoft account
   credentials.

## Background operation

The task starts at login and is retried every five minutes if it has exited.
To inspect it:

```powershell
cd C:\clara-system
Get-ScheduledTask -TaskName 'CLARA Demo Watchdog'
Get-Content .clara\deployment\watchdog-status.json
Get-Content .clara\deployment\watchdog.log -Tail 20
.\status-clara.ps1
```

Health status is timestamped with `checked_at` (Unix seconds); an old timestamp
means monitoring itself stopped. Logs and credentials stay in ignored `.clara/`.
The verified machine-specific configuration is `.clara/deployment/watchdog.json`.
To reinstall the task on this configured laptop:

```powershell
.\scripts\install-demo-watchdog.ps1 -KeepAwakeOnAC
```

To stop automatic hosting and restore the original AC power settings:

```powershell
.\scripts\uninstall-demo-watchdog.ps1 -RestorePowerSettings
```

The local CLARA services remain running until `stop-clara.ps1` is used.
For manual recovery after removing the task, run `start-clara.ps1 -NoBrowser`,
then `start-demo-gateway.ps1`, and in another terminal run
`devtunnel host jolly-fog-g03v56m.asse`. Both manual terminals must remain open.
The tunnel permits anonymous transport but the gateway still requires its
private key. Do not tunnel the backend, LLM, database or Vite server directly.

After updating the local private URL, a public-path check is available:

```powershell
.\.venv\Scripts\python.exe scripts/verify_demo_gateway.py --public
```

Remove the watchdog (or stop the manual terminals with Ctrl+C) to stop hosting. Change
`CLARA_DEMO_ENABLED` to `false` and redeploy if you also want to close the Vercel
interface. Actual hosted Vercel routing and phone behavior must be checked after
deployment even when the tunnel test passes.

Microsoft reference:
https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/cli-commands
