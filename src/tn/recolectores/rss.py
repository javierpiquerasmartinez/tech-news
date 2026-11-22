"""Fuentes con feed RSS o Atom."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime

import feedparser

from tn.db import ahora
from tn.http import Http
from tn.modelo import Fuente, ItemRecogido
from tn.recolectores import corte
from tn.recolectores.texto import html_a_texto


class FeedIlegible(RuntimeError):
    pass


def _fecha(entrada) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entrada.get(campo)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), UTC)
    return None


def parsear_feed(fuente: Fuente, contenido: str | bytes, desde: datetime | None, ahora_: datetime) -> list[ItemRecogido]:
    feed = feedparser.parse(contenido)
    if feed.bozo and not feed.entries:
        raise FeedIlegible(f"feed ilegible: {feed.get('bozo_exception')}")
    limite = corte(desde, ahora_)
    items: list[ItemRecogido] = []
    for e in feed.entries:
        url = e.get("link")
        if not url:
            continue
        publicado = _fecha(e)
        if publicado and publicado < limite:
            continue
        items.append(
            ItemRecogido(
                fuente_id=fuente.id,
                url=url,
                titulo=html_a_texto(e.get("title"), limite=300) or "",
                resumen=html_a_texto(e.get("summary")),
                publicado_en=publicado,
                origen=fuente.url,
            )
        )
    return items


def recoger(fuente: Fuente, desde: datetime | None, http: Http) -> list[ItemRecogido]:
    assert fuente.url
    return parsear_feed(fuente, http.get(fuente.url).content, desde, ahora())
