# CLARA Project Decisions

## Cost Constraint

This project targets free/local operation because it is a 4th-year computer science degree project.

- Do not make paid APIs the default provider.
- Keep patient data in PostgreSQL as the local source of truth.
- Use Hugging Face locally for RAG embeddings.
- Prefer GroqCloud Free plan for fast LLM responses during demos and development, with Hugging Face or Ollama as local fallback options.
- GroqCloud free tier is acceptable when the account remains on the Free plan and requests stay within free rate limits.
- Use `LLM_PROVIDER=groq` for GroqCloud. Do not add xAI Grok as a default provider because it creates naming and billing confusion.
