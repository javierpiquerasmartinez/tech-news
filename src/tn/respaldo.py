"""Copia de seguridad diaria: la SQLite y `semanas/`, las dos capas que no están en git (ADR-0003)."""

from __future__ import annotations

import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from tn import config

CONSERVAR = 14  # copias diarias que se guardan


def respaldar(destino: Path | None = None, conservar: int = CONSERVAR) -> Path:
    destino = destino or config.ruta_respaldos()
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"tech-news-{datetime.now().strftime('%Y-%m-%d_%H%M')}.tar.gz"  # hora local
    with tempfile.TemporaryDirectory() as tmp:
        copia_db = Path(tmp) / "tech-news.db"
        origen = config.ruta_db()
        if origen.is_file():
            # API de backup de SQLite: copia consistente aunque haya otra conexión abierta.
            with sqlite3.connect(origen) as src, sqlite3.connect(copia_db) as dst:
                src.backup(dst)
        with tarfile.open(archivo, "w:gz") as tar:
            if copia_db.is_file():
                tar.add(copia_db, arcname="data/tech-news.db")
            semanas = config.raiz() / "semanas"
            if semanas.is_dir():
                tar.add(semanas, arcname="semanas")
            for suelto in ("perfil-editorial.md", "voz.md", "fuentes.yaml"):
                if (config.raiz() / suelto).is_file():
                    tar.add(config.raiz() / suelto, arcname=suelto)
    copias = sorted(destino.glob("tech-news-*.tar.gz"))
    for vieja in copias[:-conservar]:
        vieja.unlink()
    return archivo
