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


def cargar_env() -> None:
    """Carga `.env` de la raíz (KEY=valor por línea) sin pisar lo que ya esté en el entorno.

    Ahí viven los secretos (token de Telegram) y ajustes locales; `.env` está en .gitignore.
    """
    ruta = raiz() / ".env"
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def guardar_en_env(clave: str, valor: str) -> None:
    """Añade o reemplaza `clave=valor` en `.env`."""
    ruta = raiz() / ".env"
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.is_file() else []
    lineas = [l for l in lineas if not l.strip().startswith(f"{clave}=")] + [f"{clave}={valor}"]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    os.environ[clave] = valor


def ruta_respaldos() -> Path:
    if env := os.environ.get("TN_RESPALDOS"):
        return Path(env).expanduser().resolve()
    return Path.home() / "Documents" / "tech-news-respaldos"
