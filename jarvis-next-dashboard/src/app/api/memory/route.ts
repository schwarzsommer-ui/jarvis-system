type MemoryRecord = {
  id: string;
  category: string;
  title: string;
  type: string;
  topic: string | null;
  content: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
};

function supabaseConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_ANON_KEY;
  return url && key ? { url, key } : null;
}

export async function GET() {
  const config = supabaseConfig();

  if (!config) {
    return Response.json({ ok: false, message: "Supabase persistence is not configured." }, { status: 503 });
  }

  try {
    const response = await fetch(
      `${config.url}/rest/v1/jarvis_memory?select=id,category,title,type,topic,content,metadata,created_at&order=created_at.desc&limit=25`,
      {
        headers: {
          apikey: config.key,
          Authorization: `Bearer ${config.key}`,
          Accept: "application/json",
        },
        cache: "no-store",
        signal: AbortSignal.timeout(4000),
      },
    );

    if (!response.ok) {
      return Response.json({ ok: false, message: "Memory store could not be read." }, { status: 502 });
    }

    const records = (await response.json()) as MemoryRecord[];
    return Response.json({ ok: true, records });
  } catch (error) {
    console.error("Memory read failed:", error);
    return Response.json({ ok: false, message: "Memory read failed." }, { status: 502 });
  }
}

export async function POST(request: Request) {
  const config = supabaseConfig();

  if (!config) {
    return Response.json({ ok: false, message: "Supabase persistence is not configured." }, { status: 503 });
  }

  try {
    const body = await request.json();
    const title = typeof body?.title === "string" ? body.title.trim() : "";
    const topic = typeof body?.topic === "string" ? body.topic.trim() : "";

    if (!title || !topic) {
      return Response.json({ ok: false, message: "Memory title and topic are required." }, { status: 400 });
    }

    const response = await fetch(`${config.url}/rest/v1/jarvis_memory`, {
      method: "POST",
      headers: {
        apikey: config.key,
        Authorization: `Bearer ${config.key}`,
        "Content-Type": "application/json",
        Prefer: "return=representation",
      },
      body: JSON.stringify({
        category: typeof body?.category === "string" ? body.category : "memory",
        title,
        type: typeof body?.type === "string" ? body.type : "memory",
        topic,
        content: body?.content && typeof body.content === "object" ? body.content : {},
        metadata: body?.metadata && typeof body.metadata === "object" ? body.metadata : {},
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });

    if (!response.ok) {
      return Response.json({ ok: false, message: "Memory could not be written." }, { status: 502 });
    }

    return Response.json({ ok: true, records: await response.json() }, { status: 201 });
  } catch (error) {
    console.error("Memory write failed:", error);
    return Response.json({ ok: false, message: "Memory write failed." }, { status: 502 });
  }
}
