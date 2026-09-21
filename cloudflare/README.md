# Telegram offline queue

The Worker validates Telegram's `X-Telegram-Bot-Api-Secret-Token`, private-chat
allowlists, and message size before writing commands to the `TELEGRAM_QUEUE` KV
namespace. It does **not** call Make.com or execute commands. Every item is
marked `confirmation_required: true` and `execution_enabled: false`.

## Deploy

```powershell
npx wrangler kv namespace create TELEGRAM_QUEUE
npx wrangler kv namespace create TELEGRAM_QUEUE --preview
# Put the returned IDs in wrangler.toml, then:
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler secret put QUEUE_API_TOKEN
npx wrangler deploy
```

Point Telegram at the deployed URL with `setWebhook` and its secret token.

## Queue API

The local runner authenticates with `Authorization: Bearer <QUEUE_API_TOKEN>`.
If the Netlify webhook proxy is enabled, set its `TELEGRAM_QUEUE_TOKEN` to the
same secret and `TELEGRAM_QUEUE_URL` to the Worker's `/queue/enqueue` URL.

* `GET /queue?limit=10` (or `POST /queue/retrieve`) leases pending commands.
* `POST /queue/enqueue` accepts an authenticated proxy payload with a `command`
  field (useful when Telegram is configured to call the Netlify webhook).
* `POST /queue/ack` with `{"id":"tg-…","lease_token":"…","outcome":"processed"}`
  acknowledges a leased command.

Leases expire automatically, allowing a disconnected runner to retry. An ACK
only removes the item from active retrieval; it never authorizes an external or
destructive action.
