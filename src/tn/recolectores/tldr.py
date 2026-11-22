"""Newsletters TLDR leídas desde su web (docs/research/fuentes.md, Parte 1).

- El RSS (`/api/rss/{slug}`) solo dice qué ediciones existen; no trae noticias.
- Cada edición está en `/{slug}/{YYYY-MM-DD}`, renderizada en servidor.
- Una fecha sin edición devuelve 200 con la portada (soft 404): se detecta por contenido.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from tn.db import ahora
from tn.http import Http
from tn.modelo import Fuente, ItemRecogido
from tn.recolectores import corte
from tn.recolectores.rss import parsear_feed
from tn.recolectores.texto import html_a_texto

BASE = "https://tldr.tech"
MAX_EDICIONES_POR_EJECUCION = 10

_FECHA_EN_URL = re.compile(r"/(\d{4}-\d{2}-\d{2})/?$")
_MINUTOS = re.compile(r"\s*\(\d+\s+minute read\)\s*$", re.IGNORECASE)


def url_edicion(slug: str, dia: date) -> str:
    return f"{BASE}/{slug}/{dia.isoformat()}"


def ediciones_disponibles(fuente: Fuente, rss: str | bytes, desde: datetime | None, ahora_: datetime) -> list[tuple[date, str]]:
    """Ediciones que anuncia el RSS desde el corte, de más antigua a más reciente."""
    entradas = parsear_feed(fuente, rss, desde, ahora_)
    ediciones = []
    for e in entradas:
        m = _FECHA_EN_URL.search(e.url)
        if m:
            ediciones.append((date.fromisoformat(m.group(1)), e.url))
    ediciones.sort()
    return ediciones[-MAX_EDICIONES_POR_EJECUCION:]


def es_edicion(html: str) -> bool:
    """False si la página es la portada que TLDR sirve para fechas sin edición."""
    arbol = HTMLParser(html)
    h1 = arbol.css_first("h1")
    return bool(h1 and h1.text(strip=True).startswith("TLDR") and arbol.css_first("article"))


def parsear_edicion(fuente: Fuente, html: str, url: str, dia: date) -> list[ItemRecogido]:
    arbol = HTMLParser(html)
    if not es_edicion(html):
        return []
    publicado = datetime.combine(dia, time(0, 0), UTC)
    items: list[ItemRecogido] = []
    seccion: str | None = None
    # Cabeceras de sección y artículos, en orden de documento.
    for nodo in arbol.css("h3.text-center, article"):
        if nodo.tag == "h3":
            seccion = nodo.text(strip=True) or seccion
            continue
        enlace = nodo.css_first("a[href]")
        titulo_nodo = nodo.css_first("h3")
        if not enlace or not titulo_nodo:
            continue
        titulo = _MINUTOS.sub("", titulo_nodo.text(strip=True))
        cuerpo = nodo.css_first("div.newsletter-html")
        items.append(
            ItemRecogido(
                fuente_id=fuente.id,
                url=enlace.attributes.get("href") or "",
                titulo=titulo,
                resumen=html_a_texto(cuerpo.html if cuerpo else None),
                publicado_en=publicado,
                seccion=seccion,
                origen=url,
            )
        )
    return items


def recoger(fuente: Fuente, desde: datetime | None, http: Http) -> list[ItemRecogido]:
    assert fuente.slug
    ahora_ = ahora()
    rss = http.get(f"{BASE}/api/rss/{fuente.slug}").content
    items: list[ItemRecogido] = []
    for dia, url in ediciones_disponibles(fuente, rss, desde, ahora_):
        items.extend(parsear_edicion(fuente, http.texto(url), url, dia))
    return items
