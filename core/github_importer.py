"""Safe GitHub repository analysis and explicitly confirmed file import."""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse


class GitHubImportError(ValueError):
    pass


class GitHubImporter:
    MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
    MAX_FILE_BYTES = 500_000
    MAX_FILES = 200
    ALLOWED_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".md"}
    BLOCKED_NAMES = {".env", ".env.local", ".env.production", "id_rsa"}
    BLOCKED_PARTS = ("secret", "credential", "token", ".pem", ".key")

    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    @staticmethod
    def parse_url(value):
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise GitHubImportError("Nur https://github.com/{owner}/{repository} ist erlaubt.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or any(part in {".", ".."} for part in parts[:2]):
            raise GitHubImportError("Der GitHub-Link enthält kein gültiges Repository.")
        owner, repo = parts[:2]
        repo = re.sub(r"\.git$", "", repo)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner + repo):
            raise GitHubImportError("Ungültige Zeichen im Repository-Link.")
        return owner, repo

    def _request_json(self, url):
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Jarvis-local-importer"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def analyze(self, url):
        owner, repo = self.parse_url(url)
        metadata = self._request_json(f"https://api.github.com/repos/{owner}/{repo}")
        if metadata.get("archived"):
            risk = "high"
        else:
            risk = "medium"
        license_name = (metadata.get("license") or {}).get("spdx_id") or "nicht angegeben"
        return {
            "ok": True,
            "source": f"https://github.com/{owner}/{repo}",
            "owner": owner,
            "repository": repo,
            "default_branch": metadata.get("default_branch", "main"),
            "license": license_name,
            "archived": bool(metadata.get("archived")),
            "stars": int(metadata.get("stargazers_count", 0)),
            "risk": risk,
            "plan": (
                "Repository nur analysiert. Nach Bestätigung werden ausschließlich "
                "unbedenkliche, erlaubte Quelldateien in einen isolierten "
                "imports/{owner}-{repository}/ Ordner kopiert. Keine Installation, "
                "kein Shell-Aufruf und keine Ausführung von Fremdcode."
            ),
            "requires_confirmation": True,
        }

    def _blocked(self, name):
        lowered = name.lower()
        base = Path(name).name.lower()
        return base in self.BLOCKED_NAMES or any(part in lowered for part in self.BLOCKED_PARTS)

    def import_repository(self, url, confirmed=False):
        analysis = self.analyze(url)
        if not confirmed:
            return {"status": "confirmation_required", "analysis": analysis}
        owner, repo = analysis["owner"], analysis["repository"]
        branch = analysis["default_branch"]
        archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
        request = urllib.request.Request(archive_url, headers={"User-Agent": "Jarvis-local-importer"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(self.MAX_ARCHIVE_BYTES + 1)
        if len(payload) > self.MAX_ARCHIVE_BYTES:
            raise GitHubImportError("Das Repository überschreitet das Größenlimit.")
        destination = self.workspace / "imports" / f"{owner}-{repo}"
        destination.mkdir(parents=True, exist_ok=True)
        copied, skipped = [], []
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) > self.MAX_FILES:
                raise GitHubImportError("Das Repository enthält zu viele Dateien.")
            for member in members:
                relative = Path(*Path(member.filename).parts[1:])
                if not relative or self._blocked(str(relative)) or relative.suffix.lower() not in self.ALLOWED_SUFFIXES:
                    skipped.append(str(relative))
                    continue
                if member.file_size > self.MAX_FILE_BYTES:
                    skipped.append(str(relative))
                    continue
                target = (destination / relative).resolve()
                target.relative_to(destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                content = archive.read(member)
                target.write_bytes(content)
                copied.append({
                    "path": str(target.relative_to(self.workspace)),
                    "sha256": hashlib.sha256(content).hexdigest(),
                })
        return {
            "status": "completed",
            "verified": bool(copied),
            "source": analysis["source"],
            "destination": str(destination.relative_to(self.workspace)),
            "copied": copied,
            "skipped_count": len(skipped),
            "message": "Repository analysiert und erlaubte Dateien isoliert übernommen.",
        }
