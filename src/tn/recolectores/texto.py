from __future__ import annotations

from selectolax.lexbor import LexborHTMLParser as HTMLParser

LONGITUD_RESUMEN = 1200


def html_a_texto(html: str | None, limite: int = LONGITUD_RESUMEN) -> str | None:
    if not html:
        return None
    texto = HTMLParser(html).text(separator=" ", strip=True) if "<" in html else html
    texto = " ".join(texto.split())
    if len(texto) > limite:
        texto = texto[: limite - 1].rstrip() + "…"
    return texto or None
