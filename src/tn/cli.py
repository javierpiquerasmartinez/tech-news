"""CLI `tn`: el único punto de entrada al sistema (ADR-0004)."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from tn import agentes, config, db, historias
from tn.fuentes import cargar_fuentes
from tn.http import Http
from tn.modelo import ORIGENES, ItemRecogido
from tn.prefiltro import prefiltrar
from tn.recoger import ResultadoFuente, recoger

app = typer.Typer(
    help="tech-news: recoge Fuentes, agrupa Historias y propone contenido. Ver docs/arnes.md.",
    no_args_is_help=True,
    add_completion=False,
)

OpcionOrigen = Annotated[
    str,
    typer.Option(help=f"Quién lanza la Ejecución: {' | '.join(ORIGENES)}."),
]


def _validar_origen(origen: str) -> str:
    if origen not in ORIGENES:
        raise typer.BadParameter(f"origen debe ser uno de: {', '.join(ORIGENES)}")
    return origen


@app.command("recoger")
def cmd_recoger(
    fuente: Annotated[
        list[str] | None,
        typer.Option("--fuente", "-f", help="Recoger solo esta Fuente (repetible)."),
    ] = None,
    origen: OpcionOrigen = "manual",
) -> None:
    """Recolector: recoge Items nuevos de las Fuentes activas desde la última recogida con éxito."""
    _validar_origen(origen)
    fuentes = cargar_fuentes(config.ruta_fuentes())
    if fuente:
        desconocidas = set(fuente) - {f.id for f in fuentes}
        if desconocidas:
            raise typer.BadParameter(f"Fuentes desconocidas: {', '.join(sorted(desconocidas))}")

    def progreso(r: ResultadoFuente) -> None:
        if r.error:
            typer.secho(f"  ✗ {r.fuente_id:<22} {r.error}", fg=typer.colors.RED)
        else:
            typer.echo(f"  ✓ {r.fuente_id:<22} {r.nuevos:>4} nuevos  ({r.recogidos} recogidos, {r.descartados} descartados)")

    conn = db.conectar(config.ruta_db())
    http = Http()
    try:
        typer.echo("Recogiendo…")
        res = recoger(conn, fuentes, origen=origen, http=http, solo=set(fuente) if fuente else None,
                      al_terminar_fuente=progreso)
    finally:
        http.cerrar()
        conn.close()
    color = {"ok": typer.colors.GREEN, "con_errores": typer.colors.YELLOW}.get(res.estado, typer.colors.RED)
    typer.secho(f"Ejecución #{res.ejecucion_id}: {res.estado} · {res.nuevos} Items nuevos", fg=color, bold=True)
    if res.estado == "fallida":
        raise typer.Exit(1)


@app.command("ejecuciones")
def cmd_ejecuciones(
    id: Annotated[int | None, typer.Option("--id", help="Ver el detalle por Fuente de una Ejecución.")] = None,
    limite: Annotated[int, typer.Option(help="Cuántas mostrar.")] = 10,
) -> None:
    """Registro de Ejecuciones: cuándo, quién la lanzó, Items nuevos y errores."""
    conn = db.conectar(config.ruta_db())
    try:
        if id is not None:
            cab, filas = db.detalle_ejecucion(conn, id)
            if not cab:
                raise typer.BadParameter(f"No existe la Ejecución #{id}")
            typer.echo(f"#{cab['id']} {cab['comando']} · {cab['origen']} · {cab['estado']}")
            typer.echo(f"   inicio {cab['inicio']} · fin {cab['fin'] or '—'}")
            if cab["uso"]:
                typer.echo(f"   uso: {cab['uso']}")
            if cab["resultado"]:
                typer.echo(f"\n{cab['resultado']}\n")
            for f in filas:
                if f["error"]:
                    typer.secho(f"  ✗ {f['fuente_id']:<22} {f['error']}", fg=typer.colors.RED)
                else:
                    typer.echo(f"  ✓ {f['fuente_id']:<22} {f['nuevos']:>4} nuevos  ({f['recogidos']} recogidos, {f['descartados']} descartados)")
            return
        filas = db.ultimas_ejecuciones(conn, limite)
        if not filas:
            typer.echo("Todavía no hay Ejecuciones. Lanza `tn recoger`.")
            return
        typer.echo(f"{'#':>4}  {'inicio (UTC)':<20} {'origen':<8} {'comando':<18} {'estado':<12} {'items':>5} {'hist.':>5}  errores")
        for e in filas:
            errores = f"{e['errores'] or 0}/{e['fuentes']}" if e["fuentes"] else "—"
            typer.echo(
                f"{e['id']:>4}  {e['inicio'][:19]:<20} {e['origen']:<8} {e['comando'][:18]:<18} "
                f"{e['estado']:<12} {e['nuevos']:>5} {e['historias']:>5}  {errores}"
            )
    finally:
        conn.close()


@app.command("fuentes")
def cmd_fuentes(
    tipo: Annotated[str | None, typer.Option(help="Filtrar por tipo (p. ej. explorador).")] = None,
    como_json: Annotated[bool, typer.Option("--json", help="Salida JSON.")] = False,
) -> None:
    """Catálogo de Fuentes (fuentes.yaml) y quién recoge cada una."""
    fuentes = [f for f in cargar_fuentes(config.ruta_fuentes()) if not tipo or f.tipo == tipo]
    if como_json:
        _json([{"id": f.id, "nombre": f.nombre, "grupo": f.grupo, "tipo": f.tipo, "url": f.url,
                "activa": f.activa, "nota": f.nota} for f in fuentes if f.activa])
        return
    for f in fuentes:
        quien = "Explorador" if f.tipo == "explorador" else "Recolector"
        estado = "" if f.activa else " (pausada)"
        typer.echo(f"{f.grupo:<12} {f.id:<22} {f.tipo:<10} {quien}{estado}")


# --- Utilidades ------------------------------------------------------------------


def _json(datos, compacto: bool = False) -> None:
    if compacto:  # para los agentes: menos tokens
        typer.echo(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), default=str))
    else:
        typer.echo(json.dumps(datos, ensure_ascii=False, indent=1, default=str))


def _conn():
    return db.conectar(config.ruta_db())


def _fallar(e: Exception) -> None:
    typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _puntos(h) -> str:
    return f"U{h['urgencia']:>2} D{h['valor_didactico']:>2} S{h['peso_semanal']:>2}"


# --- Editor (lo usa la skill; también sirve para depurar) -------------------------

editor_app = typer.Typer(help="Entrada y salida del Editor: Items pendientes y lotes de decisiones.", no_args_is_help=True)
app.add_typer(editor_app, name="editor")


@editor_app.command("pendientes")
def cmd_editor_pendientes(
    limite: Annotated[int, typer.Option(help="Máximo de Items por lote.")] = 120,
) -> None:
    """JSON con Items pendientes agrupados por URL y las Historias abiertas."""
    conn = _conn()
    try:
        _json(historias.pendientes(conn, limite=limite), compacto=True)
    finally:
        conn.close()


@editor_app.command("aplicar")
def cmd_editor_aplicar(
    fichero: Annotated[str | None, typer.Argument(help="Fichero JSON con el lote, o - para leer de stdin.")] = None,
    lote_txt: Annotated[str | None, typer.Option("--lote", help="El lote como texto JSON (lo usa el Editor headless).")] = None,
) -> None:
    """Aplica un lote de decisiones del Editor (todo o nada)."""
    if lote_txt is not None:
        texto = lote_txt
    elif fichero and fichero != "-":
        texto = Path(fichero).read_text(encoding="utf-8")
    else:
        texto = sys.stdin.read()
    try:
        lote = json.loads(texto)
    except json.JSONDecodeError as e:
        _fallar(historias.LoteInvalido(f"JSON inválido: {e}"))
    ejecucion = int(os.environ["TN_EJECUCION"]) if os.environ.get("TN_EJECUCION") else None
    conn = _conn()
    try:
        _json(historias.aplicar_lote(conn, lote, ejecucion))
    except historias.LoteInvalido as e:
        _fallar(e)
    finally:
        conn.close()


# --- Historias -----------------------------------------------------------------


@app.command("historias")
def cmd_historias(
    dias: Annotated[int, typer.Option(help="Historias con Items en los últimos N días.")] = 7,
    orden: Annotated[str, typer.Option(help="urgencia | valor_didactico | peso_semanal")] = "peso_semanal",
    estado: Annotated[list[str] | None, typer.Option(help="Estados a mostrar (repetible).")] = None,
    bombas: Annotated[bool, typer.Option("--bombas", help="Solo Historias bomba.")] = False,
    limite: Annotated[int, typer.Option(help="Cuántas mostrar.")] = 30,
    como_json: Annotated[bool, typer.Option("--json", help="Salida JSON.")] = False,
) -> None:
    """Historias ordenadas por puntuación (bombas y destacadas primero)."""
    conn = _conn()
    try:
        filas = historias.listar(
            conn, desde=db.ahora() - timedelta(days=dias),
            estados=tuple(estado) if estado else ("nueva", "destacada", "usada"),
            solo_bombas=bombas, orden=orden, limite=limite,
        )
    except historias.AccionInvalida as e:
        _fallar(e)
    finally:
        conn.close()
    if como_json:
        _json([dict(f) for f in filas])
        return
    if not filas:
        typer.echo("No hay Historias en ese periodo. ¿Has lanzado `tn editar`?")
        return
    for h in filas:
        marca = "💥" if h["es_bomba"] else ("★" if h["estado"] == "destacada" else " ")
        estado_txt = "" if h["estado"] == "nueva" else f" [{h['estado']}]"
        typer.echo(f"{marca} #{h['id']:<5} {_puntos(h)}  {h['area'] or '':<12} {h['titulo']}{estado_txt}  ({h['n_items']} items, {h['n_fuentes']} fuentes)")
    typer.echo("U = Urgencia · D = Valor didáctico · S = Peso semanal")


historia_app = typer.Typer(help="Ver y corregir una Historia.", no_args_is_help=True)
app.add_typer(historia_app, name="historia")


@historia_app.command("ver")
def cmd_historia_ver(
    id: int,
    como_json: Annotated[bool, typer.Option("--json", help="Salida JSON.")] = False,
) -> None:
    """Una Historia con sus puntuaciones justificadas y sus Items."""
    conn = _conn()
    try:
        h, items = historias.ver(conn, id)
    except historias.AccionInvalida as e:
        _fallar(e)
    finally:
        conn.close()
    if como_json:
        _json({**dict(h), "items": [dict(i) for i in items]})
        return
    typer.secho(f"#{h['id']} {h['titulo']}", bold=True)
    typer.echo(f"   {h['estado']} · {h['area']} · último Item {h['ultimo_item_en'][:10]}" + (" · 💥 BOMBA" if h["es_bomba"] else ""))
    if h["motivo_descarte"]:
        typer.echo(f"   motivo del descarte: {h['motivo_descarte']}")
    if h["resumen"]:
        typer.echo(f"\n{h['resumen']}\n")
    typer.echo(f"  Urgencia        {h['urgencia']:>2}  {h['just_urgencia']}")
    typer.echo(f"  Valor didáctico {h['valor_didactico']:>2}  {h['just_didactico']}")
    typer.echo(f"  Peso semanal    {h['peso_semanal']:>2}  {h['just_peso']}")
    typer.echo("\nItems:")
    for i in items:
        typer.echo(f"  [{i['id']}] {i['fuente_id']}: {i['titulo']}\n        {i['url']}")


OpcionOrigenAccion = Annotated[str, typer.Option(help=f"Quién decide: {' | '.join(ORIGENES)}.")]


def _accion(fn) -> None:
    conn = _conn()
    try:
        fn(conn)
    except historias.AccionInvalida as e:
        _fallar(e)
    finally:
        conn.close()


@historia_app.command("descartar")
def cmd_descartar(
    id: int,
    motivo: Annotated[str | None, typer.Option(help="Por qué (alimenta el Perfil editorial).")] = None,
    origen: OpcionOrigenAccion = "manual",
) -> None:
    """Retira una Historia. El motivo es opcional pero ayuda a afinar el perfil."""
    _accion(lambda c: historias.descartar(c, id, motivo, _validar_origen(origen)))
    typer.echo(f"Historia #{id} descartada.")


@historia_app.command("destacar")
def cmd_destacar(id: int, origen: OpcionOrigenAccion = "manual") -> None:
    """Fuerza que una Historia se use aunque su puntuación no lo justifique."""
    _accion(lambda c: historias.destacar(c, id, _validar_origen(origen)))
    typer.echo(f"Historia #{id} destacada.")


@historia_app.command("restaurar")
def cmd_restaurar(id: int, origen: OpcionOrigenAccion = "manual") -> None:
    """Deshace un descarte o un destacado: la Historia vuelve a estar nueva."""
    _accion(lambda c: historias.restaurar(c, id, _validar_origen(origen)))
    typer.echo(f"Historia #{id} restaurada.")


@historia_app.command("puntuar")
def cmd_puntuar(
    id: int,
    urgencia: Annotated[int | None, typer.Option(min=0, max=10)] = None,
    didactico: Annotated[int | None, typer.Option(min=0, max=10, help="Valor didáctico.")] = None,
    peso: Annotated[int | None, typer.Option(min=0, max=10, help="Peso semanal.")] = None,
    motivo: Annotated[str | None, typer.Option(help="Por qué corriges al Editor.")] = None,
    origen: OpcionOrigenAccion = "manual",
) -> None:
    """Corrige una o varias puntuaciones del Editor."""
    cambios = {k: v for k, v in {"urgencia": urgencia, "valor_didactico": didactico, "peso_semanal": peso}.items() if v is not None}
    _accion(lambda c: historias.puntuar(c, id, cambios, motivo, _validar_origen(origen)))
    typer.echo(f"Historia #{id} puntuada de nuevo.")


@historia_app.command("fusionar")
def cmd_fusionar(
    destino: Annotated[int, typer.Argument(help="La Historia que se queda.")],
    otra: Annotated[int, typer.Argument(help="La Historia que se absorbe.")],
    origen: OpcionOrigenAccion = "manual",
) -> None:
    """Une dos Historias que son la misma: los Items de la segunda pasan a la primera."""
    _accion(lambda c: historias.fusionar(c, destino, otra, _validar_origen(origen)))
    typer.echo(f"Historia #{otra} fusionada en #{destino}.")


@historia_app.command("separar")
def cmd_separar(
    id: int,
    items: Annotated[str, typer.Option(help="Ids de los Items a sacar, separados por comas.")],
    titulo: Annotated[str, typer.Option(help="Título de la Historia nueva.")],
    origen: OpcionOrigenAccion = "manual",
) -> None:
    """Saca algunos Items de una Historia a una Historia nueva."""
    try:
        ids = [int(x) for x in items.split(",") if x.strip()]
    except ValueError:
        raise typer.BadParameter("--items debe ser una lista de números separados por comas") from None
    nueva: list[int] = []
    _accion(lambda c: nueva.append(historias.separar(c, id, ids, titulo, _validar_origen(origen))))
    typer.echo(f"Items separados de #{id} en la Historia nueva #{nueva[0]}.")


# --- Items añadidos a mano o por el Explorador ----------------------------------

item_app = typer.Typer(help="Añadir Items que el Recolector no alcanza.", no_args_is_help=True)
app.add_typer(item_app, name="item")


@item_app.command("anadir")
def cmd_item_anadir(
    fuente: Annotated[str, typer.Option(help="Id de la Fuente, o `explorador` si no es de ninguna.")],
    url: Annotated[str, typer.Option()],
    titulo: Annotated[str, typer.Option()],
    resumen: Annotated[str | None, typer.Option()] = None,
    publicado: Annotated[str | None, typer.Option(help="Fecha AAAA-MM-DD.")] = None,
    motivo: Annotated[str | None, typer.Option(help="Por qué se añade (p. ej. fuente primaria de la Historia 12).")] = None,
) -> None:
    """Añade un Item (pasa por el mismo prefiltro que el Recolector; los duplicados se ignoran)."""
    ids = {f.id for f in cargar_fuentes(config.ruta_fuentes())} | {"explorador", "manual"}
    if fuente not in ids:
        raise typer.BadParameter(f"Fuente desconocida: {fuente}")
    fecha = None
    if publicado:
        try:
            fecha = datetime.combine(date.fromisoformat(publicado), datetime.min.time(), UTC)
        except ValueError:
            raise typer.BadParameter("--publicado debe ser AAAA-MM-DD") from None
    item = ItemRecogido(fuente_id=fuente, url=url, titulo=titulo, resumen=resumen, publicado_en=fecha,
                        origen=f"explorador: {motivo}" if motivo else "explorador")
    filtrado = prefiltrar([item], conservar_fragmento=True)
    if not filtrado.aceptados:
        typer.echo("Descartado por el prefiltro (patrocinio, sin título o sin URL).")
        return
    conn = _conn()
    try:
        ejecucion = int(os.environ["TN_EJECUCION"]) if os.environ.get("TN_EJECUCION") else \
            db.abrir_ejecucion(conn, "item anadir", "manual", db.ahora())
        nuevos = db.insertar_items(conn, ejecucion, filtrado.aceptados, db.ahora())
        conn.commit()
        if not os.environ.get("TN_EJECUCION"):
            db.cerrar_ejecucion(conn, ejecucion, "ok")
    finally:
        conn.close()
    typer.echo("Item añadido." if nuevos else "Ya existía: no se duplica.")


# --- Roles que son agentes --------------------------------------------------------


def _lanzar_agente(rol: str, instrucciones: str, origen: str) -> agentes.ResultadoAgente:
    _validar_origen(origen)
    conn = _conn()
    try:
        typer.echo(f"Lanzando {rol} (puede tardar varios minutos)…")
        res = agentes.lanzar(conn, rol, instrucciones, origen=origen)
    except RuntimeError as e:
        _fallar(e)
    finally:
        conn.close()
    color = typer.colors.GREEN if res.estado == "ok" else typer.colors.RED
    typer.secho(f"Ejecución #{res.ejecucion_id} ({rol}): {res.estado}", fg=color, bold=True)
    if res.uso:
        u = res.uso
        typer.echo(f"   {u.get('modelo')} · {u.get('turnos')} turnos · {u.get('duracion_s')} s · "
                   f"tokens entrada {u.get('tokens_entrada')} (+{u.get('tokens_cache_lectura')} caché) / salida {u.get('tokens_salida')}")
    typer.echo(res.resultado)
    return res


@app.command("editar")
def cmd_editar(
    max_items: Annotated[int | None, typer.Option(help="Procesar como mucho N Items (para pruebas o para repartir la cuota).")] = None,
    origen: OpcionOrigen = "manual",
) -> None:
    """Editor: agrupa los Items pendientes en Historias y las puntúa."""
    instrucciones = (
        f"Esta vez procesa como máximo {max_items} Items: pide un único lote con "
        f"`uv run tn editor pendientes --limite {max_items}`, aplícalo y termina."
        if max_items else ""
    )
    if _lanzar_agente("editor", instrucciones, origen).estado != "ok":
        raise typer.Exit(1)


@app.command("explorar")
def cmd_explorar(origen: OpcionOrigen = "manual") -> None:
    """Explorador: Fuentes sin feed y fuente primaria de las Historias más urgentes."""
    if _lanzar_agente("explorador", "", origen).estado != "ok":
        raise typer.Exit(1)


@app.command("diario")
def cmd_diario(origen: OpcionOrigen = "manual") -> None:
    """La Ejecución diaria completa: recoger → editar → explorar → editar lo que traiga el Explorador."""
    _validar_origen(origen)
    cmd_recoger(fuente=None, origen=origen)
    editar = _lanzar_agente("editor", "", origen)
    explorar = _lanzar_agente("explorador", "", origen)
    conn = _conn()
    try:
        quedan = historias.pendientes(conn, limite=1)["items_pendientes_total"]
    finally:
        conn.close()
    if quedan:
        _lanzar_agente("editor", "Solo quedan los Items que acaba de añadir el Explorador.", origen)
    bombas = []
    conn = _conn()
    try:
        bombas = historias.listar(conn, desde=db.ahora() - timedelta(days=1), solo_bombas=True)
    finally:
        conn.close()
    for b in bombas:
        typer.secho(f"💥 Historia bomba #{b['id']}: {b['titulo']}", fg=typer.colors.MAGENTA, bold=True)
    if editar.estado != "ok" or explorar.estado != "ok":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
