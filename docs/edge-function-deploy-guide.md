# Edge function: deploy & wire the AI proxy (echo phase)

Goal: get a deployed Supabase edge function that the Lovable app can call and get
a response from — with your OpenAI key stored **server-side only**. This phase
returns an echo (no AI yet), so the pipe is proven before prompts arrive.

The function code is `supabase/functions/ai-proxy/index.ts`.

> **Deploy to the project the Lovable app connects to** (likely `budget-platform`),
> not a personal test project. Confirm you can deploy to that project first.

> **Your OpenAI key is set by you, directly in Supabase.** It never goes in the
> code, in Git, or in any chat. The function reads it from the server only.

There are two routes. **The Dashboard route needs no CLI, Docker, or terminal —
use it unless your team requires the code live in the repo.**

---

## Route A — Dashboard (recommended for a fast, no-install path)

### 1. Set the OpenAI key as a secret
1. Get a key at https://platform.openai.com/account/api-keys (create a new
   secret key). **Set a monthly spend limit** on the OpenAI account while you're
   there — see Cost & safety below.
2. In the Supabase Dashboard for the **budget-platform** project, go to
   **Edge Functions → Secrets** (the Edge Function Secrets Management page).
3. Add key `OPENAI_API_KEY`, paste the value, **Save**. That's the only place the
   key ever lives.

### 2. Create & deploy the function
1. Dashboard → **Edge Functions → Deploy a new function → via Editor** (start
   from the **Hello World** template, or "from scratch").
2. Name it exactly **`ai-proxy`**.
3. Delete the template code, paste the full contents of
   `supabase/functions/ai-proxy/index.ts`, and click **Deploy**.

### 3. Test the round-trip (right in the dashboard)
Open the function → **Test** tab. Set method **POST**, body:
```json
{ "hello": "world" }
```
Run it. You should get back something like:
```json
{
  "ok": true,
  "echo": { "hello": "world" },
  "openai_key_present": true,
  "method": "POST",
  "received_at": "2026-..."
}
```
`openai_key_present: true` confirms the secret is wired. If it's `false`, redo
step 1.

---

## Route B — CLI (if the function must live in the repo)

Prereqs: Node installed, then `npm install -g supabase`.

```bash
supabase login
supabase link --project-ref <BUDGET_PLATFORM_PROJECT_REF>   # from Dashboard → Settings → General

# set the secret (you type your real key here; it is NOT stored in the repo)
supabase secrets set OPENAI_API_KEY=sk-your-key-here

# the code is already at supabase/functions/ai-proxy/index.ts
supabase functions deploy ai-proxy
```

Test with curl (the anon key is public and safe to use here):
```bash
curl -i -X POST \
  'https://<PROJECT_REF>.supabase.co/functions/v1/ai-proxy' \
  -H 'Authorization: Bearer <ANON_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"hello":"world"}'
```
Expect the same JSON as above.

> If you keep a local `.env` for secrets, add it to `.gitignore`. Never commit a
> key.

---

## 4. Call it from the Lovable app

Lovable apps use the Supabase JS client, which sends the anon key and any signed-in
user's token automatically — so no credentials are handled in your UI code:

```js
const { data, error } = await supabase.functions.invoke('ai-proxy', {
  body: { hello: 'world' },
});
console.log(data); // { ok: true, echo: { hello: 'world' }, openai_key_present: true, ... }
```

If the round-trip returns your echo in the Lovable app, this task is done: the
transport, CORS, auth, secret, and deployment are all proven. Ask the Lovable
builder to add one throwaway button that calls this and logs `data` — that's the
acceptance check.

---

## 5. Phase 2 — when the prompts arrive (reference, don't build yet)

Only the **echo block** in `index.ts` changes. Everything else (CORS, parsing,
key handling) stays. It becomes a direct `fetch` to OpenAI — no SDK needed:

```ts
const apiKey = Deno.env.get("OPENAI_API_KEY");
if (!apiKey) {
  return new Response(JSON.stringify({ ok: false, error: "OPENAI_API_KEY not set" }),
    { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
}

const { prompt } = body as { prompt?: string };

const aiRes = await fetch("https://api.openai.com/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${apiKey}`,       // key stays server-side
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "gpt-4o-mini",                        // pick the agreed model
    messages: [{ role: "user", content: prompt ?? "" }],
  }),
});

const aiJson = await aiRes.json();
const payload = { ok: aiRes.ok, result: aiJson };
```

The `prompt` (and model, and any system message) are the only unknowns — which is
exactly what the echo-first approach was protecting.

---

## Cost & safety notes

- The OpenAI usage is billed to **your** account. In the OpenAI dashboard
  (Settings → Limits), set a **monthly hard limit** so a bug or misuse can't run
  up a surprise bill.
- Keep the function's default auth (it expects a valid Supabase key). Only reach
  for `--no-verify-jwt` if you hit auth friction during the echo test — and turn
  it back on before Phase 2, since the function will then spend real OpenAI money.
- The `Access-Control-Allow-Origin: "*"` here is fine for the hackathon. For
  production you'd restrict it to the app's domain.
