const QUEUE_PREFIX = "telegram-queue:";
const DEDUPE_PREFIX = "telegram-dedupe:";
const INDEX_KEY = `${QUEUE_PREFIX}index`;
const MAX_COMMAND_LENGTH = 4000;
const DEFAULT_LEASE_SECONDS = 300;
const MAX_LEASE_SECONDS = 900;
const RETENTION_SECONDS = 60 * 60 * 24 * 7;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/queue" && request.method === "GET") {
      return retrieveQueue(request, env, url);
    }
    if (url.pathname === "/queue/retrieve" && request.method === "POST") {
      return retrieveQueue(request, env, url);
    }
    if (url.pathname === "/queue/enqueue" && request.method === "POST") {
      return enqueueFromProxy(request, env);
    }
    if (url.pathname === "/queue/ack" && request.method === "POST") {
      return acknowledgeQueueItem(request, env);
    }
    if (url.pathname === "/queue/status" && request.method === "POST") {
      return updateQueueStatus(request, env);
    }
    if (url.pathname === "/" && request.method === "GET") {
      return json({ ok: true, service: "jarvis-telegram-relay" });
    }
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

    // Telegram's secret header is checked before parsing or storing any update.
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TELEGRAM_WEBHOOK_SECRET) {
      return json({ error: "Unauthorized webhook" }, 401);
    }
    if (!env.TELEGRAM_QUEUE) return json({ error: "Queue storage is not configured" }, 503);

    let update;
    try {
      update = await request.json();
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }

    const message = update?.message;
    const text = typeof message?.text === "string" ? message.text.trim() : "";
    const chatId = String(message?.chat?.id || "");
    const senderId = String(message?.from?.id || "");
    const allowedUsers = String(env.TELEGRAM_ALLOWED_USER_IDS || env.TELEGRAM_CHAT_ID || "")
      .split(",").map((value) => value.trim()).filter(Boolean);
    if (
      !text || chatId !== String(env.TELEGRAM_CHAT_ID || "")
      || message?.chat?.type !== "private" || !allowedUsers.includes(senderId)
    ) {
      return json({ ok: true, ignored: true });
    }
    if (text.length > MAX_COMMAND_LENGTH) return json({ error: "Command is too long" }, 413);

    const queued = await enqueueCommand(env, {
      command: text,
      source: "telegram-cloudflare-queue",
      chat_id: chatId,
      update_id: update.update_id
    });
    const requestId = queued.request_id;
    if (queued.duplicate) {
      await sendTelegramReply(env, chatId, `Auftrag bereits angenommen (${requestId}).`);
      return json({ ok: true, accepted: true, duplicate: true, request_id: requestId });
    }
    await sendTelegramReply(
      env,
      chatId,
      `Auftrag angenommen (${requestId}). Er bleibt offline in der Warteschlange; externe oder irreversible Aktionen benötigen weiterhin Bestätigung.`
    );
    return json({ ok: true, accepted: true, queued: true, request_id: requestId });
  }
};

async function enqueueFromProxy(request, env) {
  const authError = authorizeQueue(request, env);
  if (authError) return authError;
  if (!env.TELEGRAM_QUEUE) return json({ error: "Queue storage is not configured" }, 503);
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  if (typeof body?.command !== "string" || !body.command.trim()) {
    return json({ error: "command must be a non-empty string" }, 400);
  }
  if (body.command.length > MAX_COMMAND_LENGTH) return json({ error: "Command is too long" }, 413);
  const queued = await enqueueCommand(env, body);
  return json({ ok: true, queued: !queued.duplicate, duplicate: queued.duplicate, request_id: queued.request_id });
}

async function enqueueCommand(env, payload) {
  const updateId = String(payload.update_id || crypto.randomUUID());
  const requestId = `tg-${updateId}`;
  const dedupeKey = `${DEDUPE_PREFIX}${updateId}`;
  if (await env.TELEGRAM_QUEUE.get(dedupeKey)) return { request_id: requestId, duplicate: true };
  const item = {
    id: requestId,
    command: payload.command.trim(),
    source: String(payload.source || "telegram-queue").slice(0, 80),
    chat_id: String(payload.chat_id || ""),
    update_id: payload.update_id,
    created_at: new Date().toISOString(),
    status: "pending",
    confirmation_required: true,
    execution_enabled: false
  };
  await env.TELEGRAM_QUEUE.put(`${QUEUE_PREFIX}${requestId}`, JSON.stringify(item), {
    expirationTtl: RETENTION_SECONDS
  });
  await appendToIndex(env.TELEGRAM_QUEUE, requestId);
  await env.TELEGRAM_QUEUE.put(dedupeKey, "1", { expirationTtl: RETENTION_SECONDS });
  return { request_id: requestId, duplicate: false };
}

async function retrieveQueue(request, env, url) {
  const authError = authorizeQueue(request, env);
  if (authError) return authError;
  if (!env.TELEGRAM_QUEUE) return json({ error: "Queue storage is not configured" }, 503);

  let limit = Number(url.searchParams.get("limit") || 10);
  let leaseSeconds = Number(url.searchParams.get("lease_seconds") || DEFAULT_LEASE_SECONDS);
  if (request.method === "POST") {
    try {
      const body = await request.json();
      if (body.limit !== undefined) limit = Number(body.limit);
      if (body.lease_seconds !== undefined) leaseSeconds = Number(body.lease_seconds);
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }
  }
  limit = Math.max(1, Math.min(Number.isFinite(limit) ? Math.floor(limit) : 10, 100));
  leaseSeconds = Math.max(30, Math.min(
    Number.isFinite(leaseSeconds) ? Math.floor(leaseSeconds) : DEFAULT_LEASE_SECONDS,
    MAX_LEASE_SECONDS
  ));

  const now = Date.now();
  const index = await readIndex(env.TELEGRAM_QUEUE);
  const items = [];
  const remaining = [];
  for (const id of index) {
    const raw = await env.TELEGRAM_QUEUE.get(`${QUEUE_PREFIX}${id}`);
    if (!raw) continue;
    const item = JSON.parse(raw);
    if (item.status === "acknowledged") continue;
    const leaseExpired = !item.lease_expires_at || Date.parse(item.lease_expires_at) <= now;
    if (items.length < limit && (item.status === "pending" || leaseExpired)) {
      item.status = "leased";
      item.lease_token = crypto.randomUUID();
      item.lease_expires_at = new Date(now + leaseSeconds * 1000).toISOString();
      await env.TELEGRAM_QUEUE.put(`${QUEUE_PREFIX}${id}`, JSON.stringify(item), {
        expirationTtl: RETENTION_SECONDS
      });
      items.push(item);
    } else {
      remaining.push(id);
    }
  }
  await env.TELEGRAM_QUEUE.put(INDEX_KEY, JSON.stringify([...remaining, ...items.map((item) => item.id)]));
  return json({ ok: true, items, count: items.length });
}

async function acknowledgeQueueItem(request, env) {
  const authError = authorizeQueue(request, env);
  if (authError) return authError;
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  if (!body || typeof body.id !== "string" || typeof body.lease_token !== "string") {
    return json({ error: "id and lease_token are required" }, 400);
  }
  const key = `${QUEUE_PREFIX}${body.id}`;
  const raw = await env.TELEGRAM_QUEUE.get(key);
  if (!raw) return json({ error: "Queue item not found" }, 404);
  const item = JSON.parse(raw);
  if (item.status !== "leased" || item.lease_token !== body.lease_token) {
    return json({ error: "Invalid or expired lease" }, 409);
  }
  item.status = "acknowledged";
  item.acknowledged_at = new Date().toISOString();
  item.outcome = typeof body.outcome === "string" ? body.outcome.slice(0, 200) : "processed";
  delete item.lease_token;
  delete item.lease_expires_at;
  await env.TELEGRAM_QUEUE.put(key, JSON.stringify(item), { expirationTtl: RETENTION_SECONDS });
  return json({ ok: true, acknowledged: true, id: item.id });
}

async function updateQueueStatus(request, env) {
  const authError = authorizeQueue(request, env);
  if (authError) return authError;
  if (!env.TELEGRAM_QUEUE) return json({ error: "Queue storage is not configured" }, 503);
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  if (!body || typeof body.id !== "string" || typeof body.status !== "string") {
    return json({ error: "id and status are required" }, 400);
  }
  const key = `${QUEUE_PREFIX}${body.id}`;
  const raw = await env.TELEGRAM_QUEUE.get(key);
  if (!raw) return json({ error: "Queue item not found" }, 404);
  const item = JSON.parse(raw);
  item.local_status = body.status.slice(0, 40);
  if (typeof body.task_id === "string") item.local_task_id = body.task_id.slice(0, 120);
  item.local_status_at = new Date().toISOString();
  await env.TELEGRAM_QUEUE.put(key, JSON.stringify(item), { expirationTtl: RETENTION_SECONDS });
  return json({ ok: true, id: item.id, status: item.local_status });
}

function authorizeQueue(request, env) {
  const expected = env.QUEUE_API_TOKEN;
  const supplied = request.headers.get("Authorization") || "";
  const token = request.headers.get("X-Queue-Token") || "";
  if (!expected || (supplied !== `Bearer ${expected}` && token !== expected)) {
    return json({ error: "Unauthorized" }, 401);
  }
  return null;
}

async function readIndex(queue) {
  try {
    const index = JSON.parse(await queue.get(INDEX_KEY) || "[]");
    return Array.isArray(index) ? index : [];
  } catch {
    return [];
  }
}

async function appendToIndex(queue, id) {
  const index = await readIndex(queue);
  if (!index.includes(id)) index.push(id);
  await queue.put(INDEX_KEY, JSON.stringify(index.slice(-10000)));
}

async function sendTelegramReply(env, chatId, text) {
  if (!env.TELEGRAM_BOT_TOKEN) return;
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
  });
}
