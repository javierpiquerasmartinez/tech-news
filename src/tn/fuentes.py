"""Carga y valida el catálogo de Fuentes (fuentes.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

from tn.modelo import TIPOS_FUENTE, Fuente


class CatalogoInvalido(ValueError):
    pass


def cargar_fuentes(ruta: Path) -> list[Fuente]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    crudas = datos.get("fuentes") or []
    fuentes: list[Fuente] = []
    vistos: set[str] = set()
    for i, c in enumerate(crudas, start=1):
        try:
            f = Fuente(
                id=str(c["id"]),
                nombre=str(c["nombre"]),
                grupo=str(c["grupo"]),
                tipo=str(c["tipo"]),
                activa=bool(c.get("activa", True)),
                url=c.get("url"),
                slug=c.get("slug"),
                nota=c.get("nota"),
            )
        except KeyError as e:
            raise CatalogoInvalido(f"Fuente nº {i}: falta el campo {e}") from None
        if f.id in vistos:
            raise CatalogoInvalido(f"Fuente {f.id!r} repetida")
        if f.tipo not in TIPOS_FUENTE:
            raise CatalogoInvalido(f"Fuente {f.id!r}: tipo {f.tipo!r} desconocido")
        if f.tipo == "tldr" and not f.slug:
            raise CatalogoInvalido(f"Fuente {f.id!r}: las de tipo tldr necesitan slug")
        if f.tipo in ("rss", "cisa-kev") and not f.url:
            raise CatalogoInvalido(f"Fuente {f.id!r}: las de tipo {f.tipo} necesitan url")
        vistos.add(f.id)
        fuentes.append(f)
    return fuentes
