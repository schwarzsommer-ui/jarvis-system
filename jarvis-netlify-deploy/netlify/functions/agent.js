const SYSTEM_PROMPT = [
  "Du bist mein Jarvis-Agent. Du planst und beschreibst die Schritte,",
  "um meine Wünsche umzusetzen (Programmierung, Automationen, Deployments).",
  "Du arbeitest im sicheren V2-Planungsmodus: Du darfst Code entwerfen,",
  "Dateien und erwartete Diffs beschreiben sowie Tests und Builds planen,",
  "führst aber niemals selbst Shell-Befehle, Dateiänderungen oder externe Aktionen aus.",
  "Antworte ausschließlich als gültiges JSON mit den Schlüsseln summary, steps, files, tests, risks und suggestedActions.",
  "steps, files, tests, risks und suggestedActions müssen Arrays aus kurzen Strings sein.",
  "Behandle Finanzthemen als Szenarien und nicht als Anlageberatung."
].join(" ");

const headers = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

function json(statusCode, body) {
  return {
    statusCode,
    headers,
    body: JSON.stringify(body)
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers, body: "" };
  }

  if (event.httpMethod !== "POST") {
    return json(405, { error: "Methode nicht erlaubt. Verwende POST." });
  }

  const authError = require("./_shared/auth").authorize(event);
  if (authError) return authError;

  const apiKey = process.env.CLAUDE_API_KEY;
  if (!apiKey) {
    return json(503, {
      error: "CLAUDE_API_KEY ist in den Netlify Environment Variables nicht konfiguriert."
    });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch (error) {
    return json(400, { error: "Der Request-Body muss gültiges JSON sein." });
  }

  if (typeof payload.message !== "string" || !payload.message.trim()) {
    return json(400, { error: "message muss ein nicht-leerer Text sein." });
  }

  const message = payload.message.trim();
  if (message.length > 12000) {
    return json(413, { error: "message darf höchstens 12.000 Zeichen enthalten." });
  }
  const mode = typeof payload.mode === "string" ? payload.mode.trim() : "plan";
  const supportedModes = new Set(["plan", "code", "debug"]);
  if (!supportedModes.has(mode)) {
    return json(400, { error: "mode muss plan, code oder debug sein." });
  }

  const modeInstruction = {
    plan: "Erstelle einen umsetzbaren Gesamtplan.",
    code: "Plane die konkrete Code-Umsetzung. Nenne betroffene Dateien und einen sicheren Diff in Worten.",
    debug: "Analysiere den beschriebenen Fehler. Trenne Ursache, Behebung, Tests und Rollback."
  }[mode];

  let response;
  try {
    response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: process.env.CLAUDE_MODEL || "claude-sonnet-5",
        max_tokens: 1200,
        system: SYSTEM_PROMPT,
        messages: [{ role: "user", content: `${modeInstruction}\n\nAnfrage:\n${message}` }]
      })
    });
  } catch (error) {
    console.error("Claude API request failed", error);
    return json(502, { error: "Claude API ist momentan nicht erreichbar." });
  }

  const data = await response.json();
  if (!response.ok) {
    console.error("Claude API error", response.status, data);
    return json(502, {
      error: "Claude API konnte die Anfrage nicht verarbeiten.",
      providerStatus: response.status,
      providerType: data?.error?.type || "unknown"
    });
  }

  const rawReply = data.content?.find((block) => block.type === "text")?.text;
  if (!rawReply) {
    return json(502, { error: "Claude hat keine Textantwort geliefert." });
  }
  let plan;
  try {
    plan = JSON.parse(rawReply);
  } catch (error) {
    plan = {
      summary: rawReply,
      steps: [],
      files: [],
      tests: [],
      risks: ["Claude lieferte kein strukturiertes JSON."],
      suggestedActions: []
    };
  }

  return json(200, {
    reply: plan.summary || rawReply,
    plan,
    job: {
      status: "awaiting_confirmation",
      confirmationRequired: true,
      executionEnabled: false
    },
    mode,
    confirmationRequired: true,
    capabilities: ["planning", "code-design", "debug-analysis", "test-planning"],
    blockedActions: ["shell", "file-write", "deploy", "external-automation", "financial-order"]
  });
};
