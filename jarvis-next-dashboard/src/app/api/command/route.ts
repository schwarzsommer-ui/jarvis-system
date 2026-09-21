export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = typeof body?.action === "string" ? body.action.trim() : "";

    if (!action) {
      return Response.json(
        { ok: false, status: "error", message: "A non-empty command action is required." },
        { status: 400 },
      );
    }

    const backendUrl = process.env.JARVIS_BACKEND_URL ?? "http://127.0.0.1:8787";
    const workflowByAction: Record<string, string> = {
      status: "monitoring",
      research: "research",
      browser: "browser",
      desktop: "desktop",
    };
    const kind = workflowByAction[action];
    if (!kind) {
      return Response.json(
        {
          ok: false,
          status: "unsupported",
          message: `No live workflow is registered for '${action}'.`,
        },
        { status: 422 },
      );
    }

    const workflowPayload = kind === "monitoring" ? { operation: "status" } : { action };
    const runtimeResponse = await fetch(
      action === "status" ? `${backendUrl}/health` : `${backendUrl}/workflows/${kind}/execute`,
      {
      method: action === "status" ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      ...(action === "status" ? {} : { body: JSON.stringify(workflowPayload) }),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
      },
    );

    if (!runtimeResponse.ok) {
      return Response.json(
        { ok: false, status: "error", message: "JARVIS runtime rejected the command." },
        { status: 502 },
      );
    }

    const runtimeBody = await runtimeResponse.json();
    const runtime = action === "status"
      ? { status: "executed", result: runtimeBody }
      : runtimeBody;
    if (!["executed", "confirmation_required"].includes(runtime.status)) {
      return Response.json(
        { ok: false, status: "error", message: "JARVIS runtime did not accept the command.", runtime },
        { status: 502 },
      );
    }

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL;
    const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      return Response.json(
        { ok: false, status: "error", message: "Supabase persistence is not configured." },
        { status: 503 },
      );
    }

    const persistence = await fetch(`${supabaseUrl}/rest/v1/jarvis_memory`, {
      method: "POST",
      headers: {
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({
        category: "command",
        title: `JARVIS command: ${action}`,
        type: "command",
        topic: `command:${action}`,
        content: { action, status: runtime.status, result: runtime.result ?? null },
        metadata: { source: "dashboard", runtime },
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });

    if (!persistence.ok) {
      return Response.json(
        { ok: false, status: "error", message: "Command could not be persisted." },
        { status: 502 },
      );
    }

    return Response.json({
      ok: true,
      action,
      status: runtime.status,
      task_id: runtime.task_id,
      message: `Command '${action}' accepted by the live JARVIS runtime.`,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Command dispatch failed:", error);
    return Response.json(
      { ok: false, status: "error", message: "Command dispatch failed." },
      { status: 502 },
    );
  }
}
