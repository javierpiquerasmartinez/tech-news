"""Interfaz web local de tech-news.

Lee y escribe a través de las mismas funciones de dominio que la CLI (`tn.historias`,
`tn.db`), con origen `web`; las acciones largas (lanzar el día) se delegan en la propia
CLI `tn` como proceso aparte. Así un botón deja exactamente el mismo rastro que el
comando equivalente (ADR-0004).
"""

from __future__ import annotations

import json
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tn import config, db, historias
from tn.fuentes import cargar_fuentes

AQUI = Path(__file__).parent
ORIGEN = "web"
VISTAS = {"hoy": 1, "semana": 7, "descartadas": 7}
MOTIVOS_DESCARTE = ("No me interesa el tema", "Ya está muy contada", "Es ruido", "Demasiado nicho")
ACCIONES_LANZABLES = {
    "diario": ["diario"],
    "recoger": ["recoger"],
    "editar": ["editar"],
    "explorar": ["explorar"],
}

app = FastAPI(title="tech-news", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
plantillas = Jinja2Templates(directory=AQUI / "templates")


# --- Filtros de plantilla ----------------------------------------------------------


def _fecha(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso) if iso else None


def hace(iso: str | None) -> str:
    """'hace 3 h', 'hace 2 días'… en español."""
    momento = _fecha(iso)
    if not momento:
        return "—"
    s = (db.ahora() - momento).total_seconds()
    if s < 90:
        return "ahora"
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    dias = int(s // 86400)
    return "ayer" if dias == 1 else f"hace {dias} días"


def dia(iso: str | None) -> str:
    momento = _fecha(iso)
    return momento.strftime("%d/%m") if momento else "—"


def nivel(valor: int) -> str:
    return "alto" if valor >= 7 else ("medio" if valor >= 4 else "bajo")


plantillas.env.filters.update(hace=hace, dia=dia, nivel=nivel, json_cargar=lambda t: json.loads(t) if t else {})


# --- Utilidades --------------------------------------------------------------------


@contextmanager
def conexion():
    conn = db.conectar(config.ruta_db())
    try:
        yield conn
    finally:
        conn.close()


def _cabecera(conn) -> dict:
    return {
        "pendientes": historias.pendientes(conn, limite=1)["items_pendientes_total"],
        "en_curso": [dict(e) for e in db.ejecuciones_en_curso(conn)],
    }


def _tarjeta(request: Request, hid: int, error: str | None = None) -> HTMLResponse:
    with conexion() as conn:
        h, items = historias.ver(conn, hid)
        fuentes = len({i["fuente_id"] for i in items})
    return plantillas.TemplateResponse(
        request, "_historia.html",
        {"h": h, "items": items, "n_fuentes": fuentes, "error": error, "motivos": MOTIVOS_DESCARTE},
    )


def _accion(request: Request, hid: int, fn) -> HTMLResponse:
    error = None
    with conexion() as conn:
        try:
            fn(conn)
        except historias.AccionInvalida as e:
            error = str(e)
    return _tarjeta(request, hid, error)


def _recargar() -> Response:
    return Response(status_code=204, headers={"HX-Refresh": "true"})


# --- Historias ---------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def pagina_historias(request: Request, vista: str = "semana", orden: str = "peso_semanal"):
    if vista not in VISTAS:
        vista = "semana"
    if orden not in historias.PUNTUACIONES:
        orden = "peso_semanal"
    estados = ("descartada",) if vista == "descartadas" else ("nueva", "destacada", "usada")
    with conexion() as conn:
        filas = historias.listar(conn, desde=db.ahora() - timedelta(days=VISTAS[vista]),
                                 estados=estados, orden=orden, limite=80)
        tarjetas = []
        for h in filas:
            _, items = historias.ver(conn, h["id"])
            tarjetas.append({"h": h, "items": items, "n_fuentes": h["n_fuentes"]})
        cabecera = _cabecera(conn)
    return plantillas.TemplateResponse(
        request, "historias.html",
        {"tarjetas": tarjetas, "vista": vista, "orden": orden, "motivos": MOTIVOS_DESCARTE,
         "seccion": "historias", **cabecera},
    )


@app.get("/historia/{hid}", response_class=HTMLResponse)
def tarjeta(request: Request, hid: int):
    try:
        return _tarjeta(request, hid)
    except historias.AccionInvalida:
        raise HTTPException(404) from None


@app.post("/historia/{hid}/descartar", response_class=HTMLResponse)
def descartar(request: Request, hid: int, motivo: str = Form("")):
    return _accion(request, hid, lambda c: historias.descartar(c, hid, motivo.strip() or None, ORIGEN))


@app.post("/historia/{hid}/destacar", response_class=HTMLResponse)
def destacar(request: Request, hid: int):
    return _accion(request, hid, lambda c: historias.destacar(c, hid, ORIGEN))


@app.post("/historia/{hid}/restaurar", response_class=HTMLResponse)
def restaurar(request: Request, hid: int):
    return _accion(request, hid, lambda c: historias.restaurar(c, hid, ORIGEN))


@app.post("/historia/{hid}/puntuar", response_class=HTMLResponse)
def puntuar(
    request: Request, hid: int,
    urgencia: int = Form(...), valor_didactico: int = Form(...), peso_semanal: int = Form(...),
    motivo: str = Form(""),
):
    def hacer(conn):
        actual, _ = historias.ver(conn, hid)
        nuevos = {"urgencia": urgencia, "valor_didactico": valor_didactico, "peso_semanal": peso_semanal}
        cambios = {k: v for k, v in nuevos.items() if v != actual[k]}
        if not cambios:
            raise historias.AccionInvalida("No has cambiado ninguna puntuación")
        historias.puntuar(conn, hid, cambios, motivo.strip() or None, ORIGEN)

    return _accion(request, hid, hacer)


@app.post("/historia/{hid}/fusionar")
def fusionar(request: Request, hid: int, otra: int = Form(...)):
    with conexion() as conn:
        try:
            historias.fusionar(conn, hid, otra, ORIGEN)
        except historias.AccionInvalida as e:
            return _tarjeta(request, hid, str(e))
    return _recargar()


@app.post("/historia/{hid}/separar")
def separar(request: Request, hid: int, items: list[int] = Form([]), titulo: str = Form("")):
    if not titulo.strip():
        return _tarjeta(request, hid, "Escribe un título para la Historia nueva")
    with conexion() as conn:
        try:
            historias.separar(conn, hid, items, titulo.strip(), ORIGEN)
        except historias.AccionInvalida as e:
            return _tarjeta(request, hid, str(e))
    return _recargar()


# --- Fuentes -----------------------------------------------------------------------


@app.get("/fuentes", response_class=HTMLResponse)
def pagina_fuentes(request: Request):
    catalogo = cargar_fuentes(config.ruta_fuentes())
    with conexion() as conn:
        estado = db.estado_fuentes(conn)
        cabecera = _cabecera(conn)
    filas = []
    for f in catalogo:
        e = estado.get(f.id, {})
        if not f.activa:
            salud = "pausada"
        elif f.tipo == "explorador":
            salud = "explorador"
        elif e.get("ultimo_error"):
            salud = "error"
        elif not e.get("ultima_ok"):
            salud = "sin-datos"
        else:
            salud = "ok"
        filas.append({"f": f, "e": e, "salud": salud})
    orden = {"error": 0, "sin-datos": 1, "ok": 2, "explorador": 3, "pausada": 4}
    filas.sort(key=lambda x: (orden[x["salud"]], x["f"].grupo, x["f"].id))
    resumen = {k: sum(1 for x in filas if x["salud"] == k) for k in orden}
    return plantillas.TemplateResponse(
        request, "fuentes.html", {"filas": filas, "resumen": resumen, "seccion": "fuentes", **cabecera}
    )


# --- Ejecuciones -------------------------------------------------------------------


@app.get("/ejecuciones", response_class=HTMLResponse)
def pagina_ejecuciones(request: Request, lanzada: str | None = None):
    with conexion() as conn:
        filas = db.ultimas_ejecuciones(conn, 40)
        cabecera = _cabecera(conn)
    return plantillas.TemplateResponse(
        request, "ejecuciones.html",
        {"filas": filas, "lanzada": lanzada, "acciones": list(ACCIONES_LANZABLES), "seccion": "ejecuciones", **cabecera},
    )


@app.get("/ejecuciones/{eid}", response_class=HTMLResponse)
def detalle_ejecucion(request: Request, eid: int):
    with conexion() as conn:
        cab, filas = db.detalle_ejecucion(conn, eid)
    if not cab:
        raise HTTPException(404)
    return plantillas.TemplateResponse(request, "_ejecucion.html", {"e": cab, "fuentes": filas})


@app.post("/lanzar/{accion}")
def lanzar(accion: str):
    """Lanza `tn <accion> --origen web` en segundo plano; su progreso se ve en Ejecuciones."""
    if accion not in ACCIONES_LANZABLES:
        raise HTTPException(404)
    with conexion() as conn:
        if db.ejecuciones_en_curso(conn):
            return RedirectResponse("/ejecuciones?lanzada=ocupado", status_code=303)
    registros = config.ruta_db().parent / "registros"
    registros.mkdir(parents=True, exist_ok=True)
    salida = registros / f"{db.ahora().strftime('%Y%m%dT%H%M%S')}-{accion}.log"
    with salida.open("w") as f:
        subprocess.Popen(
            ["uv", "run", "tn", *ACCIONES_LANZABLES[accion], "--origen", ORIGEN],
            cwd=config.raiz(), stdout=f, stderr=subprocess.STDOUT, start_new_session=True,
        )
    return RedirectResponse(f"/ejecuciones?lanzada={accion}", status_code=303)
