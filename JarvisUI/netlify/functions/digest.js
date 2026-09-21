let latestDigest = null;

const headers = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
};

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers, body: "" };
  }

  if (event.httpMethod === "GET") {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ digest: latestDigest })
    };
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

  if (typeof payload.digest !== "string" || !payload.digest.trim()) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: "digest must be a non-empty string" }) };
  }

  latestDigest = {
    digest: payload.digest.trim(),
    timestamp: typeof payload.timestamp === "string" ? payload.timestamp : new Date().toISOString()
  };

  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, digest: latestDigest }) };
};
