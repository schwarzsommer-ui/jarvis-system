function unauthorized(message) {
  return {
    statusCode: 401,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ error: message })
  };
}

function authorize(event) {
  const expected = process.env.JARVIS_ACCESS_TOKEN;
  if (!expected) return null;
  const supplied = event.headers?.authorization || event.headers?.Authorization || "";
  if (supplied !== `Bearer ${expected}`) {
    return unauthorized("Authentifizierung erforderlich.");
  }
  return null;
}

module.exports = { authorize, unauthorized };
