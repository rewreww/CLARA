# Current demo setup: Microsoft Dev Tunnels + Vercel

This replaces the ngrok setup in VERCEL_DEMO.md. Do not install ngrok or disable
antivirus protections. The gateway key remains enabled; respondent sign-in has been
removed. Anyone with the Vercel link can access the demo after the agreement modal.
The agreement is a UI acknowledgment, not API authentication.

## Current connection

The gateway is running on `127.0.0.1:8765`. The current public URL is:
`https://7rp78j6f-8765.asse.devtunnels.ms`.

The private `.clara/deployment/vercel.env` has been updated to use this URL.
No password or gateway key has changed.

Keep the gateway and `devtunnel host` terminals open, and keep your computer awake.
This is a temporary tunnel: after restarting it, use the newly printed HTTPS
forwarding URL if it changes, update `CLARA_GATEWAY_URL` in Vercel and redeploy.
Use the forwarding URL, never the `-inspect` URL.

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

## Local commands for another session

First PowerShell terminal:

```powershell
cd C:\clara-system
.\start-clara.ps1 -NoBrowser
.\start-demo-gateway.ps1
```

Second terminal:

```powershell
devtunnel host -p 8765 --allow-anonymous
```

`--allow-anonymous` permits Vercel to reach the tunnel without Microsoft login.
The local gateway still rejects requests without its private key. Do not tunnel
the underlying backend, LLM, database or Vite development server directly.

After updating the local private URL, a public-path check is available:

```powershell
.\.venv\Scripts\python.exe scripts/verify_demo_gateway.py --public
```

Stop the gateway and tunnel with Ctrl+C after testing. Change
`CLARA_DEMO_ENABLED` to `false` and redeploy if you also want to close the Vercel
interface. Actual hosted Vercel routing and phone behavior must be checked after
deployment even when the tunnel test passes.

Microsoft reference:
https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/cli-commands
