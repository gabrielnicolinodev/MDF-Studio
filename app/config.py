"""Configurações padrão e constantes centralizadas da aplicação."""
from __future__ import annotations

from pathlib import Path

from app import __version__

APP_NAME = "MDF Studio"
APP_VERSION = __version__
ORGANIZATION_NAME = "MDFStudio"
APP_DESCRIPTION = (
    "Aplicação desktop para criar projetos paramétricos em MDF "
    "(caixas, gavetas, organizadores e divisórias) e exportá-los em SVG "
    "para corte a laser."
)

SETTINGS_FILENAME = "settings.json"

# Opcoes validas (preparadas para crescer em etapas futuras).
VALID_UNITS = ("mm",)
VALID_THEMES = ("dark",)
STARTUP_PAGES = ("home", "generators", "projects", "settings", "last")

UNIT_LABELS = {"mm": "Milímetros (mm)"}
THEME_LABELS = {"dark": "Escuro"}
STARTUP_LABELS = {
    "home": "Abrir na página Início",
    "generators": "Abrir em Geradores",
    "projects": "Abrir em Meus projetos",
    "settings": "Abrir em Configurações",
    "last": "Reabrir a última página usada",
}


def default_export_dir() -> str:
    """Pasta de exportação padrão: ~/Documents/MDF Studio (ou ~/MDF Studio)."""
    home = Path.home()
    documents = home / "Documents"
    base = documents if documents.is_dir() else home
    return str(base / APP_NAME)


def default_settings() -> dict:
    """Retorna uma copia nova dos valores padrão."""
    return {
        "unit": "mm",
        "theme": "dark",
        "export_dir": default_export_dir(),
        "startup_page": "home",
        "last_page": "home",
    }


def sanitize_settings(raw: object) -> dict:
    """Mescla `raw` com os padrões, descartando chaves/valores invalidos."""
    result = default_settings()
    if not isinstance(raw, dict):
        return result
    if raw.get("unit") in VALID_UNITS:
        result["unit"] = raw["unit"]
    if raw.get("theme") in VALID_THEMES:
        result["theme"] = raw["theme"]
    export_dir = raw.get("export_dir")
    if isinstance(export_dir, str) and export_dir.strip():
        result["export_dir"] = export_dir.strip()
    if raw.get("startup_page") in STARTUP_PAGES:
        result["startup_page"] = raw["startup_page"]
    if raw.get("last_page") in STARTUP_PAGES and raw["last_page"] != "last":
        result["last_page"] = raw["last_page"]
    return result
