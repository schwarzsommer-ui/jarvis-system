const FEEDS = [
  "https://www.tagesschau.de/xml/rss2",
  "https://feeds.bbci.co.uk/news/world/rss.xml",
  "https://www.theguardian.com/world/rss",
  "https://www3.nhk.or.jp/rss/news/cat0.xml"
];

function response(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=120"
    },
    body: JSON.stringify(body)
  };
}

function decode(value) {
  return value
    .replace(/<!\[CDATA\[|\]\]>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<[^>]+>/g, "")
    .trim();
}

function parseItems(xml) {
  return [...xml.matchAll(/<item[\s\S]*?<\/item>/gi)].map((match) => {
    const item = match[0];
    const title = item.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1];
    const description = item.match(/<(?:description|summary|content:encoded)[^>]*>([\s\S]*?)<\/(?:description|summary|content:encoded)>/i)?.[1];
    const link = item.match(/<link[^>]*>([\s\S]*?)<\/link>/i)?.[1];
    const date = item.match(/<pubDate[^>]*>([\s\S]*?)<\/pubDate>/i)?.[1];
    return {
      title: decode(title || ""),
      description: decode(description || ""),
      link: decode(link || ""),
      published: decode(date || "")
    };
  }).filter((item) => item.title);
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") return response(405, { error: "GET erforderlich." });
  const query = String(event.queryStringParameters?.query || "").toLowerCase().trim();
  const results = [];
  for (const feed of FEEDS) {
    try {
      const result = await fetch(feed, { headers: { "User-Agent": "JarvisNews/1.0" } });
      if (!result.ok) continue;
      const items = parseItems(await result.text());
      results.push(...items);
    } catch {
      // A failed feed is ignored; the response remains honest about available items.
    }
  }
  const unique = [...new Map(results.map((item) => [item.title, item])).values()];
  const filtered = query
    ? unique.filter((item) => item.title.toLowerCase().includes(query))
    : unique;
  const items = filtered.slice(0, 5);
  return response(200, {
    ok: items.length > 0,
    query,
    items,
    message: items.length ? "Bestätigte Meldungen:" : "Keine bestätigten Meldungen verfügbar."
  });
};
