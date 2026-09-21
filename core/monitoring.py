"""Key-free local RSS monitoring for Jarvis."""

import json
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlencode


RSS_FEEDS = {
    "tagesschau": "https://www.tagesschau.de/xml/rss2",
    "bbc_world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
}


class LocalMonitoring:
    def __init__(self, timeout=10):
        self.timeout = timeout

    def _fetch(self, name, url):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JarvisLocalMonitoring/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            root = ET.fromstring(response.read())
        items = []
        for item in root.findall(".//item")[:10]:
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (
                    item.findtext("pubDate")
                    or item.findtext("{http://purl.org/dc/elements/1.1/}date")
                    or ""
                ).strip(),
            })
        return {"source": name, "url": url, "items": items, "ok": True}

    def news(self):
        sources = []
        for name, url in RSS_FEEDS.items():
            try:
                sources.append(self._fetch(name, url))
            except (OSError, urllib.error.URLError, ET.ParseError) as exc:
                sources.append({
                    "source": name,
                    "url": url,
                    "items": [],
                    "ok": False,
                    "error": str(exc),
                })
        news_api_key = os.getenv("NEWSAPI_API_KEY", "").strip()
        if news_api_key:
            try:
                data = self._json_get(
                    "https://newsapi.org/v2/top-headlines?"
                    + urlencode({"language": "en", "pageSize": 10, "apiKey": news_api_key})
                )
                sources.append({
                    "source": "NewsAPI",
                    "url": "https://newsapi.org",
                    "items": [
                        {"title": item.get("title", ""), "link": item.get("url", ""), "published": item.get("publishedAt", "")}
                        for item in data.get("articles", [])
                    ],
                    "ok": data.get("status") == "ok",
                })
            except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
                sources.append({"source": "NewsAPI", "items": [], "ok": False})
        try:
            ids = self._json_get("https://hacker-news.firebaseio.com/v0/topstories.json")[:10]
            items = []
            for story_id in ids:
                story = self._json_get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
                if story and story.get("title"):
                    items.append({"title": story["title"], "link": story.get("url", ""), "published": story.get("time", "")})
            sources.append({"source": "Hacker News", "items": items, "ok": bool(items)})
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            sources.append({"source": "Hacker News", "items": [], "ok": False})
        return {
            "ok": any(source["ok"] for source in sources),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            "financialAdvice": False,
        }

    def _json_get(self, url):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JarvisLocalMonitoring/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def weather(self, latitude=51.0504, longitude=13.7373, location="Dresden"):
        try:
            data = self._json_get(
                "https://api.open-meteo.com/v1/forecast?"
                + urlencode({
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                    "timezone": "Europe/Berlin",
                })
            )
            source = "Open-Meteo"
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            key = os.getenv("OPENWEATHER_API_KEY", "").strip()
            if not key:
                raise
            data = self._json_get(
                "https://api.openweathermap.org/data/2.5/weather?"
                + urlencode({"lat": latitude, "lon": longitude, "appid": key, "units": "metric"})
            )
            current = data.get("main", {})
            return {
                "ok": True, "source": "OpenWeatherMap", "location": location,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "temperature": current.get("temp"), "humidity": current.get("humidity"),
                "wind": (data.get("wind") or {}).get("speed"),
                "weatherCode": (data.get("weather") or [{}])[0].get("id"),
            }
        current = data.get("current", {})
        return {
            "ok": True,
            "source": "Open-Meteo",
            "location": location,
            "fetchedAt": current.get("time"),
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "weatherCode": current.get("weather_code"),
        }

    def forex(self, base="EUR", symbols=("USD", "GBP", "CHF", "JPY")):
        data = self._json_get(
            "https://api.frankfurter.app/latest?"
            + urlencode({"from": base, "to": ",".join(symbols)})
        )
        return {
            "ok": bool(data.get("rates")),
            "source": "Frankfurter/EZB",
            "base": data.get("base", base),
            "date": data.get("date"),
            "rates": data.get("rates", {}),
        }

    def alpha_forex(self, from_symbol="EUR", to_symbol="USD"):
        key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
        if not key:
            return {"ok": False, "source": "Alpha Vantage", "error": "API key not configured"}
        data = self._json_get(
            "https://www.alphavantage.co/query?"
            + urlencode({
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_symbol,
                "to_currency": to_symbol,
                "apikey": key,
            })
        )
        quote = data.get("Realtime Currency Exchange Rate", {})
        return {
            "ok": bool(quote),
            "source": "Alpha Vantage",
            "pair": f"{from_symbol}{to_symbol}",
            "rate": quote.get("5. Exchange Rate"),
            "timestamp": quote.get("6. Last Refreshed"),
        }

    def crypto(self, ids=("bitcoin", "ethereum", "solana")):
        data = self._json_get(
            "https://api.coingecko.com/api/v3/simple/price?"
            + urlencode({
                "ids": ",".join(ids),
                "vs_currencies": "usd,eur",
                "include_24hr_change": "true",
            })
        )
        assets = []
        for coin_id, values in data.items():
            assets.append({
                "symbol": coin_id.upper(),
                "price": values.get("usd"),
                "priceEur": values.get("eur"),
                "change24h": values.get("usd_24h_change"),
                "source": "CoinGecko",
                "ok": True,
            })
        return {
            "ok": bool(assets),
            "source": "CoinGecko",
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "assets": assets,
            "financialAdvice": False,
        }

    def markets(self):
        """Return only provider-backed snapshots; never synthesize missing prices."""
        return self.crypto()

    def status(self):
        return {
            "enabled": True,
            "sources": list(RSS_FEEDS) + ["Hacker News"] + (["NewsAPI"] if os.getenv("NEWSAPI_API_KEY") else []),
            "marketData": True,
            "marketProviders": ["CoinGecko crypto", "Frankfurter/EZB FX"],
            "weatherProviders": ["Open-Meteo"] + (["OpenWeatherMap"] if os.getenv("OPENWEATHER_API_KEY") else []),
            "optionalProviders": {
                "NewsAPI": bool(os.getenv("NEWSAPI_API_KEY")),
                "Alpha Vantage": bool(os.getenv("ALPHAVANTAGE_API_KEY")),
            },
            "externalActions": False,
            "financialAdvice": False,
        }
