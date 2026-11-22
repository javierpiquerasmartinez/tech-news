"""Un recolector por tipo de Fuente.

Cada uno es `recoger(fuente, desde, http) -> list[ItemRecogido]`:
- `desde` es la última recogida con éxito de esa Fuente (None si nunca).
- Devuelve los Items que encuentre a partir de `desde` (con margen); el prefiltro y la
  base de datos se encargan de no duplicar.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from tn.http import Http
from tn.modelo import Fuente, ItemRecogido

Recolector = Callable[[Fuente, "datetime | None", Http], list[ItemRecogido]]

# Primera vez que se recoge una Fuente: cuánto hacia atrás.
VENTANA_INICIAL = timedelta(days=7)
# Margen hacia atrás sobre el cursor, por Fuentes que publican con fecha atrasada.
MARGEN = timedelta(days=2)


def corte(desde: datetime | None, ahora: datetime) -> datetime:
    """Fecha a partir de la cual interesa un Item."""
    return (desde - MARGEN) if desde else (ahora - VENTANA_INICIAL)


def recolectores() -> dict[str, Recolector]:
    from tn.recolectores import cisa_kev, rss, tldr

    return {"rss": rss.recoger, "tldr": tldr.recoger, "cisa-kev": cisa_kev.recoger}
