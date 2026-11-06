# CLARA LLM providers

Local configuration lives in `ai-services/llm_service/.env`, which is ignored by Git.

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<private OpenRouter key>
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
GROQ_API_KEY=<private Groq key>
GROQ_MODEL=openai/gpt-oss-20b
```

Restart CLARA after configuration changes. `/health` on the LLM service reports
the configured primary and fallback; it does not test their remote availability.

OpenRouter receives the same prepared patient/guideline prompt used by CLARA.
It is attempted once with a 10-second connection and 45-second read timeout.
Quota/capacity failures, network failures, invalid response bodies and empty or
truncated answers trigger the existing Groq adapter. Access/credential errors,
invalid requests and explicit refusals do not trigger fallback. If both providers
fail, CLARA returns an error rather than an incomplete answer. Existing guideline
validation and citation checks still apply to both providers.

Only `:free` OpenRouter model IDs are accepted; no alternate paid models or paid
plugins are requested. Groq uses its own key and account allowance. The LLM service
logs the successful provider/model and fallback events without logging prompts,
keys or raw provider error bodies. Opt-in evaluation traces record each provider
attempt, including fallback attempts.

NVIDIA's free endpoint notice prohibits confidential/personal information and
states that sessions are logged for security and service improvement. Use only
permitted demo data. Review the endpoint terms before changing datasets.

To revert: set `LLM_PROVIDER=groq` and restart. No PDF import, database migration,
embedding rebuild or frontend deployment is required for this provider change.

The automated tests mock failures to check routing. A successful connectivity
test does not establish clinical quality: rerun the clinical evaluation before
using the model change in a survey, and distinguish model/fallback results.
