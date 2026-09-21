const { authorize } = require("./_shared/auth");
const { headers, json } = require("./_shared/response");

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return { statusCode: 204, headers, body: "" };
  if (event.httpMethod !== "POST") return json(405, { error: "Methode nicht erlaubt." });
  const authError = authorize(event);
  if (authError) return authError;

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch (error) {
    return json(400, { error: "Ungültiges JSON." });
  }
  if (typeof payload.action !== "string" || !payload.action.trim()) {
    return json(400, { error: "action ist erforderlich." });
  }

  const job = {
    id: `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    action: payload.action.trim(),
    status: "awaiting_confirmation",
    confirmationRequired: true,
    executionEnabled: false,
    createdAt: new Date().toISOString(),
    message: "Job vorbereitet. Ein privater Runner und eine ausdrückliche Bestätigung sind erforderlich."
  };
  return json(202, { job });
};
