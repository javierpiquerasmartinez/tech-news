"""Propuestas: la capa humana (ADR-0003). Markdown con cabecera YAML en `semanas/<viernes>/`.

El Redactor (agente) pide `contexto()` y entrega cada Propuesta con `guardar()`. La persona
editora lee, edita y cambia el estado; nada se publica sin que ella lo apruebe.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from tn import config, historias
from tn.db import _iso, ahora

# Formato → nombre de fichero y cómo elige Historias candidatas.
FORMATOS = {
    "resumen": "Resumen semanal",
    "linkedin": "Post de LinkedIn",
    "ideas-didacticas": "Ideas de Vídeo didáctico",
    "didactico": "Vídeo didáctico",
    "bomba": "Vídeo bomba",
}
ESTADOS = ("propuesta", "aprobada", "descartada", "publicada")
TRANSICIONES = {
    "propuesta": ("aprobada", "descartada"),
    "aprobada": ("publicada", "propuesta"),
    "descartada": ("propuesta",),
    "publicada": (),
}
# Formatos que necesitan exactamente una Historia (se piden para una Historia concreta).
POR_HISTORIA = ("didactico", "bomba")
# Una Historia pasa a `usada` cuando la persona editora aprueba una Propuesta basada en
# ella, no cuando el Redactor la escribe. Las ideas no "usan" una Historia: solo el guion.
NO_MARCAN_USADA = ("ideas-didacticas",)
_CABECERA = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


class PropuestaInvalida(ValueError):
    pass


# --- Semanas editoriales ----------------------------------------------------------


def inicio_semana(dia: date) -> date:
    """Viernes de inicio de la Semana editorial (viernes a jueves) que contiene `dia`."""
    return dia - timedelta(days=(dia.weekday() - 4) % 7)


def carpeta_semana(inicio: date) -> Path:
    return config.raiz() / "semanas" / inicio.isoformat()


def semana_por_defecto(momento: datetime | None = None) -> date:
    return inicio_semana((momento or ahora()).date())


def _slug(texto: str, largo: int = 48) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:largo].rstrip("-") or "propuesta"


# --- Ficheros ------------------------------------------------------------------------


@dataclass
class Propuesta:
    ruta: Path
    meta: dict
    cuerpo: str

    @property
    def relativa(self) -> str:
        return str(self.ruta.relative_to(config.raiz()))

    @property
    def estado(self) -> str:
        return self.meta.get("estado", "propuesta")


def leer(ruta: Path) -> Propuesta:
    texto = ruta.read_text(encoding="utf-8")
    m = _CABECERA.match(texto)
    meta = yaml.safe_load(m.group(1)) if m else {}
    return Propuesta(ruta=ruta, meta=meta or {}, cuerpo=texto[m.end():] if m else texto)


def _escribir(p: Propuesta) -> None:
    cabecera = yaml.safe_dump(p.meta, allow_unicode=True, sort_keys=False).strip()
    p.ruta.parent.mkdir(parents=True, exist_ok=True)
    p.ruta.write_text(f"---\n{cabecera}\n---\n\n{p.cuerpo.strip()}\n", encoding="utf-8")


def resolver(nombre: str) -> Path:
    """Acepta `semanas/2026-11-20/x.md` o una ruta absoluta dentro de `semanas/`."""
    base = (config.raiz() / "semanas").resolve()
    ruta = (config.raiz() / nombre).resolve() if not Path(nombre).is_absolute() else Path(nombre).resolve()
    if base not in ruta.parents or ruta.suffix != ".md" or not ruta.is_file():
        raise PropuestaInvalida(f"No encuentro la Propuesta {nombre!r} dentro de semanas/")
    return ruta


def listar(inicio: date | None = None) -> list[Propuesta]:
    carpetas = [carpeta_semana(inicio)] if inicio else sorted((config.raiz() / "semanas").glob("*/"), reverse=True)
    res = []
    for c in carpetas:
        if c.is_dir():
            res += [leer(f) for f in sorted(c.glob("*.md"))]
    orden = list(FORMATOS)
    return sorted(res, key=lambda p: (str(p.ruta.parent), orden.index(p.meta.get("formato", "resumen")) if p.meta.get("formato") in orden else 99, p.ruta.name))


# --- Lo que ve el Redactor ----------------------------------------------------------


def _historia_para_redactor(conn: sqlite3.Connection, hid: int) -> dict:
    h, items = historias.ver(conn, hid)
    return {
        "id": h["id"], "titulo": h["titulo"], "resumen": h["resumen"], "area": h["area"], "estado": h["estado"],
        "urgencia": h["urgencia"], "valor_didactico": h["valor_didactico"], "peso_semanal": h["peso_semanal"],
        "just_urgencia": h["just_urgencia"], "just_didactico": h["just_didactico"], "just_peso": h["just_peso"],
        "es_bomba": bool(h["es_bomba"]), "continua_a": h["continua_a"],
        "items": [{"fuente": i["fuente_id"], "titulo": i["titulo"], "url": i["url"],
                   "resumen": (i["resumen"] or "")[:500] or None, "publicado": (i["publicado_en"] or "")[:10] or None}
                  for i in items],
    }


def contexto(conn: sqlite3.Connection, formato: str, *, semana: date | None = None,
             historia_id: int | None = None, momento: datetime | None = None) -> dict:
    """Historias candidatas y Propuestas ya escritas para que el Redactor elija y no repita."""
    if formato not in FORMATOS:
        raise PropuestaInvalida(f"Formato desconocido: {formato}. Usa uno de {', '.join(FORMATOS)}")
    momento = momento or ahora()
    inicio = semana or semana_por_defecto(momento)
    ya = [{"fichero": p.relativa, "formato": p.meta.get("formato"), "titulo": p.meta.get("titulo"),
           "historias": p.meta.get("historias", []), "estado": p.estado} for p in listar(inicio)]

    if formato in POR_HISTORIA:
        if historia_id is None:
            raise PropuestaInvalida(f"El formato {formato} se pide para una Historia concreta (--historia)")
        candidatas = [_historia_para_redactor(conn, historia_id)]
    else:
        orden, desde, limite = {
            "resumen": ("peso_semanal", datetime.combine(inicio, datetime.min.time(), momento.tzinfo), 20),
            "linkedin": ("peso_semanal", momento - timedelta(days=7), 12),
            "ideas-didacticas": ("valor_didactico", momento - timedelta(days=14), 12),
        }[formato]
        usadas_en_formato = {h for p in ya if p["formato"] == formato for h in p["historias"]}
        filas = historias.listar(conn, desde=desde, estados=("nueva", "destacada", "usada"), orden=orden, limite=limite * 2)
        candidatas = [_historia_para_redactor(conn, f["id"]) for f in filas if f["id"] not in usadas_en_formato][:limite]

    return {
        "formato": formato,
        "nombre_formato": FORMATOS[formato],
        "semana_editorial": {"inicio": inicio.isoformat(), "fin": (inicio + timedelta(days=6)).isoformat()},
        "propuestas_ya_escritas_esta_semana": ya,
        "historias_candidatas": candidatas,
    }


# --- Lo que entrega el Redactor ------------------------------------------------------


def _nombre_fichero(formato: str, titulo: str, carpeta: Path) -> str:
    if formato == "resumen":
        return "resumen-semanal.md"
    if formato == "ideas-didacticas":
        return "ideas-didacticas.md"
    if formato == "linkedin":
        n = len(list(carpeta.glob("linkedin-*.md"))) + 1
        return f"linkedin-{n}-{_slug(titulo, 40)}.md"
    return f"{formato}-{_slug(titulo)}.md"


def guardar(conn: sqlite3.Connection, formato: str, titulo: str, contenido: str, historia_ids: list[int],
            *, semana: date | None = None, enlace: str | None = None) -> Propuesta:
    if formato not in FORMATOS:
        raise PropuestaInvalida(f"Formato desconocido: {formato}")
    titulo, contenido = titulo.strip(), contenido.strip()
    if not titulo or not contenido:
        raise PropuestaInvalida("Una Propuesta necesita título y contenido")
    if not historia_ids:
        raise PropuestaInvalida("Indica en qué Historias se basa (--historias)")
    if formato in POR_HISTORIA and len(historia_ids) != 1:
        raise PropuestaInvalida(f"El formato {formato} se basa en exactamente una Historia")
    for hid in historia_ids:
        try:
            historias.ver(conn, hid)
        except historias.AccionInvalida as e:
            raise PropuestaInvalida(str(e)) from None

    inicio = semana or semana_por_defecto()
    carpeta = carpeta_semana(inicio)
    ruta = carpeta / _nombre_fichero(formato, titulo, carpeta)
    if ruta.exists() and leer(ruta).estado != "propuesta":
        raise PropuestaInvalida(f"{ruta.name} ya está {leer(ruta).estado}: no la sobrescribo")
    meta = {
        "formato": formato,
        "titulo": titulo,
        "estado": "propuesta",
        "historias": historia_ids,
        "semana_editorial": inicio.isoformat(),
        "creada": _iso(ahora()),
    }
    if enlace:
        meta["enlace_primer_comentario"] = enlace
    p = Propuesta(ruta=ruta, meta=meta, cuerpo=contenido)
    _escribir(p)
    return p


# --- Lo que hace la persona editora ---------------------------------------------------


def cambiar_estado(conn: sqlite3.Connection, ruta: Path, nuevo: str, origen: str) -> Propuesta:
    if nuevo not in ESTADOS:
        raise PropuestaInvalida(f"Estado desconocido: {nuevo}. Usa uno de {', '.join(ESTADOS)}")
    p = leer(ruta)
    if nuevo not in TRANSICIONES[p.estado]:
        raise PropuestaInvalida(f"Una Propuesta {p.estado} no puede pasar a {nuevo}")
    p.meta["estado"] = nuevo
    p.meta.setdefault("historial", []).append({"estado": nuevo, "origen": origen, "momento": _iso(ahora())})
    _escribir(p)
    if nuevo in ("aprobada", "publicada") and p.meta.get("formato") not in NO_MARCAN_USADA:
        for hid in p.meta.get("historias", []):
            try:
                h, _ = historias.ver(conn, hid)
            except historias.AccionInvalida:
                continue
            if h["estado"] in ("nueva", "destacada"):
                historias.marcar_usada(conn, hid)
    return p


def editar(ruta: Path, cuerpo: str) -> Propuesta:
    p = leer(ruta)
    if p.estado == "publicada":
        raise PropuestaInvalida("Una Propuesta publicada ya no se edita")
    if not cuerpo.strip():
        raise PropuestaInvalida("El contenido no puede quedar vacío")
    p.cuerpo = cuerpo
    _escribir(p)
    return p


def bombas_sin_propuesta(conn: sqlite3.Connection, momento: datetime | None = None) -> list[int]:
    """Historias bomba del último día que aún no tienen Vídeo bomba."""
    momento = momento or ahora()
    escritas = {h for p in listar(semana_por_defecto(momento)) if p.meta.get("formato") == "bomba"
                for h in p.meta.get("historias", [])}
    filas = historias.listar(conn, desde=momento - timedelta(days=1), estados=("nueva", "destacada", "usada"),
                             solo_bombas=True)
    return [f["id"] for f in filas if f["id"] not in escritas]
