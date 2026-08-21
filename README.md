# budget-platform

Backend and canonical data-contract repository for the AI budget negotiator.

## Contents

- `contracts/` — versioned JSON Schema; the canonical shape shared by UI, seed data, and integrations.
- `mock-data/implementations/` — deterministic mock households that validate against the canonical schema.
- `supabase/` — migrations and Edge Functions. OpenAI calls stay server-side.
- `n8n/workflows/` — exported workflow definitions only; runtime state and credentials stay outside Git.
- `prompts/` — versioned AI prompt templates and output contracts.

## Security boundary

Commit no credentials, exported n8n credential records, `.env` files, or Supabase service-role keys. Use separate DEV and production configuration.

## Initial contract workflow

1. Change and version the schema in `contracts/`.
2. Update each affected mock-data implementation.
3. Validate fixtures before generating Supabase seed/reset data or copying a fixture to the front end.
