// supabase/functions/ai-proxy/index.ts
//
// PHASE 1 — echo round-trip. Proves the pipe works end to end:
//   Lovable app  ->  this edge function  ->  JSON response  ->  Lovable app
// It also confirms the OpenAI key is wired as a server-side secret WITHOUT ever
// exposing the value, so when the real prompts arrive the prompt is the only
// new unknown.
//
// The OpenAI key is read from the server environment only (Deno.env). It never
// appears in browser code, in this file's output, or in any response body.
//
// PHASE 2 (when prompts land): replace the "echo block" below with the OpenAI
// call shown in edge-function-deploy-guide.md. Nothing else changes.

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

Deno.serve(async (req) => {
  // Browsers send a preflight OPTIONS request before the real one.
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Read the caller's JSON body if there is one (default to {}).
    let body: unknown = {};
    const contentType = req.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      body = await req.json().catch(() => ({}));
    }

    // Is the OpenAI secret set on the server? Report true/false only —
    // NEVER the value.
    const openaiKeyPresent = Boolean(Deno.env.get("OPENAI_API_KEY"));

    // ---- echo block (Phase 2 replaces this with the OpenAI call) ----
    const payload = {
      ok: true,
      echo: body,                     // sends back whatever the front end sent
      openai_key_present: openaiKeyPresent,
      method: req.method,
      received_at: new Date().toISOString(),
    };
    // -----------------------------------------------------------------

    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
