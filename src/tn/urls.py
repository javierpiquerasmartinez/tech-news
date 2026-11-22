"""Normalización de URLs para deduplicar Items."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parámetros de seguimiento que no cambian el contenido enlazado.
_PARAMS_SEGUIMIENTO = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src",
    "_hsenc", "_hsmi", "mkt_tok", "igshid", "si",
}


def _es_seguimiento(clave: str) -> bool:
    k = clave.lower()
    return k.startswith("utm_") or k in _PARAMS_SEGUIMIENTO


def normalizar_url(url: str, conservar_fragmento: bool = False) -> str:
    """Forma canónica de una URL: sin seguimiento, sin fragmento, host en minúsculas.

    `conservar_fragmento` es para páginas con varias entradas (changelogs), donde el
    `#ancla` es lo único que distingue una entrada de otra.
    """
    partes = urlsplit(url.strip())
    esquema = (partes.scheme or "https").lower()
    if esquema == "http":
        esquema = "https"
    host = partes.hostname.lower() if partes.hostname else ""
    if host.startswith("www."):
        host = host[4:]
    if partes.port and partes.port not in (80, 443):
        host = f"{host}:{partes.port}"
    ruta = partes.path or "/"
    if len(ruta) > 1 and ruta.endswith("/"):
        ruta = ruta.rstrip("/")
    query = sorted(
        (k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True) if not _es_seguimiento(k)
    )
    return urlunsplit((esquema, host, ruta, urlencode(query), partes.fragment if conservar_fragmento else ""))
