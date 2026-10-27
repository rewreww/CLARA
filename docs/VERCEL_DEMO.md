# CLARA respondent demo: Vercel + your computer

**Current setup uses Microsoft Dev Tunnels instead of ngrok. Follow
[MICROSOFT_TUNNEL.md](MICROSOFT_TUNNEL.md) for the current URL and commands.
The ngrok-specific steps below are retained only as an alternative.**

The frontend runs on Vercel. A Vercel routing middleware requires demo credentials,
then forwards API requests to ngrok with a separate gateway key. ngrok forwards only
to `127.0.0.1:8765`, the restricted gateway. The gateway reaches the existing .NET
service on 5000 and LLM service on 8001. PostgreSQL, PDFs, model services and Groq
credentials remain on the research computer. Requests and responses pass through
Vercel and ngrok; these services are not end-to-end opaque relays.

## 1. Create an ngrok account and install its Windows agent

1. Sign up at https://dashboard.ngrok.com/signup and verify your account.
2. Install ngrok using its official Windows instructions:
   https://ngrok.com/download/windows . The recommended Microsoft Store command is:

   ```powershell
   winget install ngrok -s msstore
   ```

3. In the ngrok dashboard, open **Your Authtoken** and follow its agent setup command:

   ```powershell
   ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
   ```

   Enter this on your own computer, not in chat or Git. The token is for the ngrok
   agent only, and is NOT any of the Vercel variables below.
4. Find the assigned development domain under the dashboard's **Domains** section.
   Use that exact HTTPS domain for the tunnel. A free assigned domain is sufficient
   to start testing; check your account's request and data-transfer quotas before
   inviting a group. No paid subscription or custom domain has been purchased.

## 2. Start the local services for an evaluation session

In PowerShell at `C:\clara-system`:

```powershell
.\start-clara.ps1 -NoBrowser
.\start-demo-gateway.ps1
```

The gateway occupies this terminal. Keep it open. Its private key is loaded from
`.clara/deployment/gateway.env`. It listens only on loopback and fails to start if
the key is absent or too short. On another computer, install gateway dependencies
with `.\.venv\Scripts\python.exe -m pip install -r scripts/demo-requirements.txt` first.

In a second terminal, use your actual assigned domain:

```powershell
ngrok http http://127.0.0.1:8765 --url https://YOUR-ASSIGNED-DOMAIN.ngrok-free.app --inspect=false
```

Keep that terminal open too. `--inspect=false` disables the agent's local request
inspector. This does not promise that the hosting/tunnel providers retain no logs.
Do NOT tunnel Vite port 3000, .NET port 5000, LLM port 8001, the database, or the ML
service directly. Do not forward router ports.

Optional local verification, with the gateway running:

```powershell
.\.venv\Scripts\python.exe scripts/verify_demo_gateway.py
```

This checks authentication, patients, a known demo PDF range request and a completed
chat stream. It prints no record contents or credentials and clears its test chat.

## 3. Prepare the private Vercel variables

The setup has generated `.clara/deployment/vercel.env` on this computer. It is
ignored by Git. If setting up a fresh computer, run:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_demo.py
```

The script preserves existing secrets. Open `vercel.env` locally and replace only
the placeholder `CLARA_GATEWAY_URL` with the exact HTTPS ngrok domain, with no path.

The six variables are:

- `CLARA_DEMO_ENABLED`: `true` during testing. `false` closes the deployed demo.
- `VITE_RESPONDENT_DEMO`: `true`. Public build flag, not a secret. Disables ingestion
  log polling over the metered tunnel and enables the online-demo privacy notice.
- `CLARA_DEMO_USERNAME`: generated as `respondent`.
- `CLARA_DEMO_PASSWORD`: the generated respondent password.
- `CLARA_GATEWAY_KEY`: the generated private server-to-server key; it must exactly
  match `gateway.env`. Never give it to respondents.
- `CLARA_GATEWAY_URL`: your assigned HTTPS ngrok domain.

The two credentials have different purposes. Respondents receive only the demo
username/password. Do not prefix any secret with `VITE_`. Do not upload the Groq key,
database connection string, ngrok authtoken, `.env`, `.clara`, PDF backups or the
private name-removal dictionary to Vercel/Git.

## 4. Commit and push, then configure the Vercel website

Commit and push the reviewed source changes (including the phone layout, agreement,
name-removal code, middleware, package lock and `frontend/vercel.json`) to your Git
remote. The deployment cannot see changes that remain only on your computer.

1. Sign in at https://vercel.com and choose **Add New → Project**.
2. Connect your Git provider and import the CLARA repository.
3. Set **Root Directory** to `frontend`.
4. Select **Framework Preset: Vite**.
5. Confirm **Install Command: npm ci**, **Build Command: npm run build**, and
   **Output Directory: dist**. The committed `vercel.json` supplies these defaults.
6. Use Node.js **22.x** (also declared in `package.json`).
7. Add all six variables from the local file under **Environment Variables** for
   **Production**. If testing a Preview deployment, add the same variables to
   **Preview**, too. Mark the password and gateway key sensitive where available.
8. Click **Deploy**. If you imported before setting variables, add them under
   **Project → Settings → Environment Variables**, then **Deployments → Redeploy**.
9. Use the Production `https://...vercel.app` URL for respondents. In **Settings →
   Deployment Protection**, ensure that this Production URL does not require a
   Vercel team login. Leave Preview deployment protection enabled if desired. The
   app's own demo authentication must remain active.

No custom domain, redirect, manual API URL in frontend code, or CORS wildcard is
needed. `middleware.js` runs on Vercel before serving pages and rewrites API calls.
The local Vite proxy remains unchanged. The frontend uses hash-based navigation,
so no catch-all SPA rewrite is required.

## 5. Verify the actual hosted deployment before inviting respondents

- Open the Production link in a private browser window on a phone using mobile
  data. It must ask for the demo username/password before showing CLARA.
- Enter the respondent credentials, then review/accept the CLARA agreement.
- Check patient selection, Overview, Discharge, laboratory sections, chat streaming,
  conversation reopening, source citations and PDF paging/zoom.
- A direct request to the ngrok API without the private gateway key must return 401.
- Confirm an unauthenticated private window cannot read the Vercel patient API.
- Stop the tunnel and check that records/chat become unavailable; restart it using
  the same domain. The Vercel frontend will remain online independently.
- Test with a small simultaneous group before a full session. The gateway permits
  four concurrent chats and 30 chat requests per minute across the demo. It does
  not guarantee capacity for an entire class at once.

Local checks do not validate Vercel's deployed middleware execution, ngrok, real
mobile keyboards or internet streaming. Those remain acceptance checks after the
accounts/domain are configured. Vercel documents a 120-second proxied-request limit;
test representative longer questions. The gateway does not buffer SSE or PDFs, but
the deployed network path must still be checked for stream latency and timeouts.

## Scheduled sessions and shutdown

Keep the computer awake, powered and connected, with PostgreSQL and CLARA running.
Use the existing approved demo dataset only. Newly added PDFs are not automatically
name-redacted. Respondent mode keeps ingestion logs private and does not auto-refresh
from ingestion events; refresh/reload the record if the researcher changes it.

After testing, press Ctrl+C in the ngrok and gateway terminals. This closes backend
access without stopping your usual local CLARA. To close the whole public interface,
set `CLARA_DEMO_ENABLED=false` in Vercel and redeploy. Redeploy after every variable
change, including a changed password or tunnel domain. Rotate the respondent password
between cohorts if needed. Browser Basic authentication is cached: use private windows
and close them after each participant. Saved conversations are browser-local and are
not a survey-response collection system.

## Troubleshooting

- **Setup incomplete (503):** missing/short variables, or a gateway URL without
  `https://`, with a path, or still containing the placeholder. Correct and redeploy.
- **Repeated login prompt:** check the demo username/password, not the gateway key.
- **Vercel team login:** you used a protected Preview URL or Production protection.
- **Gateway authentication required (401) after login:** the two gateway keys differ,
  or the deployment middleware did not run. Do not remove gateway authentication.
- **ngrok offline/502/503:** check the gateway/tunnel terminals and `status-clara.ps1`.
- **Chat 429:** wait for an active chat to finish or for the one-minute rate window.
- **Chat incomplete:** check upstream/Groq quota, internet connectivity and proxy timeout.
- **PDF missing:** verify the demo PDFs and their registered paths on this computer.

References: https://vercel.com/docs/frameworks/frontend/vite,
https://vercel.com/docs/routing-middleware/getting-started,
https://vercel.com/docs/limits,
https://ngrok.com/download/windows,
https://ngrok.com/docs/gateway/endpoints/http.
