"""Persistencia das configuracoes em JSON (sem dependencia de Qt)."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from app.config import SETTINGS_FILENAME, default_settings, sanitize_settings

log = logging.getLogger(__name__)


def default_settings_path() -> Path:
    """Caminho do settings.json no diretorio de dados do usuario.

    Usa QStandardPaths (AppDataLocation) quando PySide6 esta disponível.
    """
    try:
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if base:
            return Path(base) / SETTINGS_FILENAME
    except Exception:  # pragma: no cover - fallback defensivo
        log.exception("QStandardPaths indisponivel; usando fallback")
    return Path.home() / ".mdf-studio" / SETTINGS_FILENAME


class SettingsStore:
    """Le e grava configuracoes; nunca levanta excecao ao carregar."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_settings_path()

    def load(self) -> dict:
        """Carrega configuracoes; em qualquer falha devolve os padrões."""
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default_settings()
        except OSError as exc:
            log.warning("Não foi possivel ler %s: %s", self.path, exc)
            return default_settings()
        if not text.strip():
            return default_settings()
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            log.warning("JSON invalido em %s: %s", self.path, exc)
            return default_settings()
        return sanitize_settings(raw)

    def save(self, settings: dict) -> bool:
        """Grava de forma atomica. Retorna False se a gravacao falhar."""
        data = sanitize_settings(settings)
        tmp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self.path.parent, prefix=".settings-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_name, self.path)
            return True
        except OSError as exc:
            log.error("Não foi possivel gravar %s: %s", self.path, exc)
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
            return False
