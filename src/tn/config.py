"""Rutas del proyecto. Se pueden sobrescribir con TN_HOME y TN_DB."""

from __future__ import annotations

import os
from pathlib import Path


def raiz() -> Path:
    if env := os.environ.get("TN_HOME"):
        return Path(env).expanduser().resolve()
    # src/tn/config.py → raíz del repo
    return Path(__file__).resolve().parents[2]


def ruta_fuentes() -> Path:
    return raiz() / "fuentes.yaml"


def ruta_db() -> Path:
    if env := os.environ.get("TN_DB"):
        return Path(env).expanduser().resolve()
    return raiz() / "data" / "tech-news.db"
