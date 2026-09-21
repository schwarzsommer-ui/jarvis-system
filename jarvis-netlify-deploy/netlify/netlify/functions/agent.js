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
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

function json(statusCode, body) {
  return {
    statusCode,
    headers,
    body: JSON.stringify(body)
  };
}

const providerDefinitions = {
  gemini: { keyEnv: "GEMINI_API_KEY", endpointEnv: "GEMINI_API_URL", modelEnv: "GEMINI_MODEL", defaultModel: "gemini-2.5-flash" },
  gpt: { keyEnv: "GPT_API_KEY", endpointEnv: "GPT_API_URL", modelEnv: "GPT_MODEL", defaultModel: "gpt-4o-mini" },
  nim: { keyEnv: "NIM_API_KEY", endpointEnv: "NIM_API_URL", modelEnv: "NIM_MODEL", defaultModel: "meta/llama-3.1-8b-instruct" },
  claude: { keyEnv: "CLAUDE_API_KEY", modelEnv: "CLAUDE_MODEL", defaultModel: "claude-sonnet-5" }
};

function providerError(provider) {
  const definition = providerDefinitions[provider];
  return json(503, {
    error: `${provider} ist nicht konfiguriert. Setze ${definition.keyEnv} in Netlify Environment Variables.`,
    provider,
    configured: false
  });
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
  const provider = typeof payload.provider === "string" ? payload.provider.trim().toLowerCase() : "gemini";
  if (!providerDefinitions[provider]) {
    return json(400, { error: "provider muss gemini, gpt oder nim sein." });
  }
  const task = typeof payload.task === "string" ? payload.task.trim().toLowerCase() : "default";
  const supportedTasks = new Set(["monitoring", "alert", "dashboard", "default"]);
  if (!supportedTasks.has(task)) {
    return json(400, { error: "task muss monitoring, alert, dashboard oder default sein." });
  }
  const definition = providerDefinitions[provider];
  const apiKey = process.env[definition.keyEnv];
  if (!apiKey) return providerError(provider);

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
  const taskInstruction = {
    monitoring: "Ordne die Anfrage als Monitoring-Szenario ein und nenne Datenquellen sowie Trigger.",
    alert: "Ordne die Anfrage als bestätigungspflichtigen Alert ein und beschreibe den Make.com-Platzhalter.",
    dashboard: "Ordne die Anfrage einem Dashboard-Panel zu und beschreibe die Datenstruktur.",
    default: "Bearbeite die Anfrage als allgemeine Projektaufgabe."
  }[task];
  const prompt = `${modeInstruction}\n${taskInstruction}\n\nAnfrage:\n${message}`;

  let response;
  try {
    if (provider === "claude") {
      response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({
          model: process.env.CLAUDE_MODEL || definition.defaultModel,
          max_tokens: 1200,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: prompt }]
        })
      });
    } else if (provider === "gemini") {
      const endpoint = process.env.GEMINI_API_URL || "https://generativelanguage.googleapis.com/v1beta/models";
      const model = process.env.GEMINI_MODEL || definition.defaultModel;
      response = await fetch(`${endpoint}/${model}:generateContent?key=${encodeURIComponent(apiKey)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] }, contents: [{ parts: [{ text: prompt }] }] })
      });
    } else {
      const endpoint = process.env[definition.endpointEnv];
      if (!endpoint) return json(503, { error: `${provider} benötigt ${definition.endpointEnv}.`, provider, configured: false });
      response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify({
          model: process.env[definition.modelEnv] || definition.defaultModel,
          temperature: 0.2,
          messages: [{ role: "system", content: SYSTEM_PROMPT }, { role: "user", content: prompt }]
        })
      });
    }
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

  const rawReply = provider === "claude"
    ? data.content?.find((block) => block.type === "text")?.text
    : provider === "gemini"
      ? data.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("")
      : data.choices?.[0]?.message?.content;
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
    provider,
    task,
    confirmationRequired: true,
    capabilities: ["planning", "code-design", "debug-analysis", "test-planning"],
    blockedActions: ["shell", "file-write", "deploy", "external-automation", "financial-order"]
  });
};
