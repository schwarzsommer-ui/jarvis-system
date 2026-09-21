async function probe(url: string, init?: RequestInit) {
  try {
    const response = await fetch(url, { ...init, cache: "no-store", signal: AbortSignal.timeout(10000) });
    return { ok: response.ok, status: response.status, text: await response.text().catch(() => "") };
  } catch {
    return { ok: false, status: 0, text: "" };
  }
}

export async function GET() {
  const now = new Date();
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL ?? "https://spftqucympldmdmxnanj.supabase.co";
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
  const backendUrl = process.env.JARVIS_BACKEND_URL ?? "http://127.0.0.1:8787";
  const ollama = await probe("http://127.0.0.1:11434/api/tags");
  const openWebUI = await probe("http://127.0.0.1:3000");
  const n8n = await probe("http://127.0.0.1:5678/healthz");
  const qdrant = await probe("http://127.0.0.1:6333/collections");
  const backend = await probe(`${backendUrl}/health`);
  const supabase = await probe(`${supabaseUrl}/rest/v1/`, {
    headers: {
      apikey: supabaseKey,
      Authorization: supabaseKey ? `Bearer ${supabaseKey}` : "",
      Accept: "application/json",
    },
  });
  const liveMarkets = await probe(`${backendUrl}/live/markets`);
  const liveNews = await probe(`${backendUrl}/live/news`);
  let model = "llama3";
  try {
    model = JSON.parse(ollama.text)?.models?.[0]?.name ?? model;
  } catch {}
  const localHealthy = [ollama, openWebUI, n8n, qdrant].every((item) => item.ok);
  return Response.json({
    status: {
      online: [ollama, openWebUI, n8n, qdrant, backend].some((item) => item.ok),
      health: localHealthy ? "HEALTHY" : "PARTIAL",
      model,
      time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      energy: 96.4,
      reasoning: 92,
      planning: 88,
      autonomy: 94,
      learning: 90,
    },
    agents: [
      { name: "Commander Agent", status: backend.ok ? "planning" : "offline", hue: "cyan" },
      { name: "Coding Agent", status: "executing", hue: "blue" },
      { name: "Browser Agent", status: "active", hue: "violet" },
      { name: "Research Agent", status: liveNews.ok ? "monitoring" : "offline", hue: "teal" },
      { name: "Trading Agent", status: liveMarkets.ok ? "syncing" : "offline", hue: "amber" },
      { name: "Memory Agent", status: "learning", hue: "purple" },
      { name: "Tool Hunter Agent", status: "online", hue: "cyan" },
    ],
    tasks: [
      { label: "Objective", value: "Complete mission recovery pipeline", tone: "cyan" },
      { label: "Current focus", value: "Research + code + browser orchestration", tone: "violet" },
      { label: "Risk level", value: "Low / adaptive response", tone: "green" },
    ],
    logs: [
      "Commander packet synchronized",
      `JARVIS runtime: ${backend.ok ? "reachable" : "offline"}`,
      `Live market feed: ${liveMarkets.ok ? "updated" : "unavailable"}`,
      `Live news feed: ${liveNews.ok ? "updated" : "unavailable"}`,
    ],
    news: readNews(liveNews.text),
    markets: readMarkets(liveMarkets.text),
    tools: [
      { name: "Ollama", status: ollama.ok ? "Connected" : "Offline" },
      { name: "Open WebUI", status: openWebUI.ok ? "Online" : "Offline" },
      { name: "n8n", status: n8n.ok ? "Listening" : "Offline" },
      { name: "Qdrant", status: qdrant.ok ? "Ready" : "Offline" },
      { name: "JARVIS Runtime", status: backend.ok ? "Executing" : "Offline" },
      { name: "Supabase", status: supabase.ok ? "Connected" : "Offline" },
    ],
    intelligence: [
      { label: "Reasoning", value: 92 },
      { label: "Planning", value: 88 },
      { label: "Autonomy", value: 94 },
      { label: "Learning", value: 90 },
    ],
    memoryNodes: [
      { x: "50%", y: "18%", label: "Goals" },
      { x: "20%", y: "48%", label: "Project" },
      { x: "78%", y: "46%", label: "Tools" },
      { x: "50%", y: "72%", label: "Memory" },
      { x: "32%", y: "82%", label: "Docs" },
      { x: "68%", y: "82%", label: "Acts" },
    ],
  });
}

function readMarkets(text: string) {
  try {
    const assets = JSON.parse(text)?.assets ?? [];
    return assets.slice(0, 4).map((asset: { symbol?: string; price?: number; change24h?: number }) => ({
      symbol: asset.symbol ?? "UNKNOWN",
      value: typeof asset.price === "number" ? asset.price.toLocaleString("en-US") : "n/a",
      change: typeof asset.change24h === "number" ? `${asset.change24h >= 0 ? "+" : ""}${asset.change24h.toFixed(2)}%` : "n/a",
      positive: typeof asset.change24h === "number" && asset.change24h >= 0,
    }));
  } catch {
    return [];
  }
}

function readNews(text: string) {
  try {
    const sources = JSON.parse(text)?.sources ?? [];
    return sources.flatMap((source: { source?: string; items?: Array<{ title?: string }> }) =>
      (source.items ?? []).slice(0, 1).map((item) => ({ title: item.title ?? "Untitled live item", tag: source.source ?? "News" })),
    ).slice(0, 3);
  } catch {
    return [];
  }
}

