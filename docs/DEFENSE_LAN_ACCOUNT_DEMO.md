# CLARA final-defense LAN setup (two phases)

The **CLARA host and doctor's interface are the same Windows laptop**. The administrator uses one phone. Both are connected through an internetless Wi-Fi router only during the account-management phase. Afterwards the laptop switches Wi-Fi to a teammate's internet hotspot for API-based LLM inference, while the doctor keeps using `http://localhost:3000`.

This setup needs **no Vercel**, external email, cloud account provider or Ethernet cable. AI inference still needs internet because the currently configured LLM provider uses an external API. Use synthetic or explicitly approved de-identified clinical records in the demo.

## Before the defense

- Back up PostgreSQL. Do not commit private configuration, personal data, passwords or API keys.
- Update the dedicated review branch on your Windows laptop. The existing scripts continue working without account mode.
- Configure the PostgreSQL connection in your existing private CLARA configuration.
- Prepare the first administrator **once**. In PowerShell, before starting CLARA for the first time, set a private username and strong password in the **current terminal session**, for example:

  ```powershell
  cd C:\clara-system
  $env:ClaraAuth__BootstrapUsername = "hospitaladmin"
  $env:ClaraAuth__BootstrapPassword = Read-Host "Choose first administrator password"
  .\start-clara.ps1 -WithAccounts
  ```

  The password must be at least 12 characters. The backend stores its *hash* in PostgreSQL. After the first successful bootstrap, remove the bootstrap password from that terminal's environment (`Remove-Item Env:ClaraAuth__BootstrapPassword`); it is no longer needed for subsequent starts. Do not share the password with thesis respondents or paste it in chat.

- For later runs, simply execute ` .\start-clara.ps1 -WithAccounts ` (without bootstrap credentials); stop normally using ` .\stop-clara.ps1 `.
- The `-WithAccounts` flag starts:
  - **Doctor / clinical CLARA**: `http://localhost:3000` on the hosting laptop only.
  - **Admin Console**: `http://localhost:3001` on the hosting laptop and `http://<YOUR-LAPTOP-LAN-IP>:3001` on the phone connected to the same Wi-Fi.
  - PostgreSQL, ASP.NET Core API and AI services continue on local-only interfaces.
- On Windows, set the router's network to **Private** and allow only inbound TCP **3001** through Windows Defender Firewall for the Private profile (preferably restricted to the router's local subnet). **Never open ports 5000, 8001, 8002 or PostgreSQL to the LAN.** Keep your router's **client/AP isolation disabled**, disable WAN port forwarding and use a strong WPA2/WPA3 SSID password.
- Determine the server's Wi-Fi IP with `ipconfig` (look for the IPv4 address under the Wi-Fi adapter). Phone address should be `http://<IP>:3001/`, **not** `localhost:3001`.
- If the admin page doesn't load, first check firewall, network profile, router client isolation and that you used the Wi-Fi IPv4 address, not a hotspot/VPN address.
- This authentication demo uses **HTTP on a closed test LAN only** so the phone can sign in without hospital-issued certificates. It is **not a production healthcare configuration**. Real deployment requires trusted HTTPS, administrator MFA and patient-by-patient access controls.

## Phase 1 — Authorization, offline router

1. Connect the Windows laptop and the admin phone to the **same offline router SSID**. Turn off the phone's mobile-data fallback if it refuses to use Wi-Fi without internet.
2. Start ` .\start-clara.ps1 -WithAccounts ` on the laptop.
3. On the phone, visit `http://<LAPTOP-IP>:3001/`. Log in as the administrator.
4. In **User Management**, create a clinician account. The app generates a **single-use 24-hour activation code**; deliver it securely. No email or external service is involved.
5. On the laptop, open `http://localhost:3000`, select **Activate a staff account**, enter the code and choose the doctor's password. Sign in.
6. For a recovery demonstration, the admin verifies the doctor and presses **Recovery** in the account list; the code lasts 20 minutes. On the laptop the doctor uses **Forgot password** with the new code.
7. Demonstrate that the doctor's account cannot access admin-only routes. Accounts and chat history are persisted in the local PostgreSQL database.

## Phase 2 — External LLM via hotspot

1. Keep all local CLARA services running. Disconnect the **laptop** from the offline-router Wi-Fi and connect it to your groupmate's internet hotspot.
2. The admin phone will no longer reach the laptop through the offline router. **That is expected**; administrative actions are already complete.
3. Continue using **the same laptop** at `http://localhost:3000`. The doctor's signed-in cookie stays tied to localhost, not the changing Wi-Fi address, so it should remain valid. The backend and PostgreSQL remain on the same device.
4. With the hotspot connected, CLARA's **server-side API key** calls OpenRouter/Groq (or another selected external LLM). Ask a question using synthetic/de-identified records.
5. Refresh the browser and reopen the conversation to demonstrate **account-bound saved chat history**.

## Safety checks before the panel arrives

- On a private browser window and before login, patient and AI APIs must reject requests. Accessing `http://localhost:3000` must show the login screen.
- Test doctor activation, login, account recovery and chat persistence **while the laptop is still on the offline router** (no email/API internet dependency).
- Test the phone on Wi-Fi and admin login through LAN IP. Check login cookies and that private API routes remain inaccessible from the phone except via authorized admin endpoints.
- Test switching the laptop from router Wi-Fi to hotspot Wi-Fi **without restarting services or signing out**.
- Test an LLM completion using the hotspot **before** the defense. Internet access is used only for the external AI inference, not for local authentication/database operations.
- Record an offline fallback demonstration (screenshots of the login/admin screens and a synthetic chat) in case the hotspot or API provider fails.
- Do not use actual hospital patient data in this development-mode HTTP demonstration.

## Known release gates

- The account feature's initial review branch was assembled without passing ASP.NET build + device-level verification. Use `dotnet build backend/CLARA.Backend.csproj`, `cd frontend; node --test; npm run build` and the real two-device scenario before committing to this setup.
- First account bootstrap requires an existing PostgreSQL connection and a working new account migration. This migration adds tables; it does not replace patient tables.
- The current UI offers clinician and administrator roles; additional roles may exist for future clinical policy. Real hospitals require stronger safeguards (trusted TLS, MFA, audit review, least-privilege patient scopes).
- The old Vercel files can remain in the repository for history, but are **not involved in this LAN demonstration**. Keep the already-created PR draft and do not merge to main before acceptance tests.
