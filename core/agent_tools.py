import os
import re
import shutil
import subprocess
import urllib.parse
import webbrowser
import json
from pathlib import Path
from dataclasses import dataclass
from core.tradingview_automation import TradingViewAutomation
from core.skill_manager import SkillManager


class DesktopControls:
    """Allowlisted, visible desktop actions.

    The assistant must never turn user text into a shell command.  Applications
    and URLs are resolved through small allowlists and files are only opened by
    the operating system's normal associated application.
    """

    APPLICATIONS = {
        "jarvis": (r"C:\Users\Timlo\OneDrive\Desktop\JARVIS_SYSTEM\start_v2.ps1", "JARVIS V2"),
        "jarvis gui": (r"C:\Users\Timlo\OneDrive\Desktop\JARVIS_SYSTEM\start_v2.ps1", "JARVIS V2"),
        "jarvis-system": (r"C:\Users\Timlo\OneDrive\Desktop\JARVIS_SYSTEM\start_v2.ps1", "JARVIS V2"),
        "zoey": (os.path.expandvars(r"%LOCALAPPDATA%\Zoey OS\zoey-os.exe"), "Zoey OS"),
        "zoey os": (os.path.expandvars(r"%LOCALAPPDATA%\Zoey OS\zoey-os.exe"), "Zoey OS"),
        "editor": ("notepad.exe", "Editor"),
        "notepad": ("notepad.exe", "Editor"),
        "rechner": ("calc.exe", "Rechner"),
        "calculator": ("calc.exe", "Rechner"),
        "dateien": ("explorer.exe", "Dateien"),
        "explorer": ("explorer.exe", "Dateien"),
        "chrome": ("chrome.exe", "Chrome"),
        "google chrome": ("chrome.exe", "Chrome"),
        "edge": ("msedge.exe", "Microsoft Edge"),
        "microsoft edge": ("msedge.exe", "Microsoft Edge"),
        "browser": ("msedge.exe", "Microsoft Edge"),
        "firefox": ("firefox.exe", "Firefox"),
        "opera": ("opera.exe", "Opera"),
        "vscode": ("code.cmd", "Visual Studio Code"),
        "visual studio code": ("code.cmd", "Visual Studio Code"),
        "discord": ("Discord.exe", "Discord"),
        "steam": ("steam.exe", "Steam"),
        "spotify": ("spotify.exe", "Spotify"),
        "telegram": ("telegram.exe", "Telegram"),
        "outlook": ("outlook.exe", "Outlook"),
        "teams": ("Teams.exe", "Microsoft Teams"),
        "taskmanager": ("taskmgr.exe", "Task-Manager"),
        "terminal": ("wt.exe", "Terminal"),
        "cmd": ("cmd.exe", "Command Prompt"),
    }
    WEBSITES = {
        "gmail": "https://mail.google.com",
        "mail": "https://mail.google.com",
        "youtube": "https://www.youtube.com",
        "whatsapp": "https://web.whatsapp.com",
        "spotify": "https://open.spotify.com",
        "tradingview": "https://www.tradingview.com",
        "github": "https://github.com",
        "instagram": "https://www.instagram.com",
        "google": "https://www.google.com",
        "bing": "https://www.bing.com",
        "märkte": "https://www.tradingview.com/markets/",
        "maerkte": "https://www.tradingview.com/markets/",
        "marktübersicht": "https://www.tradingview.com/markets/",
        "marktuebersicht": "https://www.tradingview.com/markets/",
    }

    @staticmethod
    def _result(tool, ok, message, **data):
        return {"tool": tool, "ok": ok, "message": message, "data": data}

    @staticmethod
    def _find_executable_in_path(app_name):
        app_name = str(app_name).strip()
        if not app_name:
            return None
        candidates = [app_name, app_name + ".exe", app_name + ".cmd", app_name + ".bat"]
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    @staticmethod
    def _find_browser_binary():
        for name in ("msedge", "chrome", "firefox", "brave", "opera"):
            path = shutil.which(name) or shutil.which(name + ".exe")
            if path:
                return path
        return None

    def _resolve_application_command(self, name):
        key = str(name).strip().lower()
        direct = self.APPLICATIONS.get(key)
        if direct:
            return direct

        if os.name == "nt":
            alias = key.replace(" ", "")
            for candidate in (alias, key):
                for known in self.APPLICATIONS:
                    if known.replace(" ", "") == candidate:
                        return self.APPLICATIONS[known]

        resolved = self._find_executable_in_path(key)
        if resolved:
            return (resolved, os.path.basename(resolved))

        browser = self._find_browser_binary()
        if browser and ("browser" in key or "web" in key or "chrome" in key or "edge" in key or "firefox" in key):
            return (browser, os.path.basename(browser))

        return None

    def open_application(self, name):
        command = self._resolve_application_command(name)
        if not command:
            return self._result(
                "open_application", False,
                "Diese Anwendung ist aus Sicherheitsgründen nicht freigegeben oder nicht installiert.",
            )
        try:
            if os.name == "nt" and hasattr(os, "startfile"):
                os.startfile(command[0])
                return self._result(
                    "open_application", True,
                    f"{command[1]} wird geöffnet.",
                )
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            process = subprocess.Popen(
                [command[0]],
                shell=False,
                close_fds=True,
                creationflags=creationflags,
            )
            return self._result(
                "open_application", True,
                f"{command[1]} wurde geöffnet.",
                pid=process.pid,
            )
        except OSError as exc:
            return self._result("open_application", False, f"Anwendung konnte nicht geöffnet werden: {exc}")

    def open_default_browser(self, target=None):
        if target:
            return self.open_url(target)
        return self.open_url("https://www.google.com")

    def detect_active_window_title(self):
        try:
            if os.name == "nt":
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                return self._result("detect_active_window_title", True, "Aktives Fenster erkannt.", title=title)
        except Exception:
            pass
        return self._result("detect_active_window_title", False, "Aktives Fenster konnte nicht ermittelt werden.")

    def active_context(self):
        """Read the active window and exposed UI metadata without moving input devices."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            context = {"title": title, "hwnd": int(hwnd), "browser_url": None, "controls": []}
            try:
                from pywinauto import Application
                window = Application(backend="uia").connect(handle=hwnd).window(handle=hwnd)
                for control in window.descendants():
                    name = str(control.window_text() or "").strip()
                    control_type = str(control.element_info.control_type or "")
                    if not name and control_type not in {"Edit", "Document"}:
                        continue
                    value = ""
                    try:
                        value = str(control.get_value() or "").strip()
                    except Exception:
                        pass
                    item = {"name": name[:200], "type": control_type, "value": value[:500]}
                    context["controls"].append(item)
                    if control_type == "Edit" and value.startswith(("http://", "https://")):
                        context["browser_url"] = value
                    if len(context["controls"]) >= 120:
                        break
            except (ImportError, OSError, RuntimeError):
                pass
            return self._result("active_context", True, "Aktiver Fensterkontext gelesen.", **context)
        except Exception as exc:
            return self._result("active_context", False, f"Aktiver Fensterkontext nicht verfügbar: {exc}")

    def wait(self, seconds=1.0):
        try:
            import time
            time.sleep(float(seconds))
            return self._result("wait", True, f"Gewartet: {seconds}s", seconds=float(seconds))
        except Exception as exc:
            return self._result("wait", False, f"Warten fehlgeschlagen: {exc}")

    def search_web(self, query, engine="google"):
        cleaned = str(query or "").strip()
        if not cleaned:
            return self._result("search_web", False, "Keine Suchanfrage angegeben.")
        engine_key = str(engine).strip().lower()
        engines = {
            "google": "https://www.google.com/search?q=",
            "bing": "https://www.bing.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
        }
        base = engines.get(engine_key, engines["google"])
        url = base + urllib.parse.quote(cleaned)
        return self.open_url(url)

    def browser_open(self, url, wait_for_load=True):
        """Open a page with the browser engine when Playwright is available."""
        result = self.open_url(url)
        if not result.get("ok"):
            return result
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_open", True, "Browser geöffnet; Playwright-Engine fehlt für Live-Interaktion.", url=url)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded")
                if wait_for_load:
                    page.wait_for_load_state("load", timeout=15000)
                title = page.title()
                text = page.locator("body").inner_text()[:2000]
                browser.close()
                return self._result(
                    "browser_open",
                    True,
                    f"Seite geöffnet und geladen: {title}",
                    url=url,
                    title=title,
                    text=text,
                )
        except Exception as exc:
            return self._result("browser_open", True, f"URL geöffnet, aber Live-Browser-Check fehlgeschlagen: {exc}", url=url)

    def browser_click(self, url, selector=None, text=None, timeout=15000):
        """Find a visible page element by selector or text and click it."""
        if not selector and not text:
            return self._result("browser_click", False, "Kein Selektor oder Text für Klick angegeben.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_click", False, "Playwright fehlt; Live-Browser-Klick nicht verfügbar.")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                target = selector or f"xpath=//*[contains(normalize-space(.), '{text}')]"
                page.locator(target).first.click(timeout=timeout)
                browser.close()
                return self._result("browser_click", True, f"Element geklickt: {selector or text}", url=url)
        except Exception as exc:
            return self._result("browser_click", False, f"Klick fehlgeschlagen: {exc}")

    def browser_fill(self, url, selector, value, timeout=15000):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_fill", False, "Playwright fehlt; Browser-Feld Eingabe nicht verfügbar.")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                page.locator(selector).fill(value)
                browser.close()
                return self._result("browser_fill", True, f"Feld gefüllt: {selector}", url=url)
        except Exception as exc:
            return self._result("browser_fill", False, f"Füllen fehlgeschlagen: {exc}")

    def browser_get_text(self, url, selector="body", timeout=15000):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_get_text", False, "Playwright fehlt; Browser-Lesezugriff nicht verfügbar.")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                text = page.locator(selector).inner_text()
                browser.close()
                return self._result("browser_get_text", True, "Seiteninhalt gelesen.", url=url, text=text[:4000])
        except Exception as exc:
            return self._result("browser_get_text", False, f"Lesen fehlgeschlagen: {exc}")

    def browser_snapshot(self, url, selector="body", timeout=15000):
        """Return a compact, structured snapshot of a page for the next decision step."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_snapshot", False, "Playwright fehlt; Browser-Snapshot nicht verfügbar.")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1200})
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                title = page.title()
                visible_text = page.locator(selector).inner_text()
                url_value = page.url
                browser.close()
                return self._result(
                    "browser_snapshot",
                    True,
                    "Browser-Snapshot erfasst.",
                    url=url_value,
                    title=title,
                    text=(visible_text or "")[:4000],
                )
        except Exception as exc:
            return self._result("browser_snapshot", False, f"Snapshot fehlgeschlagen: {exc}")

    def youtube_video_analysis(self, url, frames=5, every_second=False, timeout=25000):
        """Capture a few YouTube frames, collect visible page text, and OCR the images."""
        candidate = str(url or "").strip()
        if not candidate:
            return self._result("youtube_video_analysis", False, "Keine YouTube-URL angegeben.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("youtube_video_analysis", False, "Playwright fehlt; YouTube-Videoanalyse nicht verfügbar.")
        try:
            import pytesseract
            from PIL import Image, ImageChops, ImageStat
            if not shutil.which("tesseract"):
                for executable in (
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ):
                    if Path(executable).is_file():
                        pytesseract.pytesseract.tesseract_cmd = executable
                        break
        except ImportError as exc:
            return self._result("youtube_video_analysis", False, f"OCR-Abhängigkeiten fehlen: {exc}")

        output_dir = Path(__file__).resolve().parents[1] / "data" / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        image_paths = []
        frame_records = []
        page_body_text = ""
        duration = 0.0

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 980})
                page.goto(candidate, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_load_state("load", timeout=timeout)
                consent_labels = (
                    "Alle akzeptieren", "Akzeptieren", "Accept all", "I agree",
                )
                for label in consent_labels:
                    try:
                        page.get_by_role("button", name=label, exact=True).first.click(timeout=1500)
                        page.wait_for_timeout(700)
                        break
                    except Exception:
                        continue
                try:
                    page.locator("button[aria-label*='accept' i], button[aria-label*='akzept' i]").first.click(timeout=1500)
                    page.wait_for_timeout(700)
                except Exception:
                    pass

                title = page.title()
                page_body_text = (page.locator("body").inner_text() or "")[:6000]
                try:
                    page.wait_for_function("() => !!document.querySelector('video')", timeout=10000)
                    try:
                        page.wait_for_function(
                            "() => { const v = document.querySelector('video'); "
                            "return v && Number.isFinite(v.duration) && v.duration > 0; }",
                            timeout=10000,
                        )
                    except Exception:
                        pass
                    duration = page.evaluate("() => { const v = document.querySelector('video'); return v ? v.duration || 0 : 0; }")
                    page.evaluate(
                        "() => { const v = document.querySelector('video'); "
                        "if (v) { v.muted = true; v.play().catch(() => {}); } }"
                    )
                    page.wait_for_timeout(1200)
                    if every_second and duration and duration > 0:
                        target_frames = max(1, int(duration))
                    else:
                        target_frames = max(1, min(int(frames), 8))
                    if duration and duration > 0:
                        for index in range(target_frames):
                            if every_second:
                                seek_to = min(max(0.5, index + 0.5), max(0.5, duration - 0.5))
                            else:
                                seek_to = max(0.5, min(duration - 0.5, ((index + 1) * duration) / (target_frames + 1)))
                            page.evaluate(f"() => {{ const v = document.querySelector('video'); if (v) v.currentTime = {seek_to}; return true; }}")
                            page.wait_for_timeout(450 if every_second else 1000 + index * 300)
                            frame_path = output_dir / f"youtube_frame_{index + 1}_{int(__import__('time').time())}.png"
                            video = page.locator("video").first
                            if video.count():
                                video.screenshot(path=str(frame_path))
                            else:
                                page.screenshot(path=str(frame_path), full_page=False)
                            image_paths.append(str(frame_path))
                            frame_records.append({"index": index + 1, "seconds": round(seek_to, 2), "path": str(frame_path)})
                    else:
                        for index in range(target_frames):
                            page.wait_for_timeout(1000 + index * 300)
                            frame_path = output_dir / f"youtube_frame_{index + 1}_{int(__import__('time').time())}.png"
                            video = page.locator("video").first
                            if video.count():
                                video.screenshot(path=str(frame_path))
                            else:
                                page.screenshot(path=str(frame_path), full_page=False)
                            image_paths.append(str(frame_path))
                            frame_records.append({"index": index + 1, "seconds": None, "path": str(frame_path)})
                except Exception:
                    fallback_frames = max(1, int(duration)) if every_second and duration else max(1, min(int(frames), 5))
                    for index in range(fallback_frames):
                        page.wait_for_timeout(450 if every_second else 1000 + index * 300)
                        frame_path = output_dir / f"youtube_frame_{index + 1}_{int(__import__('time').time())}.png"
                        video = page.locator("video").first
                        if video.count():
                            video.screenshot(path=str(frame_path))
                        else:
                            page.screenshot(path=str(frame_path), full_page=False)
                        image_paths.append(str(frame_path))
                        frame_records.append({"index": index + 1, "seconds": None, "path": str(frame_path)})
                browser.close()

            ocr_chunks = []
            scene_lines = []
            previous = None
            for record in frame_records:
                frame_path = record["path"]
                try:
                    image = Image.open(frame_path)
                    try:
                        text = pytesseract.image_to_string(image, lang="eng")
                        clean = " ".join(str(text).split())
                    except Exception:
                        clean = ""
                    if clean:
                        ocr_chunks.append(f"[{record['seconds'] or '?'}s] {clean}")
                    small = image.convert("RGB").resize((96, 54))
                    brightness = round(ImageStat.Stat(small).mean[0], 1)
                    change = None
                    if previous is not None:
                        diff = ImageChops.difference(previous, small)
                        change = round(ImageStat.Stat(diff).mean[0], 1)
                    previous = small
                    if change is None:
                        scene_type = "Startbild"
                    elif change >= 24:
                        scene_type = "wahrscheinlicher Szenenwechsel"
                    elif change >= 10:
                        scene_type = "deutliche Bildänderung"
                    else:
                        scene_type = "ähnliche Szene"
                    scene_lines.append(
                        f"Frame {record['index']} bei {record['seconds'] or '?'}s: "
                        f"{scene_type}, Helligkeit {brightness}, Änderung {change if change is not None else '-'}"
                    )
                except Exception:
                    continue

            visual_text = "\n".join(ocr_chunks)[:12000]
            scene_report = "\n".join(scene_lines)
            return self._result(
                "youtube_video_analysis",
                True,
                "YouTube-Video wurde pro Sekunde auf Frames, Szenenwechsel, Seitentext und OCR-Text analysiert."
                if every_second else
                "YouTube-Video wurde zeitlich verteilt auf Frames, Szenenwechsel, Seitentext und OCR-Text analysiert.",
                url=candidate,
                title=title,
                frames=image_paths,
                frame_records=frame_records,
                duration_seconds=duration if "duration" in locals() else None,
                page_text=page_body_text,
                ocr_text=visual_text,
                scene_report=scene_report,
            )
        except Exception as exc:
            return self._result("youtube_video_analysis", False, f"YouTube-Videoanalyse fehlgeschlagen: {exc}")

    def browser_search_and_open(self, query, engine="google", result_index=0, timeout=20000):
        """Search a query, then open the Nth result in a headless browser and return a summary."""
        cleaned = str(query or "").strip()
        if not cleaned:
            return self._result("browser_search_and_open", False, "Keine Suchanfrage angegeben.")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._result("browser_search_and_open", False, "Playwright fehlt; Such-Openflow nicht verfügbar.")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1200})

                def fetch_link(search_page):
                    links = []
                    anchors = search_page.locator("a[href]")
                    for index in range(min(anchors.count(), 60)):
                        anchor = anchors.nth(index)
                        href = (anchor.get_attribute("href") or "").strip()
                        text = (anchor.inner_text() or "").strip()
                        if not href or href in {"#", "javascript:void(0)"}:
                            continue
                        if text.lower() in {"alle akzeptieren", "alle ablehnen", "weitere optionen", "datenschutz", "nutzungsbedingungen", "google"}:
                            continue
                        if href.startswith("/url?"):
                            href = "https://www.google.com" + href
                        elif href.startswith("/search?"):
                            href = "https://www.google.com" + href
                        elif href.startswith("/"):
                            href = "https://www.google.com" + href
                        if href.startswith("http") and "google.com" not in href:
                            links.append(href)
                    return links

                search_url = {
                    "google": "https://www.google.com/search?q=" + urllib.parse.quote(cleaned),
                    "bing": "https://www.bing.com/search?q=" + urllib.parse.quote(cleaned),
                    "duckduckgo": "https://duckduckgo.com/?q=" + urllib.parse.quote(cleaned),
                }.get(str(engine).lower(), "https://www.google.com/search?q=" + urllib.parse.quote(cleaned))
                page.goto(search_url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                links = fetch_link(page)
                if not links and str(engine).lower() == "google":
                    fallback_url = "https://www.bing.com/search?q=" + urllib.parse.quote(cleaned)
                    page.goto(fallback_url, wait_until="domcontentloaded")
                    page.wait_for_load_state("load", timeout=timeout)
                    links = fetch_link(page)
                if not links:
                    browser.close()
                    return self._result("browser_search_and_open", False, "Keine Suchergebnisse gefunden.", query=cleaned)
                resolved_url = links[max(0, int(result_index))]
                page.goto(resolved_url, wait_until="domcontentloaded")
                page.wait_for_load_state("load", timeout=timeout)
                snippet = (page.locator("body").inner_text() or "")[:2000]
                title = page.title()
                browser.close()
                return self._result(
                    "browser_search_and_open",
                    True,
                    f"Ergebnis {result_index} geöffnet: {resolved_url}",
                    query=cleaned,
                    url=resolved_url,
                    title=title,
                    text=snippet,
                )
        except Exception as exc:
            return self._result("browser_search_and_open", False, f"Such-Openflow fehlgeschlagen: {exc}")

    def capture_screen(self, filename=None):
        """Capture a screenshot into a safe local path for verification."""
        save_path = Path(filename).expanduser() if filename else Path.home() / "Desktop" / "jarvis_capture.png"
        try:
            import pyautogui
            resolved = save_path if save_path.is_absolute() else (Path.cwd() / save_path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            image = pyautogui.screenshot()
            image.save(str(resolved))
            return self._result("capture_screen", True, f"Screenshot gespeichert: {resolved}", path=str(resolved))
        except ImportError:
            return self._result("capture_screen", False, "Screenshot fehlt: pyautogui ist nicht installiert.")
        except Exception as exc:
            return self._result("capture_screen", False, f"Screenshot fehlgeschlagen: {exc}")

    def focus_window(self, title):
        target = str(title or "").strip()
        if not target:
            return self._result("focus_window", False, "Kein Fenstername angegeben.")
        try:
            if os.name == "nt":
                safe_target = target.replace("'", "''")
                cmd = (
                    "$ws = New-Object -ComObject WScript.Shell; "
                    + f"$ws.AppActivate('{safe_target}'); "
                    + "exit 0"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False, shell=False, capture_output=True)
                return self._result("focus_window", True, f"Fenster fokussiert: {target}")
            return self._result("focus_window", False, "Window-Fokus ist aktuell nur für Windows sicher implementiert.")
        except Exception as exc:
            return self._result("focus_window", False, f"Fenster fokussieren fehlgeschlagen: {exc}")

    def read_clipboard(self):
        try:
            import pyperclip
            return self._result("read_clipboard", True, "Inhalt aus Zwischenablage gelesen.", text=pyperclip.paste())
        except ImportError:
            return self._result("read_clipboard", False, "Clipboard-Unterstützung fehlt: pyperclip ist nicht installiert.")
        except Exception as exc:
            return self._result("read_clipboard", False, f"Clipboard lesen fehlgeschlagen: {exc}")

    def write_clipboard(self, text):
        value = str(text or "")
        try:
            import pyperclip
            pyperclip.copy(value)
            return self._result("write_clipboard", True, "Text in Zwischenablage kopiert.", text=value)
        except ImportError:
            return self._result("write_clipboard", False, "Clipboard-Unterstützung fehlt: pyperclip ist nicht installiert.")
        except Exception as exc:
            return self._result("write_clipboard", False, f"Clipboard schreiben fehlgeschlagen: {exc}")

    @staticmethod
    def _normalize_url(value):
        raw = str(value or "").strip()
        if not raw:
            return None, "Keine URL angegeben."
        lower = raw.lower()
        if lower in DesktopControls.WEBSITES:
            return DesktopControls.WEBSITES[lower], None
        if re.match(r"^[a-z][a-z0-9+.-]*$", raw, re.IGNORECASE) and "." not in raw:
            return "https://www.google.com/search?q=" + urllib.parse.quote(raw), None
        if re.match(r"^[a-z][a-z0-9+.-]*$", raw, re.IGNORECASE) and "." in raw:
            return "https://" + raw, None
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.IGNORECASE) and not re.match(r"^https?://", raw, re.IGNORECASE):
            return None, "Nur sichere http(s)-Adressen dürfen geöffnet werden."
        if not re.match(r"^https?://", raw, re.IGNORECASE):
            return "https://www.google.com/search?q=" + urllib.parse.quote(raw), None
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None, "Nur sichere http(s)-Adressen dürfen geöffnet werden."
        return raw, None

    def open_url(self, url):
        value, error = self._normalize_url(url)
        if error:
            return self._result("open_url", False, error)
        if not value:
            return self._result("open_url", False, "Keine URL angegeben.")
        try:
            if not webbrowser.open(value):
                return self._result("open_url", False, "Der Browser konnte nicht geöffnet werden.")
            return self._result("open_url", True, f"Geöffnet: {value}", url=value)
        except Exception as exc:
            return self._result("open_url", False, f"Browser konnte nicht geöffnet werden: {exc}")

    def open_file(self, filename):
        raw = str(filename).strip().strip('"')
        if not raw:
            return self._result("open_file", False, "Keine Datei angegeben.")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            path = path.resolve()
        except OSError:
            return self._result("open_file", False, "Der Dateipfad ist ungültig.")
        if not path.exists() or not path.is_file():
            return self._result("open_file", False, f"Datei nicht gefunden: {path}")
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)], shell=False)
            return self._result("open_file", True, f"Datei geöffnet: {path}", path=str(path))
        except OSError as exc:
            return self._result("open_file", False, f"Datei konnte nicht geöffnet werden: {exc}")

    def open_folder(self, directory="."):
        path = Path(str(directory).strip().strip('"') or ".").expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            path = path.resolve()
        except OSError:
            return self._result("open_folder", False, "Der Ordnerpfad ist ungültig.")
        if not path.exists() or not path.is_dir():
            return self._result("open_folder", False, f"Ordner nicht gefunden: {path}")
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)], shell=False)
            return self._result("open_folder", True, f"Ordner geöffnet: {path}", path=str(path))
        except OSError as exc:
            return self._result("open_folder", False, f"Ordner konnte nicht geöffnet werden: {exc}")

    def list_files(self, directory="."):
        path = Path(str(directory).strip() or ".").expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            path = path.resolve()
            if not path.is_dir():
                return self._result("list_files", False, f"Ordner nicht gefunden: {path}")
            entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            names = [f"[Ordner] {entry.name}" if entry.is_dir() else entry.name for entry in entries[:50]]
            suffix = "\n(Weitere Einträge wurden ausgeblendet.)" if len(entries) > 50 else ""
            return self._result("list_files", True, "\n".join(names) + suffix if names else "Der Ordner ist leer.", path=str(path))
        except OSError as exc:
            return self._result("list_files", False, f"Ordner konnte nicht gelesen werden: {exc}")

    @staticmethod
    def _resolve_local_path(value, default="."):
        raw = str(value if value is not None else default).strip().strip('"')
        path = Path(raw or default).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def create_folder(self, directory):
        try:
            path = self._resolve_local_path(directory)
            path.mkdir(parents=True, exist_ok=False)
            return self._result("create_folder", True, f"Ordner erstellt: {path}", path=str(path))
        except FileExistsError:
            return self._result("create_folder", False, f"Ordner existiert bereits: {directory}")
        except (OSError, ValueError) as exc:
            return self._result("create_folder", False, f"Ordner konnte nicht erstellt werden: {exc}")

    def move_path(self, source, destination):
        try:
            source_path = self._resolve_local_path(source)
            destination_path = self._resolve_local_path(destination)
            if not source_path.exists():
                return self._result("move_path", False, f"Quelle nicht gefunden: {source_path}")
            if destination_path.exists():
                return self._result("move_path", False, f"Ziel existiert bereits: {destination_path}")
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(destination_path))
            return self._result(
                "move_path", True, f"Verschoben: {source_path} -> {destination_path}",
                source=str(source_path), destination=str(destination_path),
            )
        except (OSError, ValueError) as exc:
            return self._result("move_path", False, f"Verschieben fehlgeschlagen: {exc}")

    def delete_path(self, path, recursive=False):
        try:
            target = self._resolve_local_path(path)
            if not target.exists():
                return self._result("delete_path", False, f"Pfad nicht gefunden: {target}")
            if target.is_dir():
                if not recursive:
                    return self._result(
                        "delete_path", False,
                        "Ordner ist nicht leer oder rekursives Löschen wurde nicht freigegeben.",
                    )
                shutil.rmtree(target)
            else:
                target.unlink()
            return self._result("delete_path", True, f"Gelöscht: {target}", path=str(target))
        except (OSError, ValueError) as exc:
            return self._result("delete_path", False, f"Löschen fehlgeschlagen: {exc}")

    def position_window(self, title, x, y, width=None, height=None):
        target = str(title or "").strip()
        if not target:
            return self._result("position_window", False, "Kein Fenstername angegeben.")
        if os.name != "nt":
            return self._result("position_window", False, "Fensterpositionierung ist nur unter Windows verfügbar.")
        try:
            import win32gui
            matches = []

            def collect(hwnd, _):
                caption = win32gui.GetWindowText(hwnd)
                if caption and target.lower() in caption.lower():
                    matches.append(hwnd)

            win32gui.EnumWindows(collect, None)
            if not matches:
                return self._result("position_window", False, f"Fenster nicht gefunden: {target}")
            hwnd = matches[0]
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            new_width = int(width) if width is not None else right - left
            new_height = int(height) if height is not None else bottom - top
            win32gui.SetWindowPos(hwnd, 0, int(x), int(y), new_width, new_height, 0x0040)
            return self._result(
                "position_window", True, f"Fenster positioniert: {target}",
                title=win32gui.GetWindowText(hwnd), x=int(x), y=int(y),
                width=new_width, height=new_height,
            )
        except ImportError:
            return self._result("position_window", False, "Windows-Fenstersteuerung fehlt: Installiere pywin32.")
        except (OSError, TypeError, ValueError) as exc:
            return self._result("position_window", False, f"Fenster konnte nicht positioniert werden: {exc}")

    def type_text(self, text, interval=0.01):
        value = str(text)
        if not value:
            return self._result("type_text", False, "Kein Text angegeben.")
        try:
            import pyautogui
            # Clipboard paste preserves German and other non-ASCII characters.
            try:
                import pyperclip
                pyperclip.copy(value)
                pyautogui.hotkey("ctrl", "v")
            except ImportError:
                pyautogui.write(value, interval=float(interval))
            return self._result("type_text", True, "Text wurde in das aktive Fenster eingegeben.")
        except ImportError:
            return self._result("type_text", False, "Tastatursteuerung fehlt: Installiere pyautogui.")
        except Exception as exc:
            return self._result("type_text", False, f"Text konnte nicht eingegeben werden: {exc}")

    def press_key(self, key):
        value = str(key).strip()
        if not value:
            return self._result("press_key", False, "Keine Taste angegeben.")
        try:
            import pyautogui
            pyautogui.press(value)
            return self._result("press_key", True, f"Taste {value} wurde gedrückt.")
        except ImportError:
            return self._result("press_key", False, "Tastatursteuerung fehlt: Installiere pyautogui.")
        except Exception as exc:
            return self._result("press_key", False, f"Taste konnte nicht gedrückt werden: {exc}")

    def hotkey(self, keys):
        values = [str(key).strip() for key in keys if str(key).strip()]
        if not values:
            return self._result("hotkey", False, "Keine Tastenkombination angegeben.")
        try:
            import pyautogui
            pyautogui.hotkey(*values)
            return self._result("hotkey", True, f"Tastenkombination {'+'.join(values)} wurde ausgeführt.")
        except ImportError:
            return self._result("hotkey", False, "Tastatursteuerung fehlt: Installiere pyautogui.")
        except Exception as exc:
            return self._result("hotkey", False, f"Tastenkombination fehlgeschlagen: {exc}")

    def mouse_move(self, x, y):
        try:
            import pyautogui
            pyautogui.moveTo(int(x), int(y), duration=0.2)
            return self._result("mouse_move", True, f"Maus bewegt nach ({x}, {y}).", x=int(x), y=int(y))
        except ImportError:
            return self._result("mouse_move", False, "Maussteuerung fehlt: Installiere pyautogui.")
        except (TypeError, ValueError) as exc:
            return self._result("mouse_move", False, f"Ungültige Mauskoordinaten: {exc}")
        except Exception as exc:
            return self._result("mouse_move", False, f"Mausbewegung fehlgeschlagen: {exc}")

    def mouse_scroll(self, amount=0):
        try:
            import pyautogui
            pyautogui.scroll(int(amount))
            return self._result("mouse_scroll", True, f"Bildlauf ausgeführt: {amount}.", amount=int(amount))
        except ImportError:
            return self._result("mouse_scroll", False, "Maussteuerung fehlt: Installiere pyautogui.")
        except (TypeError, ValueError) as exc:
            return self._result("mouse_scroll", False, f"Ungültiger Bildlaufwert: {exc}")
        except Exception as exc:
            return self._result("mouse_scroll", False, f"Bildlauf fehlgeschlagen: {exc}")

    def click(self, x=None, y=None, button="left"):
        try:
            import pyautogui
            if x is None or y is None:
                pyautogui.click(button=button)
            else:
                pyautogui.click(int(x), int(y), button=button)
            return self._result("click", True, "Mausklick wurde ausgeführt.")
        except ImportError:
            return self._result("click", False, "Maussteuerung fehlt: Installiere pyautogui.")
        except (TypeError, ValueError) as exc:
            return self._result("click", False, f"Ungültige Mauskoordinaten: {exc}")
        except Exception as exc:
            return self._result("click", False, f"Mausklick fehlgeschlagen: {exc}")

    def list_windows(self):
        try:
            if os.name != "nt":
                return self._result("list_windows", False, "Fensterauflistung ist aktuell nur unter Windows verfügbar.")
            import win32gui
            titles = []
            def enum_windows(hwnd, result):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    result.append(title)
            windows = []
            win32gui.EnumWindows(enum_windows, windows)
            unique = sorted(set(windows), key=lambda item: item.lower())
            titles = unique[:50]
            return self._result("list_windows", True, "Offene Fenster aufgelistet.", windows=titles)
        except Exception as exc:
            return self._result("list_windows", False, f"Fensterauflistung fehlgeschlagen: {exc}")

    def system_status(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return self._result(
                "system_status",
                True,
                "Systemstatus gelesen.",
                cpu_percent=cpu,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                memory_used_gb=round(memory.used / (1024 ** 3), 2),
                disk_used_gb=round(disk.used / (1024 ** 3), 2),
            )
        except ImportError:
            return self._result("system_status", False, "psutil fehlt; Systemstatus nicht verfügbar.")
        except Exception as exc:
            return self._result("system_status", False, f"Systemstatus fehlgeschlagen: {exc}")

    def ocr_image(self, path, language="eng"):
        candidate = str(path or "").strip()
        if not candidate:
            return self._result("ocr_image", False, "Kein Bildpfad angegeben.")
        try:
            from PIL import Image
            import pytesseract
            if not shutil.which("tesseract"):
                for executable in (
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ):
                    if Path(executable).is_file():
                        pytesseract.pytesseract.tesseract_cmd = executable
                        break
            image = Image.open(candidate)
            text = pytesseract.image_to_string(image, lang=language)
            return self._result(
                "ocr_image",
                True,
                "Bildtext erkannt.",
                path=candidate,
                text=(text or "").strip(),
            )
        except ImportError as exc:
            return self._result("ocr_image", False, f"OCR fehlt: {exc}")
        except Exception as exc:
            return self._result("ocr_image", False, f"OCR fehlgeschlagen: {exc}")

    @staticmethod
    def _window_title_patterns(window_title):
        normalized = str(window_title or "").strip().lower()
        aliases = {
            "notepad": [r".*notepad.*", r".*editor.*"],
            "editor": [r".*notepad.*", r".*editor.*"],
            "calculator": [r".*rechner.*", r".*calculator.*"],
            "rechner": [r".*rechner.*", r".*calculator.*"],
            "browser": [r".*edge.*", r".*chrome.*", r".*browser.*"],
            "edge": [r".*edge.*"],
            "chrome": [r".*chrome.*"],
            "vscode": [r".*visual studio code.*", r".*code.*"],
            "outlook": [r".*outlook.*"],
            "explorer": [r".*dateien.*", r".*explorer.*"],
        }
        patterns = [rf"(?i).*{re.escape(str(window_title).strip())}.*"]
        if normalized in aliases:
            patterns = [f"(?i){p}" for p in aliases[normalized]] + patterns
        for alias in aliases:
            if normalized and alias in normalized:
                patterns = [f"(?i){p}" for p in aliases[alias]] + patterns
        return list(dict.fromkeys(patterns))

    def ui_click_visible_text(self, window_title, text, timeout=15):
        target = str(window_title or "").strip()
        label = str(text or "").strip()
        if not target or not label:
            return self._result("ui_click_visible_text", False, "Fenstername und Buttontext müssen angegeben werden.")
        try:
            from pywinauto import Application, findwindows
            hwnds = []
            for pattern in self._window_title_patterns(target):
                hwnds.extend(findwindows.find_windows(title_re=pattern))
            if not hwnds:
                return self._result("ui_click_visible_text", False, f"Fenster '{target}' nicht gefunden.")
            hwnd = hwnds[0]
            app = Application(backend="uia").connect(handle=hwnd)
            window = app.window(handle=hwnd)
            for key in (label, f".*{re.escape(label)}.*"):
                try:
                    control = window.child_window(title=key, control_type="MenuItem")
                    control.click_input()
                    return self._result("ui_click_visible_text", True, f"UI-Klick ausgeführt: {label}", window=target, text=label)
                except Exception:
                    pass
                try:
                    control = window.child_window(title_re=f".*{re.escape(label)}.*", control_type="Button")
                    control.click_input()
                    return self._result("ui_click_visible_text", True, f"UI-Klick ausgeführt: {label}", window=target, text=label)
                except Exception:
                    pass
            try:
                window.menu_item(label).click_input()
                return self._result("ui_click_visible_text", True, f"UI-Klick ausgeführt: {label}", window=target, text=label)
            except Exception:
                pass
            window.set_focus()
            window.type_keys("{ENTER}")
            return self._result("ui_click_visible_text", True, f"Fenster fokussiert und Enter ausgelöst: {label}", window=target, text=label)
        except Exception as exc:
            return self._result("ui_click_visible_text", False, f"UI-Klick fehlgeschlagen: {exc}")

    def ui_inspect(self, window_title="", timeout=5):
        """Read the Windows UI tree so actions can target controls, not pixels."""
        target = str(window_title or "").strip()
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows(
                title_re=self._window_title_patterns(target)[0] if target else ".*"
            )
            if not windows:
                return self._result("ui_inspect", False, f"Fenster '{target}' nicht gefunden.")
            window = windows[0]
            controls = []
            for control in window.descendants():
                name = str(control.window_text() or "").strip()
                if not name:
                    continue
                try:
                    rect = control.rectangle()
                    bounds = {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
                except Exception:
                    bounds = None
                controls.append({
                    "name": name[:200],
                    "type": str(control.element_info.control_type or ""),
                    "bounds": bounds,
                })
                if len(controls) >= 200:
                    break
            return self._result("ui_inspect", True, "Windows-UI gelesen.", window=target, controls=controls)
        except ImportError as exc:
            return self._result("ui_inspect", False, f"Windows-UI-Automation fehlt: {exc}")
        except Exception as exc:
            return self._result("ui_inspect", False, f"Windows-UI konnte nicht gelesen werden: {exc}")

    def ui_fill_visible_field(self, window_title, field_name, value, timeout=15):
        target = str(window_title or "").strip()
        field = str(field_name or "").strip()
        if not target or not field:
            return self._result("ui_fill_visible_field", False, "Fenstername und Feldname müssen angegeben werden.")
        try:
            from pywinauto import Application, findwindows
            hwnds = []
            for pattern in self._window_title_patterns(target):
                hwnds.extend(findwindows.find_windows(title_re=pattern))
            if not hwnds:
                return self._result("ui_fill_visible_field", False, f"Fenster '{target}' nicht gefunden.")
            hwnd = hwnds[0]
            app = Application(backend="uia").connect(handle=hwnd)
            window = app.window(handle=hwnd)
            for candidate in (
                window.child_window(title_re=f".*{re.escape(field)}.*", control_type="Edit"),
                window.child_window(title_re=f".*{re.escape(field)}.*", control_type="Document"),
                window.child_window(best_match="Edit"),
                window.child_window(best_match="Document"),
            ):
                try:
                    candidate.set_focus()
                    candidate.type_keys(str(value), with_spaces=True)
                    return self._result("ui_fill_visible_field", True, f"Feld gefüllt: {field}", window=target, field=field, value=str(value))
                except Exception:
                    pass
            window.set_focus()
            window.type_keys(str(value), with_spaces=True)
            return self._result("ui_fill_visible_field", True, f"Text in Fenster eingegeben: {value}", window=target, field=field, value=str(value))
        except Exception as exc:
            return self._result("ui_fill_visible_field", False, f"Feldfüllung fehlgeschlagen: {exc}")

    def ui_run_app_flow(self, app_name, steps=None):
        app_key = str(app_name or "").strip().lower()
        if not app_key:
            return self._result("ui_run_app_flow", False, "Keine App angegeben.")
        flow = steps or []
        if not isinstance(flow, list):
            flow = [{"action": "open", "target": app_key}]
        results = []
        if app_key:
            open_result = self.open_application(app_key)
            results.append({"tool": "open_application", "result": open_result})
            if not open_result.get("ok"):
                return {"ok": False, "results": results, "message": open_result.get("message", "App konnte nicht gestartet werden.")}
        failed = False
        for step in flow:
            if not isinstance(step, dict):
                continue
            action = str(step.get("action") or "").lower()
            target = str(step.get("target") or "").strip()
            value = step.get("value", "")
            if action in {"click", "button", "press"} and target:
                result = self.ui_click_visible_text(target.split("::", 1)[0] if "::" in target else app_key, target.split("::", 1)[1] if "::" in target else target)
                results.append({"tool": "ui_click_visible_text", "result": result})
                failed = failed or not result.get("ok", False)
            elif action in {"fill", "type", "input"} and target:
                result = self.ui_fill_visible_field(app_key, target, value)
                results.append({"tool": "ui_fill_visible_field", "result": result})
                failed = failed or not result.get("ok", False)
        return {"ok": not failed, "results": results, "message": f"App-Flow für {app_key} {'erfolgreich ausgeführt.' if not failed else 'fehlgeschlagen.'}"}


class DesktopWorkflowOrchestrator:
    """Run a real local orchestration across browser and desktop actions with verification."""

    def __init__(self, desktop, browser=None):
        self.desktop = desktop
        self.browser = browser

    def execute(self, steps):
        if not isinstance(steps, list) or not steps:
            return {"ok": False, "message": "Keine Orchestrierungs-Schritte angegeben."}
        results = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            tool_name = str(step.get("tool") or "").strip()
            args = dict(step.get("arguments", {}))
            if not tool_name:
                continue
            if tool_name == "open_application":
                result = self.desktop.open_application(args.get("name") or args.get("app"))
            elif tool_name == "browser_search_and_open":
                result = self.desktop.browser_search_and_open(args.get("query"), engine=args.get("engine", "google"))
            elif tool_name == "browser_navigate":
                result = self.browser.navigate(args.get("url")) if self.browser else self.desktop.open_url(args.get("url"))
            elif tool_name == "system_status":
                result = self.desktop.system_status()
            elif tool_name == "capture_screen":
                result = self.desktop.capture_screen(args.get("filename"))
            elif tool_name == "ui_click_visible_text":
                result = self.desktop.ui_click_visible_text(args.get("window_title") or args.get("title"), args.get("text"))
            elif tool_name == "ui_fill_visible_field":
                result = self.desktop.ui_fill_visible_field(args.get("window_title") or args.get("title"), args.get("field_name") or args.get("field"), args.get("value", ""))
            elif tool_name == "ui_run_app_flow":
                result = self.desktop.ui_run_app_flow(args.get("app_name") or args.get("app"), args.get("steps", []))
            elif tool_name == "detect_active_window_title":
                result = self.desktop.detect_active_window_title()
            elif tool_name == "active_context":
                result = self.desktop.active_context()
            elif tool_name == "wait":
                result = self.desktop.wait(args.get("seconds", 1.0))
            else:
                result = {"tool": tool_name, "ok": False, "message": "Unbekannter Orchestrierungs-Schritt."}
            results.append({"tool": tool_name, "result": result})
            if not result.get("ok"):
                return {"ok": False, "results": results, "message": result.get("message", "Orchestrierungs-Schritt fehlgeschlagen.")}
        return {"ok": True, "results": results, "message": "Desktop-/Browser-Orchestrierung erfolgreich ausgeführt."}


@dataclass
class AgentMessage:
    """Auditable message exchanged by the local orchestration roles."""

    sender: str
    recipient: str
    content: str
    step: int = 0


class MultiAgentOrchestrator:
    """Coordinate planner, operator and verifier roles over shared local context.

    This is deliberately local and deterministic: roles are lightweight protocol
    participants, while all real actions still go through ``execute_structured``
    and its allowlists/confirmation checks.
    """

    ROLE_BY_TOOL = {
        "detect_active_window_title": "verifier",
        "system_status": "verifier",
        "capture_screen": "verifier",
        "browser_get_text": "verifier",
        "browser_snapshot": "verifier",
    }

    def __init__(self, executor):
        self.executor = executor
        self.roles = self._load_roles()

    @staticmethod
    def _load_roles():
        path = Path(__file__).resolve().parents[1] / "config" / "agent_roles.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("roles", {})
        except (OSError, ValueError):
            return {}

    def role_for_request(self, request):
        """Select the specialists that should participate in a request."""
        text = str(request or "").lower()
        roles = ["planner"]
        if any(word in text for word in ("aktuell", "news", "suche", "preis", "recherche")):
            roles.append("researcher")
        if any(word in text for word in (
            "öffne", "oeffne", "starte", "klick", "schreibe", "tippe",
            "browser", "app", "fenster", "desktop", "chart",
        )):
            roles.append("operator")
        if any(word in text for word in (
            "code", "python", "fehler", "debug", "projekt", "testen", "reparier",
        )):
            roles.append("coder")
        if any(word in text for word in ("merk dir", "merke", "präferenz", "vorliebe")):
            roles.append("memory")
        roles.append("verifier")
        return list(dict.fromkeys(roles))

    @staticmethod
    def _serializable(value, seen=None):
        """Keep protocol results safe to pass through JSON/API boundaries."""
        if seen is None:
            seen = set()
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        identity = id(value)
        if identity in seen:
            return "<circular>"
        if isinstance(value, dict):
            seen.add(identity)
            result = {str(key): MultiAgentOrchestrator._serializable(item, seen)
                      for key, item in value.items()}
            seen.discard(identity)
            return result
        if isinstance(value, (list, tuple, set)):
            seen.add(identity)
            result = [MultiAgentOrchestrator._serializable(item, seen) for item in value]
            seen.discard(identity)
            return result
        return str(value)

    @staticmethod
    def _role_for(step):
        return str(step.get("role") or "").strip().lower() or MultiAgentOrchestrator.ROLE_BY_TOOL.get(
            str(step.get("tool") or "").strip(), "operator"
        )

    @staticmethod
    def _verify(result, expected=None):
        if not isinstance(result, dict):
            return {"ok": False, "message": "Agent-Ergebnis ist nicht serialisierbar."}
        if not result.get("ok"):
            return {"ok": False, "message": result.get("message", "Agent-Schritt fehlgeschlagen.")}
        if expected and isinstance(expected, dict):
            data = result.get("data", {})
            missing = [key for key, value in expected.items() if data.get(key) != value]
            if missing:
                return {"ok": False, "message": f"Verifikation fehlgeschlagen; Werte fehlen: {', '.join(missing)}."}
        return {"ok": True, "message": "Ergebnis bestätigt."}

    def execute(self, steps, request="", confirmed=False, context=None):
        if not isinstance(steps, list) or not steps:
            return {"ok": False, "message": "Keine Agent-Schritte angegeben.", "messages": []}
        shared = dict(context) if isinstance(context, dict) else {}
        shared.update({"request": str(request or shared.get("request", "")), "step_count": len(steps)})
        shared["agent_roles"] = self.role_for_request(shared["request"])
        shared["role_contract"] = {
            role: self.roles.get(role, {}) for role in shared["agent_roles"]
        }
        results, messages = [], []
        read_cache = {}
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict) or not step.get("tool"):
                return {"ok": False, "message": f"Ungültiger Agent-Schritt {index}.", "results": results, "messages": messages, "context": shared}
            tool = str(step["tool"]).strip()
            if tool == "multi_agent_orchestrate":
                return {"ok": False, "message": "Verschachtelte Multi-Agent-Orchestrierung ist nicht erlaubt.", "results": results, "messages": messages, "context": shared}
            role = self._role_for(step)
            messages.append(AgentMessage("planner", role, f"Schritt {index}: {tool}", index).__dict__)
            arguments = dict(step.get("arguments") or {})
            # Status is read-only and can be requested by both planner and verifier.
            # Reuse it within one orchestration, but never cache action results.
            cache_key = (tool, tuple(sorted((str(key), repr(value)) for key, value in arguments.items())))
            if tool == "system_status" and cache_key in read_cache:
                result = read_cache[cache_key]
            else:
                result = self.executor(tool, confirmed=confirmed, **arguments)
                if tool == "system_status" and isinstance(result, dict) and result.get("ok"):
                    read_cache[cache_key] = result
            verification = self._verify(result, step.get("expect"))
            record = {"step": index, "tool": tool, "role": role, "result": result, "verification": verification}
            results.append(record)
            shared["last_result"] = result
            shared["completed_steps"] = index if verification["ok"] else index - 1
            messages.append(AgentMessage(role, "verifier", verification["message"], index).__dict__)
            if not verification["ok"]:
                messages.append(AgentMessage("verifier", "planner", "Ausführung wegen fehlender Verifikation angehalten.", index).__dict__)
                return {"ok": False, "results": results, "messages": messages, "context": shared, "message": verification["message"]}
            messages.append(AgentMessage("verifier", "planner", "Schritt bestätigt.", index).__dict__)
        shared["completed_steps"] = len(results)
        return {"ok": True, "results": results, "messages": messages, "context": shared, "message": "Multi-Agent-Orchestrierung erfolgreich verifiziert."}


class BrowserSession:
    """A small live browser manager for real web actions and verifiable page state."""

    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None
        self.history = []

    @staticmethod
    def _bounded_timeout(timeout, default=20000):
        try:
            value = int(timeout)
        except (TypeError, ValueError):
            value = default
        return max(1, min(value, 120000))

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(f"Playwright fehlt: {exc}") from exc
        self._playwright = sync_playwright()
        self._browser = self._playwright.start().chromium.launch(headless=self.headless)
        self._page = self._browser.new_page(viewport={"width": 1440, "height": 1200})
        return self._page

    def navigate(self, url, timeout=20000):
        value, error = DesktopControls._normalize_url(url)
        if error:
            raise ValueError(error)
        page = self._ensure_page()
        timeout = self._bounded_timeout(timeout)
        page.goto(value, wait_until="domcontentloaded", timeout=timeout)
        # domcontentloaded is the bounded readiness point; waiting for every
        # asset can stall indefinitely on pages with long-lived requests.
        title = page.title()
        record = {"url": page.url, "title": title}
        self.history.append(record)
        return {"ok": True, "url": page.url, "title": title, "text": (page.locator("body").inner_text() or "")[:3000]}

    def history_summary(self, limit=5):
        recent = self.history[-limit:]
        return {"ok": True, "count": len(self.history), "history": recent}

    def search(self, query, engine="google", timeout=20000, result_index=0):
        cleaned = str(query or "").strip()
        if not cleaned:
            raise ValueError("Keine Suchanfrage angegeben.")
        page = self._ensure_page()
        timeout = self._bounded_timeout(timeout)
        search_url = {
            "google": "https://www.google.com/search?q=" + urllib.parse.quote(cleaned),
            "bing": "https://www.bing.com/search?q=" + urllib.parse.quote(cleaned),
            "duckduckgo": "https://duckduckgo.com/?q=" + urllib.parse.quote(cleaned),
        }.get(str(engine).lower(), "https://www.google.com/search?q=" + urllib.parse.quote(cleaned))
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
        selector_sets = ["h3 a", "a[href]", "a.result__a"]
        href = None
        for selector in selector_sets:
            locators = page.locator(selector)
            try:
                href = locators.nth(int(result_index)).get_attribute("href")
            except Exception:
                href = None
            if href:
                break
        if not href:
            raise RuntimeError("Keine Suchergebnisse gefunden.")
        target = href if href.startswith("http") else "https://" + href.lstrip("/")
        page.goto(target, wait_until="domcontentloaded", timeout=timeout)
        title = page.title()
        return {"ok": True, "url": page.url, "title": title, "text": (page.locator("body").inner_text() or "")[:3000]}

    def search_results(self, query, engine="google", timeout=20000, max_results=5):
        """Return a compact list of search titles and URLs for the next decision step."""
        cleaned = str(query or "").strip()
        if not cleaned:
            raise ValueError("Keine Suchanfrage angegeben.")
        page = self._ensure_page()
        timeout = self._bounded_timeout(timeout)

        def fetch_results(search_page):
            results = []
            anchors = search_page.locator("a[href]")
            for idx in range(min(anchors.count(), 80)):
                anchor = anchors.nth(idx)
                href = (anchor.get_attribute("href") or "").strip()
                text = (anchor.inner_text() or "").strip()
                if not href or not text or href in {"#", "javascript:void(0)"}:
                    continue
                if text.lower() in {"alle akzeptieren", "alle ablehnen", "weitere optionen", "datenschutz", "nutzungsbedingungen", "google"}:
                    continue
                if href.startswith("/url?"):
                    href = "https://www.google.com" + href
                elif href.startswith("/"):
                    href = "https://www.google.com" + href
                if href.startswith("http") and "google.com" not in href:
                    results.append({"title": text, "url": href})
                if len(results) >= int(max_results):
                    break
            return results

        search_url = {
            "google": "https://www.google.com/search?q=" + urllib.parse.quote(cleaned),
            "bing": "https://www.bing.com/search?q=" + urllib.parse.quote(cleaned),
            "duckduckgo": "https://duckduckgo.com/?q=" + urllib.parse.quote(cleaned),
        }.get(str(engine).lower(), "https://www.google.com/search?q=" + urllib.parse.quote(cleaned))
        page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
        results = fetch_results(page)
        if not results and str(engine).lower() == "google":
            fallback = "https://www.bing.com/search?q=" + urllib.parse.quote(cleaned)
            page.goto(fallback, wait_until="domcontentloaded", timeout=timeout)
            results = fetch_results(page)
        if not results:
            raise RuntimeError("Keine Suchergebnisse gefunden.")
        return {"ok": True, "query": cleaned, "results": results, "url": page.url}

    def click_text(self, text, timeout=15000):
        if not text:
            raise ValueError("Kein Text für Klick angegeben.")
        page = self._ensure_page()
        escaped = str(text).replace("\\", "\\\\").replace("'", "\\'")
        try:
            page.get_by_text(str(text), exact=False).first.click(timeout=timeout)
        except Exception:
            page.locator(f"xpath=//*[contains(normalize-space(.), '{escaped}')]").first.click(timeout=timeout)
        return {"ok": True, "message": f"Text geklickt: {text}", "url": page.url}

    def fill(self, selector, value, timeout=15000):
        page = self._ensure_page()
        page.locator(selector).fill(str(value), timeout=timeout)
        return {"ok": True, "message": f"Feld gefüllt: {selector}", "url": page.url}

    def fill_form(self, fields=None, timeout=15000):
        """Fill a form using label names or CSS selectors."""
        page = self._ensure_page()
        payload = fields or {}
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Keine Formularfelder angegeben.")
        for selector, value in payload.items():
            target = str(selector).strip()
            if not target:
                continue
            try:
                page.locator(target).fill(str(value), timeout=timeout)
            except Exception:
                try:
                    page.get_by_label(target, exact=False).fill(str(value), timeout=timeout)
                except Exception:
                    fallback = target.replace(" ", "")
                    try:
                        page.locator(f"xpath=//*[@name='{fallback}' or @id='{fallback}' or @placeholder='{target}' or contains(@aria-label, '{target}')]" ).fill(str(value), timeout=timeout)
                    except Exception as exc:
                        raise RuntimeError(f"Feld '{target}' konnte nicht gefunden werden: {exc}") from exc
        return {"ok": True, "message": "Formularfelder ausgefüllt.", "url": page.url, "fields": list(payload.keys())}

    def type(self, value, selector=None, timeout=15000):
        page = self._ensure_page()
        if selector:
            page.locator(selector).press_sequentially(str(value), delay=30, timeout=timeout)
        else:
            page.keyboard.type(str(value), delay=30)
        return {"ok": True, "message": "Text eingegeben.", "url": page.url}

    def read(self, selector="body"):
        page = self._ensure_page()
        return {"ok": True, "text": (page.locator(selector).inner_text() or "")[:4000], "url": page.url}

    def scroll(self, amount=700):
        page = self._ensure_page()
        distance = max(-5000, min(int(amount), 5000))
        page.mouse.wheel(0, distance)
        return {"ok": True, "message": f"Seite um {distance}px gescrollt.", "url": page.url}

    def wait_for_selector(self, selector, timeout=15000):
        page = self._ensure_page()
        page.wait_for_selector(selector, timeout=timeout)
        return {"ok": True, "message": f"Selektor sichtbar: {selector}", "url": page.url}

    def click_selector(self, selector, timeout=15000):
        page = self._ensure_page()
        page.locator(selector).first.click(timeout=timeout)
        return {"ok": True, "message": f"Selektor geklickt: {selector}", "url": page.url}

    def submit(self, selector="form", timeout=15000):
        page = self._ensure_page()
        page.locator(selector).first.evaluate("form => form.requestSubmit ? form.requestSubmit() : form.submit()")
        return {"ok": True, "message": "Formular abgeschickt.", "url": page.url}

    def execute_flow(self, task, timeout=20000, confirmed=False):
        """Run a small natural-language workflow: search, fill, click, submit, read."""
        text = str(task or "").strip()
        if not text:
            raise ValueError("Keine Browser-Aufgabe angegeben.")
        lower = text.lower()
        if any(marker in lower for marker in ("suche", "search", "finde", "find")):
            query = text
            for prefix in ("suche ", "search ", "finde ", "find "):
                if lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            results = self.search_results(query, timeout=timeout)
            if not results.get("ok"):
                return results
            if not results.get("results"):
                return {"ok": False, "message": "Keine Suchergebnisse für den Workflow gefunden."}
            result = self.navigate(results["results"][0]["url"], timeout=timeout)
            return {"ok": True, "message": "Suchlauf und erste Seite geöffnet.", "url": result.get("url"), "query": query, "results": results.get("results", [])[:3]}

        if any(marker in lower for marker in ("formular", "form", "login", "anmeldung", "ausfüllen", "fill", "submit", "absenden")):
            if "{" in text:
                import json
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {}
            else:
                payload = {}
            if payload:
                self.fill_form(payload, timeout=timeout)
                if "submit" in lower or "absenden" in lower:
                    if not confirmed:
                        return {
                            "ok": False,
                            "error_code": "confirmation_required",
                            "message": "Das Formular ist ausgefüllt. Das endgültige Absenden braucht deine Bestätigung.",
                            "fields": list(payload.keys()),
                        }
                    self.submit()
                return {"ok": True, "message": "Formularflow ausgeführt.", "fields": list(payload.keys())}
            return {"ok": False, "message": "Für Formulare braucht der Workflow konkrete Feldwerte oder ein JSON-Objekt."}

        if any(marker in lower for marker in ("klick", "click", "öffne", "oeffne", "open")):
            target = text
            match = re.search(r"(?:klick|click|öffne|oeffne|open)\s+(?:auf\s+)?(.+)$", text, flags=re.IGNORECASE)
            if match:
                target = match.group(1).strip()
            if target:
                if not confirmed:
                    return {
                        "ok": False,
                        "error_code": "confirmation_required",
                        "message": "Der Klick ist vorbereitet. Bestätigung erforderlich.",
                    }
                return self.click_text(target, timeout=timeout)

        if re.match(r"^https?://", text, re.IGNORECASE):
            return self.navigate(text, timeout=timeout)
        return self.navigate(text, timeout=timeout)

    def execute_steps(self, steps, timeout=20000, confirmed=False):
        """Execute explicit browser steps and stop at the first failed verification."""
        if not isinstance(steps, list) or not steps:
            raise ValueError("Keine Browser-Schritte angegeben.")
        results = []
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Browser-Schritt {index} ist ungültig.")
            action = str(step.get("action") or step.get("tool") or "").strip().lower()
            args = dict(step.get("arguments") or step.get("args") or {})
            action = {
                "open": "navigate",
                "read": "read",
                "click": "click_text",
                "fill": "fill",
                "wait": "wait_for_selector",
                "screenshot": "screenshot",
                "scroll": "scroll",
                "submit": "submit",
            }.get(action, action)
            if action in {
                "submit", "browser_submit", "click_text", "click_selector",
                "fill", "fill_form",
            } and not confirmed:
                return {
                    "ok": False,
                    "error_code": "confirmation_required",
                    "message": "Der Browser-Flow ist bis zum Absenden vorbereitet. Bestätigung erforderlich.",
                    "results": results,
                }
            handlers = {
                "navigate": self.navigate,
                "read": self.read,
                "click_text": self.click_text,
                "click_selector": self.click_selector,
                "fill": self.fill,
                "fill_form": self.fill_form,
                "wait_for_selector": self.wait_for_selector,
                "wait_for_text": self.wait_for_text,
                "screenshot": self.screenshot,
                "scroll": self.scroll,
                "submit": self.submit,
            }
            handler = handlers.get(action)
            if handler is None:
                raise ValueError(f"Nicht erlaubte Browser-Aktion: {action}")
            if action in {"navigate", "click_text", "click_selector", "fill", "fill_form", "wait_for_selector", "wait_for_text", "submit"}:
                args.setdefault("timeout", timeout)
            result = handler(**args)
            results.append({"step": index, "action": action, "result": result})
            if not isinstance(result, dict) or not result.get("ok"):
                return {
                    "ok": False,
                    "message": f"Browser-Schritt {index} fehlgeschlagen.",
                    "results": results,
                }
        return {"ok": True, "message": "Browser-Flow vollständig ausgeführt und verifiziert.", "results": results}

    def wait_for_text(self, text, timeout=15000):
        page = self._ensure_page()
        page.get_by_text(str(text), exact=False).first.wait_for(timeout=timeout)
        return {"ok": True, "message": f"Text sichtbar: {text}", "url": page.url}

    def screenshot(self, path=None):
        page = self._ensure_page()
        target = str(path or (Path.cwd() / "browser_capture.png"))
        resolved = Path(target).expanduser()
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        resolved.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(resolved), full_page=False)
        return {"ok": True, "path": str(resolved), "message": "Screenshot gespeichert."}

    def close(self):
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


class AgentTools:
    """Safe, user-visible actions that require no credentials or hidden automation."""

    def __init__(self):
        self.pending = None
        self._tradingview = None
        self.desktop = DesktopControls()
        self.browser = BrowserSession()
        self.orchestrator = DesktopWorkflowOrchestrator(self.desktop, self.browser)
        self.multi_agent = MultiAgentOrchestrator(self.execute_structured)

    @property
    def tradingview(self):
        # TradingView automation is only needed after an explicit paper-trade
        # confirmation; avoid importing/initialising it for normal requests.
        if self._tradingview is None:
            self._tradingview = TradingViewAutomation()
        return self._tradingview

    @staticmethod
    def _normalize_command(value):
        text = re.sub(r"\s+", " ", str(value or "").strip().lower())
        replacements = (
            (r"\?ffne\b", "öffne"),
            (r"\?ffnen\b", "öffnen"),
            (r"\?rufe\b", "prüfe"),
            (r"\boeffne\b", "öffne"),
            (r"\bmaerkte\b", "märkte"),
            (r"\bpruefe\b", "prüfe"),
            (r"\bpruefen\b", "prüfen"),
            (r"\btradingwiew\b|\btradinview\b|\btraddingview\b", "tradingview"),
            (r"\btrading view\b", "tradingview"),
            (r"\bmarkt ?übersicht\b|\bmarkt ?uebersicht\b", "märkte"),
            (r"\bbitte mal\b|\bmal bitte\b", "bitte"),
            (r"\bmach(?:e)?\s+(.+?)\s+auf\b", r"öffne \1"),
            (r"\bgeh(?:e)?\s+(?:zu|auf)\s+(.+?)(?=\s*(?:,|\bdann\b|$))", r"öffne \1"),
            (r"\bzeig(?:e)?\s+mir\s+(.+)", r"öffne \1"),
            (r"\bhol(?:e)?\s+(.+?)\s+her\b", r"öffne \1"),
            (r"\bcd\b(?=.*(?:usd|dollar|chart|tradingview))", "dxy"),
            (r"\bbtc\s*[-/]?\s*usdt\b", "btc/usdt"),
            (r"\bxau\s*[-/]?\s*usd\b", "xauusd"),
        )
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def plan_goal(request):
        text = str(request or "").strip()
        if not text:
            return {"steps": [], "summary": "Keine Aufgabe angegeben."}

        normalized = AgentTools._normalize_command(text)
        lower = normalized
        steps = []
        market_urls = (
            ("xauusd", "OANDA:XAUUSD"),
            ("gold", "OANDA:XAUUSD"),
            ("dxy", "TVC:DXY"),
            ("usdx", "TVC:DXY"),
            ("usd chart", "TVC:DXY"),
        )
        for alias, symbol in market_urls:
            if alias in lower and any(marker in lower for marker in ("chart", "diagramm", "markt", "öffne", "oeffne", "open", "zeige")):
                return {
                    "summary": f"TradingView öffnen und {symbol} anzeigen.",
                    "steps": [
                        {"tool": "open_application", "reason": "Browser fokussieren", "arguments": {"name": "browser"}},
                        {"tool": "open_url", "reason": "Marktchart öffnen", "arguments": {"url": f"https://www.tradingview.com/chart/?symbol={symbol}"}},
                        {"tool": "active_context", "reason": "Sichtbaren Chart verifizieren", "arguments": {}},
                    ],
                }
        if any(marker in lower for marker in ("aktiven bildschirm", "aktives fenster", "bildschirm prüfen", "bildschirm pruefen", "active screen")):
            return {
                "summary": "Aktiven Bildschirm und Fensterkontext prüfen.",
                "steps": [
                    {"tool": "active_context", "reason": "Aktiven UI-Kontext auslesen", "arguments": {}},
                    {"tool": "detect_active_window_title", "reason": "Aktives Fenster verifizieren", "arguments": {}},
                ],
            }
        if "tradingview" in lower and any(
            marker in lower for marker in ("chat", "nachrichten", "stimmung", "btc/usdt", "btcusdt")
        ):
            symbol = "BINANCE:BTCUSDT" if re.search(
                r"\bbtc\s*/?\s*usdt\b|\bbtcusdt\b", lower
            ) else ""
            if symbol:
                steps = [
                    {
                        "tool": "open_application",
                        "reason": "TradingView sichtbar öffnen oder fokussieren",
                        "arguments": {"name": "browser"},
                    },
                    {
                        "tool": "open_url",
                        "reason": "Den angeforderten TradingView-Chart öffnen",
                        "arguments": {
                            "url": f"https://www.tradingview.com/chart/?symbol={symbol}",
                        },
                    },
                    {
                        "tool": "active_context",
                        "reason": "Sichtbaren Browser- und UI-Zustand verifizieren",
                        "arguments": {},
                    },
                    {
                        "tool": "browser_get_text",
                        "reason": "Nur tatsächlich zugängliche Chat-/Community-Texte lesen",
                        "arguments": {
                            "url": f"https://www.tradingview.com/chart/?symbol={symbol}",
                        },
                    },
                ]
                return {
                    "summary": "TradingView öffnen, BTC/USDT verifizieren und zugängliche Chatdaten prüfen.",
                    "steps": steps,
                }
        if "tradingview" in lower and re.search(r"\bbtc\s*/?\s*usdt\b|\bbtcusdt\b", lower):
            return {
                "summary": "TradingView öffnen und den BTC/USDT-Chart anzeigen.",
                "steps": [
                    {"tool": "open_application", "reason": "TradingView sichtbar öffnen oder fokussieren", "arguments": {"name": "browser"}},
                    {"tool": "open_url", "reason": "Den BTC/USDT-Chart öffnen", "arguments": {"url": "https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT"}},
                    {"tool": "active_context", "reason": "Sichtbaren Browserzustand verifizieren", "arguments": {}},
                ],
            }
        if re.search(r"\b(?:öffne|open|starte|start|mach(?:e)?|browser|website|webseite|youtube|google|chrome|edge)\b", lower):
            target = normalized
            match = re.search(
                r"(?:^|\s)(?:öffne|open|starte|start|mach(?:e)?)\s+(.+?)(?:\s+auf)?$",
                normalized,
                flags=re.IGNORECASE,
            )
            if match:
                target = match.group(1).strip()
            target = re.sub(r"^(?:den|die|das|dem|der)\s+", "", target, flags=re.IGNORECASE)
            explicit_web = (
                re.match(r"^https?://", target, re.IGNORECASE)
                or re.search(r"\b(?:browser|website|webseite|youtube|google|chrome|edge)\b", lower)
            )
            if explicit_web:
                steps = [
                    {"tool": "open_application", "reason": "Browser fokussieren", "arguments": {"name": "browser"}},
                    {"tool": "open_url", "reason": "Zielseite öffnen", "arguments": {"url": target if re.match(r"^https?://", target, re.IGNORECASE) else target}},
                ]
            else:
                steps = [
                    {"tool": "open_application", "reason": "Angeforderte Anwendung öffnen", "arguments": {"name": target}},
                ]
        elif re.search(r"\b(?:suche|search|finde|find|lookup|look up)\b", lower):
            query = normalized
            for prefix in ("suche ", "search ", "finde ", "find ", "lookup ", "look up "):
                if lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            steps = [
                {"tool": "browser_search_and_open", "reason": "Suchanfrage ausführen und Top-Ergebnis öffnen", "arguments": {"query": query or text}},
            ]
        elif re.search(r"\b(?:tippe|type|schreibe|write|eingabe|enter)\b", lower):
            steps = [
                {"tool": "type_text", "reason": "Text in aktives Fenster eingeben", "arguments": {"text": text}},
            ]
        elif re.search(r"\b(?:klick|klicke|click|scroll|bildlauf|fenster|window)\b", lower):
            if re.search(r"\b(?:klick|klicke|click)\b", lower):
                match = re.search(
                    r"(?:klick|klicke|click)\s+(?:auf\s+)?(.+)$",
                    normalized,
                    flags=re.IGNORECASE,
                )
                target = match.group(1).strip() if match else normalized
                steps = [
                    {
                        "tool": "browser_click_text",
                        "reason": "Sichtbares Browser-Element gezielt anklicken",
                        "arguments": {"text": target},
                    },
                ]
            else:
                steps = [
                    {"tool": "list_windows", "reason": "Verfügbare Fenster prüfen", "arguments": {}},
                ]
        elif re.search(r"\b(?:status|info|was kannst du|welche tools|tools)\b", lower):
            steps = [
                {"tool": "detect_active_window_title", "reason": "Aktuellen Fensterstatus prüfen", "arguments": {}},
            ]
        else:
            steps = []

        return {
            "summary": f"Aufgabe geplant: {text[:80]}{'…' if len(text) > 80 else ''}",
            "steps": steps,
        }

    @staticmethod
    def _split_goal_steps(request):
        """Split only explicit action boundaries; keep normal phrases intact."""
        text = AgentTools._normalize_command(request)
        if "tradingview" in text and re.search(r"\bbtc\s*/?\s*usdt\b|\bbtcusdt\b", text):
            return [text]
        parts = re.split(
            r"\s*(?:;\s*|\b(?:und\s+)?dann\s+|\b(?:und\s+)?danach\s+|"
            r"\banschließend\s+|\bund\s+(?=(?:öffne|oeffne|starte|suche|klicke|"
            r"schreibe|tippe|prüfe|pruefe|warte|mache|führe|fuehre|zeige)\b))",
            text,
            flags=re.IGNORECASE,
        )
        return [part.strip(" ,.") for part in parts if part.strip(" ,.")]

    def execute_goal(self, request, confirmed=False):
        requests = self._split_goal_steps(request)
        if not requests:
            return {"ok": False, "message": "Keine ausführbare Aufgabe erkannt.", "results": []}
        results = []
        for request_index, request_part in enumerate(requests, start=1):
            plan = self.plan_goal(request_part)
            if not plan.get("steps"):
                return {
                    "ok": False,
                    "summary": f"Teil {request_index} konnte nicht verstanden werden: {request_part}",
                    "results": results,
                    "message": "Teilauftrag konnte nicht verstanden werden.",
                }
            for step in plan["steps"]:
                tool_name = step.get("tool")
                arguments = dict(step.get("arguments", {}))
                if tool_name == "search_web":
                    result = self.desktop.search_web(arguments.get("query"))
                else:
                    result = self.execute_structured(tool_name, confirmed=confirmed, **arguments)
                results.append({
                    "part": request_index,
                    "request": request_part,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                })
                if not result.get("ok"):
                    return {
                        "ok": False,
                        "summary": f"Teil {request_index} fehlgeschlagen: {request_part}",
                        "results": results,
                        "message": result.get("message", "Schritt fehlgeschlagen."),
                    }
        return {
            "ok": True,
            "summary": f"{len(requests)} Teilauftrag/Teilaufträge verstanden und ausgeführt.",
            "results": results,
            "message": "Jeder Teilauftrag wurde einzeln geplant, ausgeführt und geprüft.",
        }

    def inspect_goal(self, request):
        """Build a read-only execution plan without touching the desktop."""
        requests = self._split_goal_steps(request)
        if not requests:
            return {
                "ok": False,
                "message": "Keine klaren Teilaufträge erkannt.",
                "parts": [],
            }
        parts = []
        for index, request_part in enumerate(requests, start=1):
            plan = self.plan_goal(request_part)
            parts.append({
                "part": index,
                "request": request_part,
                "roles": self.multi_agent.role_for_request(request_part),
                "steps": plan.get("steps", []),
                "understood": bool(plan.get("steps")),
            })
        return {
            "ok": all(part["understood"] for part in parts),
            "parts": parts,
            "verification": "Jeder Schritt wird nach der Ausführung einzeln geprüft; bei Fehlern wird gestoppt.",
            "confirmation_policy": "Irreversible Aktionen benötigen eine unmittelbare Bestätigung.",
        }

    def execute_browser_sequence(self, steps, confirmed=False):
        """Run a browser automation sequence with verification after every step."""
        results = []
        for step in steps:
            name = step.get("tool")
            args = dict(step.get("arguments", {}))
            if not name:
                continue
            result = self.execute_structured(name, confirmed=confirmed, **args)
            results.append({"tool": name, "result": result})
            if not result.get("ok"):
                return {"ok": False, "results": results, "message": result.get("message", "Browser-Schritt fehlgeschlagen.")}
        return {"ok": True, "results": results, "message": "Browser-Sequenz erfolgreich ausgeführt."}

    def local_capability_status(self):
        """Return a compact summary of the local free automation stack the agent can use."""
        report = SkillManager.capability_report()
        return {
            "ok": True,
            "report": report,
            "message": (
                "Ich kann Fragen beantworten, Informationen zusammenfassen, "
                "Dateien und Apps öffnen, erlaubte Browser-/Desktop-Aktionen "
                "ausführen, Code prüfen und Aufgaben im Second Brain speichern."
            ),
        }

    def plan_browser_sequence(self, request):
        """Turn a natural browser request into a verifiable step sequence."""
        text = str(request or "").strip()
        if not text:
            return {"steps": [], "summary": "Keine Browser-Aufgabe angegeben."}
        lower = text.lower()
        if re.search(r"\b(?:suche|search|finde|find)\b", lower):
            query = text
            for prefix in ("suche ", "search ", "finde ", "find "):
                if lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            return {
                "summary": f"Browser-Suche: {query}",
                "steps": [{"tool": "browser_search_and_open", "arguments": {"query": query or text}}],
            }
        if re.search(r"\b(?:öffne|open)\b", lower):
            match = re.search(r"(?:öffne|open)\s+(.+)$", text, flags=re.IGNORECASE)
            target = match.group(1).strip() if match else text
            return {
                "summary": f"Browser öffnen: {target}",
                "steps": [{"tool": "browser_navigate", "arguments": {"url": target}}],
            }
        if re.search(r"\b(?:klicke|click)\b", lower):
            match = re.search(r"(?:klicke|click)\s+(?:auf\s+)?(.+)$", text, flags=re.IGNORECASE)
            target = match.group(1).strip() if match else text
            return {
                "summary": f"Browser-Klick: {target}",
                "steps": [{"tool": "browser_click_text", "arguments": {"text": target}}],
            }
        return {
            "summary": f"Browser-Task: {text}",
            "steps": [{"tool": "browser_navigate", "arguments": {"url": text}}],
        }

    def execute_task_sequence(self, request, confirmed=False):
        plan = self.plan_browser_sequence(request)
        return self.execute_browser_sequence(plan.get("steps", []), confirmed=confirmed)

    def run_task_queue(self, tasks, confirmed=False):
        """Execute a multi-step queue where each step is a structured tool call."""
        if not isinstance(tasks, list) or not tasks:
            return {"ok": False, "message": "Keine Aufgaben in der Queue."}
        results = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            name = task.get("tool")
            arguments = dict(task.get("arguments", {}))
            if not name:
                continue
            result = self.execute_structured(name, confirmed=confirmed, **arguments)
            results.append({"tool": name, "result": result})
            if not result.get("ok"):
                return {"ok": False, "results": results, "message": result.get("message", "Task-Queue-Schritt fehlgeschlagen.")}
        return {"ok": True, "results": results, "message": "Task-Queue erfolgreich ausgeführt."}

    def plan_task_queue(self, request):
        text = str(request or "").strip()
        if not text:
            return {"summary": "Keine Aufgabe angegeben.", "steps": []}
        lower = text.lower()
        tasks = []
        if any(marker in lower for marker in ("suche", "search", "finde", "find")):
            query = text
            for prefix in ("suche ", "search ", "finde ", "find "):
                if lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            if any(marker in lower for marker in ("und klick", "and click", "und klicke", "und öffne", "and open", "und oeffne")):
                tasks.append({"tool": "browser_execute_flow", "arguments": {"task": text}})
            else:
                tasks.append({"tool": "browser_search_and_open", "arguments": {"query": query or text}})
        elif any(marker in lower for marker in ("formular", "form", "login", "anmeldung", "absenden", "submit", "ausfüllen", "ausfuellen", "fill")):
            tasks.append({"tool": "browser_execute_flow", "arguments": {"task": text}})
        elif any(marker in lower for marker in ("klick", "click", "öffne", "oeffne", "open")):
            target = text
            match = re.search(r"(?:klick|click|öffne|oeffne|open)\s+(?:auf\s+)?(.+)$", text, flags=re.IGNORECASE)
            if match:
                target = match.group(1).strip()
            tasks.append({"tool": "browser_execute_flow", "arguments": {"task": text}})
        elif re.match(r"^https?://", text, re.IGNORECASE):
            tasks.append({"tool": "browser_navigate", "arguments": {"url": text}})
        else:
            tasks.append({"tool": "browser_execute_flow", "arguments": {"task": text}})
        return {"summary": f"Task-Queue geplant: {text}", "steps": tasks}

    def execute_task_queue(self, request, confirmed=False):
        plan = self.plan_task_queue(request)
        return self.run_task_queue(plan.get("steps", []), confirmed=confirmed)

    def plan_local_workflow(self, request):
        text = str(request or "").strip()
        if not text:
            return {"summary": "Keine lokale Workflow-Aufgabe angegeben.", "steps": []}
        lower = text.lower()
        steps = []

        app_name = None
        for candidate in ("notepad", "editor", "calculator", "rechner", "explorer", "vscode", "outlook", "teams", "browser", "edge", "chrome"):
            if candidate in lower:
                app_name = candidate
                break

        if app_name:
            steps.append({"tool": "open_application", "arguments": {"name": app_name}})
            if app_name in ("notepad", "editor"):
                steps.append({"tool": "ui_run_app_flow", "arguments": {"app_name": app_name, "steps": [{"action": "fill", "target": "Textfeld", "value": "JARVIS Desktop-Workflow aktiv"}]}})
            elif app_name in ("calculator", "rechner"):
                steps.append({"tool": "ui_run_app_flow", "arguments": {"app_name": app_name, "steps": [{"action": "click", "target": "Rechner"}]}})

        if any(marker in lower for marker in ("browser", "web", "seite", "netz", "google", "bing", "youtube")):
            steps.append({"tool": "open_application", "arguments": {"name": "browser"}})
        if any(marker in lower for marker in ("suche", "search", "finde", "find")):
            query = text
            for prefix in ("suche ", "search ", "finde ", "find "):
                if lower.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            steps.append({"tool": "browser_search_and_open", "arguments": {"query": query or text}})
        elif any(marker in lower for marker in ("öffne", "oeffne", "open", "starte", "start")):
            target = text
            match = re.search(r"(?:öffne|oeffne|open|starte|start)\s+(.+)$", text, flags=re.IGNORECASE)
            if match:
                target = match.group(1).strip()
            target = re.split(r"\s*(?:,|\band\b|\s+und\s+|\s*\|\s*)\s*", target, maxsplit=1)[0].strip(" .:;")
            if re.match(r"^https?://", target, re.IGNORECASE):
                steps.append({"tool": "browser_navigate", "arguments": {"url": target}})
            else:
                steps.append({"tool": "open_application", "arguments": {"name": target}})

        if any(marker in lower for marker in ("status", "system", "monitor", "zustand")):
            steps.append({"tool": "system_status", "arguments": {}})
        if any(marker in lower for marker in ("screenshot", "bildschirm", "capture", "screen")):
            steps.append({"tool": "capture_screen", "arguments": {}})
        if any(marker in lower for marker in ("clipboard", "zwischenablage", "kopieren", "copy")):
            steps.append({"tool": "read_clipboard", "arguments": {}})
        if any(marker in lower for marker in ("orchestr", "workflow", "ui flow", "desktop app", "windows app")):
            steps.insert(0, {"tool": "detect_active_window_title", "arguments": {}})

        if not steps:
            return {
                "summary": "Keine eindeutige lokale Aktion erkannt. Keine App und kein Browser wurden geöffnet.",
                "steps": [],
            }

        return {"summary": f"Lokaler Workflow geplant: {text[:80]}{'…' if len(text) > 80 else ''}", "steps": steps}

    def execute_local_workflow(self, request, confirmed=False):
        plan = self.plan_local_workflow(request)
        return self.multi_agent.execute(
            plan.get("steps", []),
            request=request,
            confirmed=confirmed,
            context={"summary": plan.get("summary", ""), "workflow": "local"},
        )

    def execute_multi_agent(self, steps, request="", confirmed=False, context=None):
        """Run explicit role-based steps with shared context and verification."""
        return self.multi_agent.execute(
            steps, request=request, confirmed=confirmed, context=context
        )

    def execute_browser_flow(self, request, confirmed=False):
        """Handle direct browser workflows such as search, fill, click, submit, and verify."""
        text = str(request or "").strip()
        if not text:
            return {"ok": False, "message": "Keine Browser-Aufgabe angegeben."}
        result = self.browser.execute_flow(text)
        if result.get("ok"):
            return {"ok": True, "message": "Browser-Workflow ausgeführt.", "result": result}
        return {"ok": False, "message": result.get("message", "Browser-Workflow fehlgeschlagen."), "result": result}

    @staticmethod
    def plan_action(tool_name, **arguments):
        """Create an auditable action plan before touching the desktop."""
        destructive = {
            "delete_file", "delete_folder", "delete_path", "move_path",
            "shutdown", "restart",
            "format_drive", "send_email", "place_order",
        }
        safe_but_powerful = {
            "open_application", "open_url", "search_web", "type_text", "click",
            "hotkey", "press_key", "browser_click", "browser_click_text",
            "browser_fill",
        }
        confirmation_tools = {
            "type_text", "click", "hotkey", "press_key",
            "browser_click", "browser_click_text", "browser_fill",
            "browser_submit",
        }
        return {
            "tool": tool_name,
            "arguments": dict(arguments),
            "confirmation_required": (
                tool_name in destructive or tool_name in confirmation_tools
            ),
            "risk": (
                "destructive" if tool_name in destructive
                else ("high" if tool_name in safe_but_powerful else "safe")
            ),
        }

    @staticmethod
    def _verified(result):
        if not isinstance(result, dict):
            return {
                "tool": "unknown", "ok": False, "verified": False,
                "error_code": "invalid_result", "message": str(result), "data": {},
            }
        # Tool adapters may return Path/enum/third-party values.  Normalize at
        # the boundary so orchestrator/API callers always get JSON-safe data.
        result = MultiAgentOrchestrator._serializable(result)
        result.setdefault("data", {})
        result["verified"] = bool(result.get("ok"))
        if not result.get("ok"):
            result.setdefault("error_code", "action_failed")
        return result

    def execute_planned(self, plan, confirmed=False):
        if not isinstance(plan, dict) or not plan.get("tool"):
            return self._verified({
                "tool": "unknown", "ok": False, "message": "Ungültiger Aktionsplan.",
            })
        if plan.get("confirmation_required") and not confirmed:
            return self._verified({
                "tool": plan["tool"], "ok": False, "error_code": "confirmation_required",
                "message": "Diese irreversible Aktion benötigt eine ausdrückliche Bestätigung.",
                "data": {"plan": plan},
            })
        return self.execute_structured(
            plan["tool"], confirmed=confirmed, **plan.get("arguments", {})
        )

    def execute_structured(self, tool_name, **arguments):
        """Run one named tool and return a stable, serialisable result."""
        confirmed = bool(arguments.pop("confirmed", False))
        plan = self.plan_action(tool_name, **arguments)
        if plan["confirmation_required"] and not confirmed:
            return self._verified({
                "tool": tool_name, "ok": False, "error_code": "confirmation_required",
                "message": "Diese irreversible Aktion benötigt eine ausdrückliche Bestätigung.",
                "data": {"plan": plan},
            })
        handlers = {
            "open_application": self.desktop.open_application,
            "open_default_browser": self.desktop.open_default_browser,
            "detect_active_window_title": self.desktop.detect_active_window_title,
            "active_context": self.desktop.active_context,
            "wait": self.desktop.wait,
            "open_url": self.desktop.open_url,
            "search_web": self.desktop.search_web,
            "browser_open": self.desktop.browser_open,
            "browser_click": self.desktop.browser_click,
            "browser_fill": self.desktop.browser_fill,
            "browser_get_text": self.desktop.browser_get_text,
            "browser_snapshot": self.desktop.browser_snapshot,
            "youtube_video_analysis": self.desktop.youtube_video_analysis,
            "browser_search_and_open": self.desktop.browser_search_and_open,
            "browser_navigate": self.browser.navigate,
            "browser_search": self.browser.search,
            "browser_search_results": self.browser.search_results,
            "browser_click_text": self.browser.click_text,
            "browser_fill_field": self.browser.fill,
            "browser_fill_form": self.browser.fill_form,
            "browser_order": self.browser.execute_flow,
            "browser_execute_flow": self.browser.execute_flow,
            "browser_type": self.browser.type,
            "browser_read": self.browser.read,
            "browser_wait_for_selector": self.browser.wait_for_selector,
            "browser_scroll": self.browser.scroll,
            "browser_click_selector": self.browser.click_selector,
            "browser_wait_for_text": self.browser.wait_for_text,
            "browser_submit": self.browser.submit,
            "browser_screenshot": self.browser.screenshot,
            "browser_execute_flow": self.browser.execute_flow,
            "browser_execute_steps": self.browser.execute_steps,
            "browser_close": self.browser.close,
            "browser_history": self.browser.history_summary,
            "local_capability_status": self.local_capability_status,
            "system_status": self.desktop.system_status,
            "ocr_image": self.desktop.ocr_image,
            "run_task_queue": self.run_task_queue,
            "execute_task_queue": self.execute_task_queue,
            "execute_local_workflow": self.execute_local_workflow,
            "execute_multi_agent": self.execute_multi_agent,
            "multi_agent_orchestrate": self.execute_multi_agent,
            "execute_browser_flow": self.execute_browser_flow,
            "capture_screen": self.desktop.capture_screen,
            "focus_window": self.desktop.focus_window,
            "list_windows": self.desktop.list_windows,
            "ui_click_visible_text": self.desktop.ui_click_visible_text,
            "ui_inspect": self.desktop.ui_inspect,
            "ui_fill_visible_field": self.desktop.ui_fill_visible_field,
            "ui_run_app_flow": self.desktop.ui_run_app_flow,
            "desktop_orchestrate": self.orchestrator.execute,
            "mouse_move": self.desktop.mouse_move,
            "mouse_scroll": self.desktop.mouse_scroll,
            "read_clipboard": self.desktop.read_clipboard,
            "write_clipboard": self.desktop.write_clipboard,
            "open_file": self.desktop.open_file,
            "open_folder": self.desktop.open_folder,
            "list_files": self.desktop.list_files,
            "create_folder": self.desktop.create_folder,
            "move_path": self.desktop.move_path,
            "delete_path": self.desktop.delete_path,
            "delete_file": lambda path: self.desktop.delete_path(path, recursive=False),
            "delete_folder": lambda path: self.desktop.delete_path(path, recursive=True),
            "type_text": self.desktop.type_text,
            "press_key": self.desktop.press_key,
            "hotkey": self.desktop.hotkey,
            "click": self.desktop.click,
            "position_window": self.desktop.position_window,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return self._verified({
                "tool": tool_name, "ok": False, "error_code": "unknown_tool",
                "message": "Unbekanntes Werkzeug. Freie Shell-Befehle sind nicht erlaubt.",
                "data": {},
            })
        if tool_name == "browser_execute_flow":
            return self._verified(self.browser.execute_flow(
                arguments.get("task"),
                timeout=arguments.get("timeout", 20000),
                confirmed=confirmed,
            ))
        if tool_name == "browser_execute_steps":
            return self._verified(self.browser.execute_steps(
                arguments.get("steps"),
                timeout=arguments.get("timeout", 20000),
                confirmed=confirmed,
            ))
        try:
            return self._verified(handler(**arguments))
        except TypeError as exc:
            return self._verified({
                "tool": tool_name, "ok": False, "error_code": "invalid_arguments",
                "message": f"Ungültige Werkzeugparameter: {exc}", "data": {},
            })

    @staticmethod
    def format_result(result):
        if not isinstance(result, dict):
            return str(result)
        if result.get("ok"):
            return result.get("message", "Werkzeug beendet.")
        code = result.get("error_code", "action_failed")
        return f"Aktion fehlgeschlagen [{code}]: {result.get('message', 'Unbekannter Fehler.')}"

    def prepare_email(self, request):
        incomplete = re.search(
            r"(?:an|für|fuer)\s+([A-Z0-9._%+-]+@[A-Z0-9.-]+)(?:\s|$)",
            request,
            flags=re.IGNORECASE,
        )
        match = re.search(
            r"(?:an|für|fuer|an\s+eine antwort an|reply\s+to|antwort\s+an)\s+"
            r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
            request,
            flags=re.IGNORECASE,
        )
        if not match:
            if incomplete:
                return (
                    f"Die Adresse „{incomplete.group(1)}“ ist unvollständig. "
                    "Bitte nenne die vollständige Adresse, zum Beispiel name@gmail.com."
                )
            return None

        recipient = match.group(1)
        subject_match = re.search(
            r"(?:betreff|betreffzeile)\s*:?\s*(.+?)(?:\s+text\s*:|\s+nachricht\s*:|$)",
            request,
            re.IGNORECASE,
        )
        body_match = re.search(
            r"(?:text|nachricht)\s*:?\s*(.+)$", request, re.IGNORECASE
        )
        subject = subject_match.group(1).strip() if subject_match else ""
        if re.search(r"\b(?:antwort|reply)\b", request, re.IGNORECASE) and subject:
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
        body = body_match.group(1).strip() if body_match else ""
        if not body and not subject_match:
            after_recipient = request[match.end():].strip()
            if after_recipient.startswith(":"):
                body = after_recipient[1:].strip()
        self.pending = {
            "type": "email",
            "mode": "reply" if re.search(r"\b(?:antwort|reply)\b", request, re.IGNORECASE) else "compose",
            "recipient": recipient,
            "subject": subject,
            "body": body,
        }
        details = f"Empfänger: {recipient}"
        if subject:
            details += f"\nBetreff: {subject}"
        if body:
            details += f"\nText: {body}"
        return (
            "Ich habe einen E-Mail-Entwurf vorbereitet:\n"
            f"{details}\n\n"
            "Soll ich ihn in deinem Mailprogramm öffnen? Ich sende nichts automatisch."
        )

    def continue_email(self, request):
        """Add subject/body details before the user confirms opening the draft."""
        if not self.pending or self.pending.get("type") != "email":
            return None
        subject_match = re.search(
            r"(?:betreff|betreffzeile)\s*:?\s*(.+?)(?:\s+text\s*:|\s+nachricht\s*:|$)",
            request, re.IGNORECASE,
        )
        body_match = re.search(r"(?:text|nachricht)\s*:?\s*(.+)$", request, re.IGNORECASE)
        if subject_match:
            self.pending["subject"] = subject_match.group(1).strip()
        if body_match:
            self.pending["body"] = body_match.group(1).strip()
        if not subject_match and not body_match:
            return None
        details = [f"Empfänger: {self.pending['recipient']}"]
        if self.pending.get("subject"):
            details.append(f"Betreff: {self.pending['subject']}")
        if self.pending.get("body"):
            details.append(f"Text: {self.pending['body']}")
        return (
            "E-Mail-Entwurf aktualisiert:\n"
            + "\n".join(details)
            + "\n\nSoll ich ihn in deinem Mailprogramm öffnen? "
            "Ich sende nichts automatisch."
        )

    def prepare_paper_trade(self, symbol, direction):
        self.pending = {
            "type": "paper_trade",
            "symbol": symbol,
            "direction": direction,
            "quantity": None,
            "order_type": None,
            "stop_loss": None,
            "awaiting_confirmation": False,
        }
        return (
            f"TradingView ist mit {symbol} geöffnet. "
            f"Ich bereite einen Paper-{direction} vor. "
            "Welche Menge und welcher Ordertyp (Market oder Limit) sollen verwendet werden?"
        )

    def continue_paper_trade(self, request):
        if not self.pending or self.pending.get("type") != "paper_trade":
            return None
        lowered = request.lower()
        quantity_match = re.search(
            r"(?:menge|quantität|quantity|größe|groesse)\s*:?\s*(\d+(?:[.,]\d+)?)",
            lowered,
        )
        if not quantity_match:
            quantity_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:einheiten?|units?)\b", lowered)
        if not quantity_match:
            quantity_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*lots?\b", lowered)
        if not quantity_match:
            quantity_match = re.search(
                r"(?:mit|menge|größe|groesse)\s*:?\s*(\d+(?:[.,]\d+)?)\b",
                lowered,
            )
        if not quantity_match:
            quantity_match = re.search(
                r"(?<![a-z])(\d+(?:[.,]\d+)?)(?![a-z])",
                lowered,
            )
        stop_loss_match = re.search(
            r"\b(?:sl|stop[\s-]?loss)\s*:?\s*(\d+(?:[.,]\d+)?)",
            lowered,
        )
        order_type = None
        if re.search(r"\bmarket\b|\bmarkt\b|\bjetzt\b|\bsofort\b|\bdirekt\b", lowered):
            order_type = "Market"
        elif re.search(r"\blimit\b", lowered):
            order_type = "Limit"
        if quantity_match:
            self.pending["quantity"] = quantity_match.group(1).replace(",", ".")
        if order_type:
            self.pending["order_type"] = order_type
        if stop_loss_match:
            self.pending["stop_loss"] = stop_loss_match.group(1).replace(",", ".")
        has_order_details = (
            quantity_match is not None
            or stop_loss_match is not None
            or order_type is not None
        )
        if self.pending["quantity"] and self.pending["order_type"]:
            self.pending["awaiting_confirmation"] = True
            stop_loss = (
                f" mit Stop-Loss {self.pending['stop_loss']}"
                if self.pending["stop_loss"] else ""
            )
            return (
                f"Ordervorschau: {self.pending['direction']} {self.pending['quantity']} "
                f"{self.pending['symbol']} als {self.pending['order_type']}-Order{stop_loss}. "
                "Soll ich diese Paper-Order jetzt in TradingView ausführen? "
                "Antworte mit „Bestätigen“ oder „Abbrechen“."
            )
        if has_order_details:
            details = []
            if self.pending["quantity"]:
                details.append(f"Menge {self.pending['quantity']}")
            if self.pending["stop_loss"]:
                details.append(f"Stop-Loss {self.pending['stop_loss']}")
            missing = []
            if not self.pending["quantity"]:
                missing.append("die Menge in Lots")
            if not self.pending["order_type"]:
                missing.append("den Ordertyp Market oder Limit")
            if len(missing) == 1:
                missing_text = missing[0]
            else:
                missing_text = " sowie ".join(missing)
            saved = f" ({' und '.join(details)} gespeichert)" if details else ""
            return (
                f"Verstanden{saved} für {self.pending['symbol']} "
                f"({self.pending['direction']}). Bitte nenne noch {missing_text}."
            )
        if not has_order_details and "paper" not in lowered and not any(
            word in lowered for word in ("doch", "ja", "bestätige", "bestatige")
        ):
            return None
        return (
            f"Ja, verstanden: Das ist ein Paper-Trade für {self.pending['symbol']} "
            f"({self.pending['direction']}). Nenne bitte noch die Menge und "
            "Market oder Limit. Ich klicke erst nach deiner vollständigen Bestätigung."
        )

    def confirm_pending(self):
        if not self.pending:
            return None
        action = self.pending
        self.pending = None
        if action["type"] == "email":
            query = urllib.parse.urlencode({
                "to": action["recipient"],
                "subject": action["subject"],
                "body": action["body"],
            })
            mailto = f"mailto:{action['recipient']}?{query}"
            # A mailto link is intentionally handed to the visible default mail
            # client; it is never submitted by JARVIS.
            try:
                if not webbrowser.open(mailto):
                    raise OSError("Mailprogramm konnte nicht geöffnet werden")
            except Exception as exc:
                self.pending = action
                return f"Mailentwurf konnte nicht geöffnet werden: {exc}"
            verb = "Antwortentwurf" if action.get("mode") == "reply" else "E-Mail-Entwurf"
            return f"Der bestätigte {verb} wurde geöffnet. Das Absenden musst du selbst bestätigen."
        if action["type"] == "paper_trade":
            try:
                return self.tradingview.execute_paper_order(action)
            except RuntimeError as exc:
                self.pending = action
                return f"Paper-Order nicht ausgeführt: {exc}"
        return "Keine ausführbare bestätigte Aktion vorhanden."

    def cancel_pending(self):
        self.pending = None
        return "Verstanden. Die geplante Aktion wurde abgebrochen."
