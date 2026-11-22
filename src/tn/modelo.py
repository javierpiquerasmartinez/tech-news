"""Tipos del dominio que maneja el Recolector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

TIPOS_FUENTE = ("rss", "tldr", "cisa-kev", "explorador")
ORIGENES = ("manual", "horario", "claude", "web")


@dataclass(frozen=True)
class Fuente:
    id: str
    nombre: str
    grupo: str
    tipo: str
    activa: bool = True
    url: str | None = None
    slug: str | None = None
    nota: str | None = None

    @property
    def la_recoge_el_recolector(self) -> bool:
        return self.activa and self.tipo != "explorador"


@dataclass
class ItemRecogido:
    """Un Item tal como lo trae una Fuente, antes del prefiltro."""

    fuente_id: str
    url: str
    titulo: str
    resumen: str | None = None
    publicado_en: datetime | None = None
    seccion: str | None = None
    origen: str | None = None  # dónde se encontró (p. ej. la edición de TLDR)
