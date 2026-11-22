"""Fichas de feedback (GLOSSARY.md): notas de la persona editora sobre un Montaje, con minuto.

Viven en `semanas/<viernes>/montaje-feedback.md` (capa humana, ADR-0003), una línea por nota:

    - v1 · 02:15 · el rótulo tapa la barbilla · 2026-11-22

Las lee la siguiente versión del Montaje y, en conjunto, `tn estilo revisar`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from tn import config, propuestas
from tn.db import ahora

_LINEA = re.compile(r"^- (?P<version>v\d+|—) · (?P<minuto>\d{1,2}:\d{2}|—) · (?P<texto>.+?) · (?P<fecha>\d{4}-\d{2}-\d{2})\s*$")
_MINUTO = re.compile(r"^\s*(\d{1,2}):(\d{2})\b\s*[-–—:·]?\s*")


@dataclass
class Nota:
    semana: str
    version: str
    minuto: str
    texto: str
    fecha: str

    @property
    def segundos(self) -> float | None:
        if self.minuto == "—":
            return None
        m, s = self.minuto.split(":")
        return int(m) * 60 + int(s)

    def como_dict(self) -> dict:
        return {"semana": self.semana, "version": self.version, "minuto": self.minuto,
                "segundos": self.segundos, "texto": self.texto, "fecha": self.fecha}


def ruta(semana: date):
    return propuestas.carpeta_semana(semana) / "montaje-feedback.md"


def anadir(semana: date, texto: str, version: str = "—") -> Nota:
    """Añade una nota. Si empieza por `MM:SS`, ese es el minuto al que se refiere."""
    texto = texto.strip()
    if not texto:
        raise ValueError("La nota está vacía")
    minuto = "—"
    if m := _MINUTO.match(texto):
        minuto = f"{int(m.group(1)):02d}:{m.group(2)}"
        texto = texto[m.end():].strip()
    texto = texto.replace("\n", " ").replace(" · ", " - ")
    nota = Nota(semana.isoformat(), version, minuto, texto, ahora().date().isoformat())
    r = ruta(semana)
    r.parent.mkdir(parents=True, exist_ok=True)
    if not r.is_file():
        r.write_text(f"# Ficha de feedback · semana {semana.isoformat()}\n\n"
                     "Una nota por línea: versión del Montaje · minuto · qué cambiar · fecha.\n\n", encoding="utf-8")
    with r.open("a", encoding="utf-8") as f:
        f.write(f"- {nota.version} · {nota.minuto} · {nota.texto} · {nota.fecha}\n")
    return nota


def leer(semana: date) -> list[Nota]:
    r = ruta(semana)
    if not r.is_file():
        return []
    notas = []
    for linea in r.read_text(encoding="utf-8").splitlines():
        if m := _LINEA.match(linea.strip()):
            notas.append(Nota(semana.isoformat(), m["version"], m["minuto"], m["texto"], m["fecha"]))
    return notas


def todas(desde: str = "") -> list[Nota]:
    """Notas de todas las semanas con fecha posterior a `desde` (AAAA-MM-DD)."""
    res = []
    for carpeta in sorted((config.raiz() / "semanas").glob("*/")):
        try:
            semana = date.fromisoformat(carpeta.name)
        except ValueError:
            continue
        res += [n for n in leer(semana) if n.fecha > desde]
    return res
