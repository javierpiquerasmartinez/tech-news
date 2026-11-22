"""Catálogo CISA KEV: vulnerabilidades con explotación activa confirmada."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from tn.db import ahora
from tn.http import Http
from tn.modelo import Fuente, ItemRecogido
from tn.recolectores import corte


def parsear_kev(fuente: Fuente, datos: dict, desde: datetime | None, ahora_: datetime) -> list[ItemRecogido]:
    limite = corte(desde, ahora_)
    items: list[ItemRecogido] = []
    for v in datos.get("vulnerabilities", []):
        try:
            añadida = datetime.combine(date.fromisoformat(v["dateAdded"]), time(0, 0), UTC)
        except (KeyError, ValueError):
            continue
        if añadida < limite:
            continue
        cve = v.get("cveID", "")
        nombre = v.get("vulnerabilityName") or f"{v.get('vendorProject', '')} {v.get('product', '')}".strip()
        resumen = v.get("shortDescription") or ""
        if v.get("knownRansomwareCampaignUse") == "Known":
            resumen = f"[Usada en campañas de ransomware] {resumen}"
        items.append(
            ItemRecogido(
                fuente_id=fuente.id,
                url=f"https://nvd.nist.gov/vuln/detail/{cve}",
                titulo=f"{cve}: {nombre}",
                resumen=resumen or None,
                publicado_en=añadida,
                seccion=v.get("vendorProject"),
                origen=fuente.url,
            )
        )
    return items


def recoger(fuente: Fuente, desde: datetime | None, http: Http) -> list[ItemRecogido]:
    assert fuente.url
    return parsear_kev(fuente, http.json(fuente.url), desde, ahora())
