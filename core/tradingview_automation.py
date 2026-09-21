from pathlib import Path
import urllib.parse
import os
from concurrent.futures import ThreadPoolExecutor


class TradingViewAutomation:
    """Optional visible Playwright driver for TradingView Paper Trading."""

    def __init__(self):
        self.profile = Path(__file__).resolve().parents[1] / "data" / "tradingview_profile"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-tradingview")
        self._context = None
        self._playwright = None
        self._connected_browser = None

    def execute_paper_order(self, action):
        return self._executor.submit(self._execute_paper_order, action).result()

    def open_chart(self, symbol):
        """Open the requested symbol in a visible TradingView window."""
        return self._executor.submit(self._open_chart, symbol).result()

    def open_markets(self):
        """Navigate the connected visible TradingView tab to the market overview."""
        return self._executor.submit(self._open_markets).result()

    def read_chat_sentiment(self, symbol):
        """Open a chart and report only chat text that is actually exposed in the UI."""
        return self._executor.submit(self._read_chat_sentiment, symbol).result()

    def _ensure_context(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright fehlt. Installiere es mit: python -m pip install playwright"
            ) from exc

        self.profile.mkdir(parents=True, exist_ok=True)
        if self._context is not None:
            return
        self._playwright = sync_playwright().start()
        try:
            cdp_urls = self._cdp_urls()
            for cdp_url in cdp_urls:
                try:
                    browser = self._playwright.chromium.connect_over_cdp(
                        cdp_url, timeout=3000
                    )
                    if not browser.contexts:
                        browser.close()
                        continue
                    self._connected_browser = browser
                    self._context = browser.contexts[0]
                    break
                except Exception:
                    continue

            if self._context is None:
                self._context = self._playwright.chromium.launch_persistent_context(
                    str(self.profile),
                    channel="msedge",
                    headless=False,
                    viewport={"width": 1440, "height": 1000},
                )
        except Exception as exc:
            self._playwright.stop()
            self._playwright = None
            self._connected_browser = None
            raise RuntimeError(
                "TradingView konnte nicht sichtbar geöffnet werden. "
                "Prüfe Chrome/Edge-Remote-Debugging oder starte start_edge_jarvis.bat."
            ) from exc

    @staticmethod
    def _cdp_urls():
        configured = (
            os.getenv("JARVIS_CDP_URL", "").strip()
            or os.getenv("JARVIS_EDGE_CDP_URL", "").strip()
        )
        candidates = [configured] if configured else []
        candidates.extend(
            url
            for url in (
                "http://127.0.0.1:9223",
                "http://127.0.0.1:9222",
            )
            if url not in candidates
        )
        return candidates

    def _open_chart(self, symbol):
        self._ensure_context()
        page = self._tradingview_page()
        page.goto(
            "https://www.tradingview.com/chart/?symbol="
            + urllib.parse.quote(symbol.upper()),
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(1500)
        self._dismiss_overlays(page)
        return f"TradingView-Chart {symbol.upper()} wurde sichtbar geöffnet."

    def _open_markets(self):
        self._ensure_context()
        page = self._tradingview_page()
        page.goto(
            "https://www.tradingview.com/markets/",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(1200)
        self._dismiss_overlays(page)
        if "tradingview.com" not in page.url:
            raise RuntimeError("TradingView-Marktübersicht wurde nicht erreicht.")
        return "TradingView-Marktübersicht wurde sichtbar geöffnet."

    def _read_chat_sentiment(self, symbol):
        self._ensure_context()
        page = self._tradingview_page()
        page.goto(
            "https://www.tradingview.com/chart/?symbol="
            + urllib.parse.quote(symbol.upper()),
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(1800)
        self._dismiss_overlays(page)
        if "tradingview.com" not in page.url:
            raise RuntimeError("Der TradingView-Chart wurde nicht erreicht.")

        body_text = page.locator("body").inner_text(timeout=10000)
        chat_controls = page.locator(
            "[aria-label*='Chat' i], [title*='Chat' i], "
            "button:has-text('Chat'), [role='button']:has-text('Chat')"
        )
        if not chat_controls.count():
            return (
                f"TradingView-Chart {symbol.upper()} wurde sichtbar geöffnet. "
                "Im verbundenen Chart ist kein zugängliches Live-Chat-Panel "
                "und keine lesbaren Chat-Nachrichten vorhanden. "
                "Die Stimmung ist daher nicht bestimmbar."
            )

        chat_text = []
        for line in body_text.splitlines():
            cleaned = " ".join(line.split())
            if cleaned and len(cleaned) >= 3:
                chat_text.append(cleaned)
        keywords = (
            "buy", "sell", "long", "short", "bull", "bear", "panic",
            "kaufen", "verkaufen", "optimistisch", "panisch", "boden",
            "moon", "dump", "rakete",
        )
        messages = [
            line for line in chat_text
            if any(keyword in line.lower() for keyword in keywords)
        ][-20:]
        if not messages:
            return (
                f"TradingView-Chart {symbol.upper()} wurde sichtbar geöffnet. "
                "Ein Chat-Steuerelement ist vorhanden, aber keine lesbaren "
                "Nachrichten wurden im DOM gefunden. Stimmung nicht bestimmbar."
            )
        bullish = sum(
            any(word in message.lower() for word in (
                "buy", "long", "bull", "kaufen", "optimistisch", "moon", "rakete",
            ))
            for message in messages
        )
        bearish = sum(
            any(word in message.lower() for word in (
                "sell", "short", "bear", "verkaufen", "panisch", "panic", "dump",
            ))
            for message in messages
        )
        if bullish > bearish:
            sentiment = "eher optimistisch"
        elif bearish > bullish:
            sentiment = "eher panisch/bearish"
        else:
            sentiment = "gemischt/unklar"
        return (
            f"TradingView-Chart {symbol.upper()} wurde sichtbar geöffnet. "
            f"{len(messages)} lesbare Chat-Zeilen geprüft: Stimmung {sentiment}. "
            "Das ist eine Textstichprobe und keine Anlageberatung."
        )

    def _tradingview_page(self):
        pages = self._context.pages
        for page in pages:
            if "tradingview.com" in page.url.lower():
                return page
        return pages[0] if pages else self._context.new_page()

    def _execute_paper_order(self, action):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright fehlt. Installiere es mit: python -m pip install playwright"
            ) from exc

        self._ensure_context()
        try:
            page = self._context.pages[0] if self._context.pages else self._context.new_page()
            page.goto(
                "https://www.tradingview.com/chart/?symbol="
                + urllib.parse.quote(action["symbol"]),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(2000)
            self._dismiss_overlays(page)
            body_text = page.locator("body").inner_text(timeout=5000).lower()
            if (
                "sign up" in body_text
                or "already have an account" in body_text
                or "benutzerkonto erstellen" in body_text
                or "sign in" in page.title().lower()
            ):
                raise RuntimeError(
                    "TradingView ist im JARVIS-Edge-Profil nicht angemeldet. "
                    "Melde dich dort mit Google an und bestätige danach erneut."
                )
            self._open_paper_trading(page)
            self._fill_order(page, action)
            result = (
                f"Paper-{action['direction']} für {action['symbol']} wurde "
                "in TradingView ausgeführt."
            )
            self._close()
            return result
        except Exception as exc:
            diagnostics = self._save_diagnostics(page if "page" in locals() else None)
            if isinstance(exc, RuntimeError):
                raise RuntimeError(f"{exc} Diagnose: {diagnostics}") from exc
            raise RuntimeError(
                f"TradingView-Automation fehlgeschlagen: {exc}. Diagnose: {diagnostics}"
            ) from exc

    def _save_diagnostics(self, page):
        directory = self.profile / "diagnostics"
        directory.mkdir(parents=True, exist_ok=True)
        screenshot = directory / "last_error.png"
        html = directory / "last_error.html"
        if page:
            try:
                page.screenshot(path=str(screenshot), full_page=True)
                html.write_text(page.content(), encoding="utf-8")
            except Exception:
                return str(directory)
        return str(screenshot)

    def _dismiss_overlays(self, page):
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        close_selectors = (
            "[aria-label='Close']",
            "[aria-label='Close dialog']",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "[data-qa-id='close-button']",
        )
        for selector in close_selectors:
            candidates = page.locator(selector)
            for index in range(min(candidates.count(), 3)):
                candidate = candidates.nth(index)
                if candidate.is_visible():
                    candidate.click(force=True)
                    page.wait_for_timeout(300)

    def close(self):
        self._executor.submit(self._close).result()

    def _close(self):
        if self._context and not self._connected_browser:
            self._context.close()
        if self._connected_browser:
            self._connected_browser = None
        self._context = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _select_symbol(self, page, symbol):
        page.keyboard.press("Control+K")
        page.wait_for_timeout(300)
        page.keyboard.type(symbol)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)

    def _open_paper_trading(self, page):
        cookie_button = page.get_by_role("button", name="Accept all", exact=True)
        if cookie_button.count() and cookie_button.first.is_visible():
            cookie_button.first.click()
            page.wait_for_timeout(300)
        trade_button = page.get_by_role("button", name="Trade", exact=True)
        if trade_button.count() and trade_button.first.is_visible():
            trade_button.first.click()
            page.wait_for_timeout(1200)
        selectors = (
            "[data-name='open-trading-panel']",
            "[data-name='trading-panel']",
            "[aria-label*='Trading Panel']",
            "[aria-label*='Trading panel']",
            "button:has-text('Trading Panel')",
            "[role='button']:has-text('Trading Panel')",
            "button:has-text('Trade')",
        )
        for selector in selectors:
            panel_button = page.locator(selector)
            if panel_button.count() and panel_button.first.is_visible():
                panel_button.first.click()
                page.wait_for_timeout(1200)
                if self._paper_controls_visible(page):
                    return
        if self._paper_controls_visible(page):
            return
        raise RuntimeError(
            "TradingView-Paper-Panel wurde nicht gefunden. "
            "Im JARVIS-Browser unten auf 'Trading Panel' klicken und erneut bestätigen."
        )
        page.wait_for_timeout(1000)

    def _paper_controls_visible(self, page):
        text = page.locator("body").inner_text(timeout=5000).lower()
        return "paper trading" in text or (
            ("buy" in text or "sell" in text)
            and ("market" in text or "limit" in text)
        )

    def _fill_order(self, page, action):
        names = (
            ("Buy", "Kaufen", "Long")
            if action["direction"].lower() == "long"
            else ("Sell", "Verkaufen", "Short")
        )
        button = None
        for name in names:
            candidate = page.get_by_role("button", name=name, exact=True)
            if candidate.count() and candidate.first.is_visible():
                button = candidate.first
                break
            candidate = page.locator(
                f"button:has-text('{name}'), [role='button']:has-text('{name}')"
            )
            if candidate.count() and candidate.first.is_visible():
                button = candidate.first
                break
        if button is None:
            raise RuntimeError(
                f"TradingView-Orderbutton ({'/'.join(names)}) wurde nicht gefunden."
            )
        quantity = str(action["quantity"])
        inputs = page.locator("input")
        filled = False
        for index in range(min(inputs.count(), 20)):
            field = inputs.nth(index)
            if field.is_visible():
                placeholder = (field.get_attribute("placeholder") or "").lower()
                aria = (field.get_attribute("aria-label") or "").lower()
                name = (field.get_attribute("name") or "").lower()
                if any(
                    marker in f"{placeholder} {aria} {name}"
                    for marker in ("qty", "quantity", "amount", "menge", "volume", "size")
                ):
                    field.fill(quantity)
                    filled = True
                    break
        if not filled:
            raise RuntimeError(
                "Mengenfeld der TradingView-Ordermaske wurde nicht gefunden."
            )
        button.click()
