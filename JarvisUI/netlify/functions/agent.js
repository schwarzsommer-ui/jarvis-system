const headers = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers, body: "" };
  }

  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers, body: JSON.stringify({ error: "Method not allowed" }) };
  }

  const apiKey = process.env.CLAUDE_API_KEY;
  if (!apiKey) {
    return {
      statusCode: 503,
      headers,
      body: JSON.stringify({ error: "CLAUDE_API_KEY ist in Netlify nicht konfiguriert" })
    };
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, headers, body: JSON.stringify({ error: "Invalid JSON body" }) };
  }

  if (typeof payload.message !== "string" || !payload.message.trim()) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: "message must be a non-empty string" }) };
  }

  const message = payload.message.trim();
  if (message.length > 12000) {
    return { statusCode: 413, headers, body: JSON.stringify({ error: "message is too long" }) };
  }

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01"
    },
    body: JSON.stringify({
      model: process.env.CLAUDE_MODEL || "claude-3-5-sonnet-20240620",
      max_tokens: 1024,
      system: "Du bist mein Jarvis-Agent. Plane und beschreibe die nächsten Schritte auf Deutsch. Führe keine externen Aktionen selbstständig aus.",
      messages: [{ role: "user", content: message }]
    })
  });

  const data = await response.json();
  if (!response.ok) {
    console.error("Claude API error", response.status, data);
    return {
      statusCode: 502,
      headers,
      body: JSON.stringify({ error: "Claude API konnte die Anfrage nicht verarbeiten" })
    };
  }

  const reply = data?.content?.find((block) => block.type === "text")?.text;
  if (!reply) {
    return {
      statusCode: 502,
      headers,
      body: JSON.stringify({ error: "Claude hat keine Textantwort geliefert" })
    };
  }

  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, reply }) };
};
