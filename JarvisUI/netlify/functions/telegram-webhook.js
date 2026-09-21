const headers = {
  "Content-Type": "application/json"
};

function json(statusCode, body) {
  return { statusCode, headers, body: JSON.stringify(body) };
}

async function telegramSend(token, chatId, text) {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers,
    body: JSON.stringify({ chat_id: chatId, text })
  });
  if (!response.ok) {
    console.error("Telegram reply failed", response.status);
  }
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") return json(405, { error: "Method not allowed" });
  const expectedSecret = process.env.TELEGRAM_WEBHOOK_SECRET;
  const suppliedSecret = event.headers?.["x-telegram-bot-api-secret-token"]
    || event.headers?.["X-Telegram-Bot-Api-Secret-Token"];
  if (!expectedSecret || suppliedSecret !== expectedSecret) {
    return json(401, { error: "Unauthorized webhook" });
  }

  let update;
  try {
    update = JSON.parse(event.body || "{}");
  } catch {
    return json(400, { error: "Invalid JSON body" });
  }

  const message = update.message;
  const text = typeof message?.text === "string" ? message.text.trim() : "";
  const chatId = String(message?.chat?.id || "");
  const chatType = String(message?.chat?.type || "");
  const senderId = String(message?.from?.id || "");
  const allowedChatId = String(process.env.TELEGRAM_CHAT_ID || "");
  const allowedUsers = String(process.env.TELEGRAM_ALLOWED_USER_IDS || allowedChatId)
    .split(",").map((value) => value.trim()).filter(Boolean);
  if (
    !text || !chatId || chatId !== allowedChatId || chatType !== "private"
    || !allowedUsers.includes(senderId)
  ) {
    return json(200, { ok: true, ignored: true });
  }

  const queueUrl = process.env.TELEGRAM_QUEUE_URL;
  const queueToken = process.env.TELEGRAM_QUEUE_TOKEN;
  const botToken = process.env.TELEGRAM_BOT_TOKEN;
  if (!queueUrl || !queueToken || !botToken) {
    return json(503, { error: "Telegram queue relay is not configured" });
  }

  const forwarded = await fetch(queueUrl.replace(/\/$/, ""), {
    method: "POST",
    headers: { ...headers, Authorization: `Bearer ${queueToken}` },
    body: JSON.stringify({
      command: text,
      source: "telegram-netlify-queue-proxy",
      chat_id: chatId,
      update_id: update.update_id,
      timestamp: new Date().toISOString(),
      confirmation_required: true,
      execution_enabled: false,
      safety: {
        external_actions_require_confirmation: true,
        destructive_actions_require_confirmation: true
      }
    })
  });
  if (!forwarded.ok) {
    await telegramSend(botToken, chatId, "Der Auftrag konnte nicht angenommen werden.");
    return json(502, { error: "Command relay failed" });
  }

  await telegramSend(
    botToken,
    chatId,
    "Auftrag angenommen. Lokale Aktionen werden ausgeführt, sobald J.A.R.V.I.S. online ist; externe oder irreversible Aktionen benötigen Bestätigung."
  );
  return json(200, { ok: true, accepted: true });
};
