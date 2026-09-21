const CITY_FEEDS = {
  berlin: ["https://www.tagesschau.de/xml/rss2"],
  tokyo: [
    "https://www3.nhk.or.jp/rss/news/cat0.xml",
    "https://feeds.bbci.co.uk/news/world/asia/rss.xml"
  ],
  london: ["https://feeds.bbci.co.uk/news/england/rss.xml"],
  paris: ["https://www.france24.com/en/france/rss"],
  newyork: ["https://rss.nytimes.com/services/xml/rss/nyt/US.xml"]
};

function json(statusCode, body) {
  return {
    statusCode,
    headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=120" },
    body: JSON.stringify(body)
  };
}

function decode(value) {
  return value.replace(/<!\[CDATA\[|\]\]>/g, "")
    .replace(/&amp;/g, "&").replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'").replace(/<[^>]+>/g, "").trim();
}

function parseFeed(xml) {
  return [...xml.matchAll(/<item[\s\S]*?<\/item>/gi)].map((match) => {
    const item = match[0];
    const title = item.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1];
    const description = item.match(/<(?:description|summary|content:encoded)[^>]*>([\s\S]*?)<\/(?:description|summary|content:encoded)>/i)?.[1];
    const link = item.match(/<link[^>]*>([\s\S]*?)<\/link>/i)?.[1];
    const date = item.match(/<(?:pubDate|published)[^>]*>([\s\S]*?)<\/(?:pubDate|published)>/i)?.[1];
    return {
      title: decode(title || ""),
      description: decode(description || ""),
      link: decode(link || ""),
      published: decode(date || "")
    };
  }).filter((item) => item.title);
}

async function translateNews(items) {
  if (!items.length) return items;
  const key = process.env.GEMINI_API_KEY;
  if (!key) return items;
  const model = process.env.GEMINI_MODEL || "gemini-3.6-flash";
  const prompt = [
    "Übersetze Titel und Beschreibung präzise ins Deutsche.",
    "Keine Einordnung, keine Zusammenfassung und keine neuen Informationen.",
    "Antworte ausschließlich als JSON-Array mit genau einem Objekt pro Eingabeobjekt.",
    "Jedes Objekt muss die Schlüssel title und description enthalten.",
    JSON.stringify(items.map((item) => ({ title: item.title, description: item.description })))
  ].join("\n");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(key)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemInstruction: {
            parts: [{ text: "Du bist ein professioneller deutscher Nachrichtenübersetzer. Bewahre Eigennamen, Zahlen und Unsicherheit exakt." }]
          },
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.1, maxOutputTokens: 1800 }
        }),
        signal: controller.signal
      }
    );
    if (!response.ok) return items;
    const data = await response.json();
    const raw = data.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("");
    const normalized = String(raw || "")
      .replace(/^```json\s*/i, "")
      .replace(/^```\s*/i, "")
      .replace(/\s*```$/i, "")
      .trim();
    const parsed = JSON.parse(normalized || "[]");
    const translated = Array.isArray(parsed) ? parsed : parsed.items;
    if (!Array.isArray(translated) || translated.length !== items.length
      || translated.some((item) => !item || typeof item.title !== "string" || !item.title.trim()
        || typeof item.description !== "string")) return items;
    return items.map((item, index) => ({
      ...item,
      title: translated[index].title.trim(),
      description: translated[index].description.trim()
    }));
  } catch {
    return items;
  } finally {
    clearTimeout(timeout);
  }
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") return json(405, { error: "GET erforderlich." });
  const params = event.queryStringParameters || {};
  const label = String(params.label || "").trim();
  const query = String(params.query || label).toLowerCase().trim();
  const lat = Number(params.lat);
  const lon = Number(params.lon);
  if (!label || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    return json(400, { error: "label, lat und lon sind erforderlich." });
  }

  const weatherPromise = fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=auto`,
    { headers: { Accept: "application/json" } }
  ).then((result) => result.ok ? result.json() : null).catch(() => null);

  const rawFeedKey = query.replace(/[^a-z]/g, "");
  const feedKey = rawFeedKey === "tokio" ? "tokyo" : rawFeedKey;
  const feeds = CITY_FEEDS[feedKey] || [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss"
  ];
  const feedResults = await Promise.all(feeds.map(async (feed) => {
    try {
      const result = await fetch(feed, { headers: { "User-Agent": "JarvisRegion/1.0" } });
      return result.ok ? parseFeed(await result.text()) : [];
    } catch {
      return [];
    }
  }));
  const allNews = [...new Map(feedResults.flat().map((item) => [item.title, item])).values()];
  const exactNews = allNews
    .filter((item) => {
      if (feedKey === "berlin") return /berlin/i.test(item.title);
      if (feedKey === "tokyo") return /tokyo|東京|首都/i.test(item.title);
      if (!query || ["london", "paris", "newyork"].includes(feedKey)) return true;
      return item.title.toLowerCase().includes(query);
    })
    .slice(0, 5);
  const news = exactNews.length || !["berlin", "tokyo"].includes(feedKey)
    ? exactNews
    : allNews.slice(0, 5);
  const newsInGerman = await translateNews(news);
  const weather = await weatherPromise;
  return json(200, {
    ok: true,
    location: { label, lat, lon },
    weather: weather?.current || null,
    timezone: weather?.timezone || null,
    news: newsInGerman,
    newsAvailable: newsInGerman.length > 0,
    scope: exactNews.length ? "local" : news.length ? "regional" : "none"
  });
};
