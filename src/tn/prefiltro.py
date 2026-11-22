"""Prefiltro determinista: lo que se resuelve sin IA antes de que el Editor vea nada (ADR-0002)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tn.modelo import ItemRecogido
from tn.urls import normalizar_url

# Títulos que marcan contenido no editorial (patrocinios, autopromoción).
_NO_EDITORIAL = re.compile(r"\((sponsor|sponsored|tldr community)\)\s*$", re.IGNORECASE)


@dataclass
class ItemFiltrado:
    item: ItemRecogido
    url_normalizada: str


@dataclass
class ResultadoPrefiltro:
    aceptados: list[ItemFiltrado]
    descartados: int


def es_no_editorial(titulo: str) -> bool:
    return bool(_NO_EDITORIAL.search(titulo))


def prefiltrar(items: list[ItemRecogido]) -> ResultadoPrefiltro:
    """Quita patrocinios, Items sin URL o título y duplicados por URL normalizada."""
    aceptados: list[ItemFiltrado] = []
    vistas: set[tuple[str, str]] = set()
    descartados = 0
    for item in items:
        titulo = (item.titulo or "").strip()
        if not titulo or not item.url or es_no_editorial(titulo):
            descartados += 1
            continue
        url_n = normalizar_url(item.url)
        clave = (item.fuente_id, url_n)
        if clave in vistas:
            descartados += 1
            continue
        vistas.add(clave)
        item.titulo = titulo
        aceptados.append(ItemFiltrado(item=item, url_normalizada=url_n))
    return ResultadoPrefiltro(aceptados=aceptados, descartados=descartados)
