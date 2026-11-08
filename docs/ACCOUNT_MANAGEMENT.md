# CLARA account management — deployment and test guide

Status: **review feature, not production-approved**. No existing UI or clinical workflow is replaced unless `ClaraAuth__Enabled=true` is explicitly configured. Never enable in a real hospital before security review, network isolation, encrypted storage, patient-level access controls and administrator MFA.

## Architecture

- React (Vercel for thesis demo) serves the sign-in, staff activation, account settings and hospital IT administration screens.
- ASP.NET Core validates passwords and signed session cookies, handles accounts, security events and chat ownership.
- PostgreSQL stores staff accounts, hashed activation/recovery tokens, audit metadata and conversations; the migration `20261108170000_ClaraAccounts` is additive.
- The restricted demo gateway proxies approved `/api/backend/account/*` routes, validates browser sessions through ASP.NET Core, and binds LLM session IDs to the verified account. An account identifier sent by the browser does **not** establish ownership.
- Existing anonymous browser chat history stays separate. It is **not automatically transferred** to a newly created user because shared-browser history cannot safely be assigned to one employee without verification.

## Before enabling

1. Back up the PostgreSQL database and existing non-sensitive configuration. Do not commit secrets or patient data.
2. Pull the review branch on the local machine. Run existing frontend tests/build and `dotnet build backend/CLARA.Backend.csproj`. Verify the migration with a disposable database before running it on the real one.
3. Start the backend in its normal local configuration. To create the **first** administrator, set private backend process environment variables:
   - `ClaraAuth__Enabled=true`
   - `ClaraAuth__BootstrapUsername=admin` (or another lowercase username)
   - `ClaraAuth__BootstrapPassword=<your securely generated, 12+ character password>`
   The password is read only for the initial bootstrap. Remove the bootstrap password from the environment after that account exists. Do not put it in Git, Vercel `VITE_*` variables or documentation.
4. For the **Vercel defense gateway**, set `CLARA_AUTH_ENABLED=true` in the gateway process environment, then restart the gateway. This must agree with the backend flag. The gateway also checks the backend's auth configuration to avoid accidentally exposing clinical/LLM routes.
5. Keep the existing Vercel gateway URL/key and `CLARA_DEMO_ENABLED=true` protections. Never disable gateway authentication. The Vercel frontend does **not** need access to the database credentials or bootstrap admin password.
6. Open the Vercel preview in a private browser window. The account configuration endpoint should return `{"enabled":true}`. You should see the CLARA login screen. The backend must bind only to loopback or an appropriately firewalled network interface; never expose its local clinical routes directly to the internet.
7. On the first admin login, create a clinician account using **User Management → Invite**; securely give the one-time activation code to the intended staff member. Activation codes expire after 24 hours. Admin-assisted recovery codes expire after 20 minutes and revoke existing sessions.

## Roles

- `admin`: manage staff accounts, invite, deactivate/reactivate, revoke, recover, review security audit, **no routine clinical workspace**.
- `clinician`: clinical chat, permitted patient workspace, own saved chats.
- `trainee`: currently has clinical workspace access. Do **not** enable this role against real identifiable patient records until patient-specific entitlements are completed and verified.
- `auditor`: read-only audit log; no account administration or clinical workspace.

**Important**: the current role gate is a defense/pilot baseline. It is not a complete hospital authorization system: patient-by-patient assignments, physician-patient relationship checks, delegated access, and minimum-necessary access must be completed before processing identifiable hospital patient data. Demo only with authorized de-identified/synthetic records.

## Account behaviors

- No public sign-up or automatic reset emails.
- Admin-generated one-time activation/recovery code; passwords are never displayed to administrators.
- Passwords use ASP.NET Identity's supported password hasher, not plaintext or custom SHA hashing.
- Staff passwords must be 12–256 characters. Administrators must verify the employee out-of-band before issuing recovery.
- New passwords or role changes revoke prior cookie sessions; accounts can be disabled without destroying audit history.
- Cookies are HttpOnly, SameSite=Lax and Secure in production with an 8-hour absolute lifetime. The ASP.NET Data Protection key ring must be persisted securely and backed up by hospital IT so restarts do not invalidate all cookies unexpectedly.
- Chat histories are stored in the account-keyed PostgreSQL table `clara_conversations` only when authentication is enabled. The backend derives the account ID from the validated session. Legacy anonymous browser history is not imported.
- Database disks/backups must be encrypted, restricted to authorized operators, and covered by hospital retention/deletion policies.

## Manual acceptance checks

1. With `ClaraAuth__Enabled` **unset**, confirm existing CLARA patient selection, AI streaming, PDF Sources, browser history and Vercel demo protection still function.
2. Set `ClaraAuth__Enabled=true`, configure the first admin, and confirm unauthenticated `/api/backend/patientdata/patients` and `/api/llm/chat/stream` are blocked, not merely the frontend UI.
3. Confirm admin can invite a clinician, and only the correct one-time code activates that account; reused and expired codes fail.
4. Confirm clinician can sign in, select an authorized synthetic/MIMIC record, chat, refresh, sign out/in and find **their own** chat history.
5. Create a second clinician; verify they cannot read/update/delete the first clinician's chat even with the known conversation ID.
6. Disable a clinician; verify existing sessions are invalidated and no patient or AI API still accepts requests.
7. Change a role; verify the previous cookie cannot keep the old privileges.
8. Issue a recovery code after manual identity verification; verify only one use, expiry, session invalidation, and no user enumeration.
9. Confirm admin cannot browse clinical data and auditor cannot invite staff.
10. Test the real Vercel preview cookie round-trip: login response must set a `clara_session` cookie for the Vercel host; later `/api/backend/account/me` must return the same account; logout must clear it. This **cannot be validated by source inspection alone**.
11. Review failed login behavior, error handling, small-screen login/admin layout, database backup/restore, and network filtering.
12. Before hospital deployment, implement and verify MFA, patient-by-patient authorization and an approved on-premises AI inference/data handling policy.

## Rollback

Set `ClaraAuth__Enabled=false` in the backend and restart it; set `CLARA_AUTH_ENABLED=false` in the demo gateway and restart. The pre-existing CLARA interface and local browser history remain available. **Do not remove the account tables** or roll back the shared database migrations on a database containing real user records without an explicit backup/rollback procedure.

## CI

The review branch includes `.github/workflows/account-review.yml` to run the frontend tests and build, ASP.NET Core build, and gateway Python compilation. GitHub Actions availability depends on repository runner permissions. Always verify the completed job outcomes rather than assuming a workflow file implies a passing build.
