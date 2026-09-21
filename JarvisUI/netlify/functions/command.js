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

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, headers, body: JSON.stringify({ error: "Invalid JSON body" }) };
  }

  if (typeof payload.command !== "string" || !payload.command.trim()) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: "command must be a non-empty string" }) };
  }

  const webhookUrl = process.env.MAKE_COMMAND_WEBHOOK_URL || process.env.MAKE_WEBHOOK_URL;
  if (!webhookUrl) {
    return {
      statusCode: 503,
      headers,
      body: JSON.stringify({ error: "MAKE_COMMAND_WEBHOOK_URL is not configured" })
    };
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command: payload.command.trim(),
      source: "jarvis-netlify-ui",
      timestamp: new Date().toISOString()
    })
  });

  const responseText = await response.text();
  let result = responseText;
  try {
    result = JSON.parse(responseText);
  } catch {
    // Make may return plain text; preserve it for the UI.
  }

  if (!response.ok) {
    return {
      statusCode: 502,
      headers,
      body: JSON.stringify({ error: "Make webhook returned an error", details: result })
    };
  }

  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, result }) };
};
