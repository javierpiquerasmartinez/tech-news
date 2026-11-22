"""CLI `tn`: el único punto de entrada al sistema (ADR-0004)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from tn import agentes, avisos, capcut, config, db, historias, horarios, montaje, perfil, propuestas, respaldo
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


@app.callback()
def _al_arrancar() -> None:
    config.cargar_env()

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
    # Un borrador ya aplicado se borra para que no se reaplique por error.
    if fichero and fichero != "-":
        ruta = (config.raiz() / fichero).resolve()
        if (config.ruta_db().parent / "borradores").resolve() in ruta.parents:
            ruta.unlink(missing_ok=True)


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
    # Tope por día para no agotar la cuota de Pro: lo que sobre se edita al día siguiente.
    tope = int(os.environ.get("TN_MAX_ITEMS_DIARIO", "200"))
    editar = _lanzar_agente(
        "editor",
        f"Esta vez procesa como máximo {tope} Items en total (pide lotes con "
        f"`uv run tn editor pendientes` hasta llegar a {tope}) y termina; el resto queda para mañana.",
        origen,
    )
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
    # Historia bomba → Vídeo bomba + post exprés sin esperar al calendario (docs/arnes.md §4.3).
    conn = _conn()
    try:
        sin_propuesta = propuestas.bombas_sin_propuesta(conn)
    finally:
        conn.close()
    for hid in sin_propuesta:
        _lanzar_agente("redactor", f"Formato: bomba. Historia: {hid}.", origen)
        _avisar_bomba(hid)
    if editar.estado != "ok" or explorar.estado != "ok":
        raise typer.Exit(1)


# --- Avisos ------------------------------------------------------------------------


def _avisar(titulo: str, texto: str) -> None:
    r = avisos.avisar(titulo, texto)
    if r.telegram:
        typer.echo(f"Aviso enviado por Telegram: {titulo}")
    else:
        typer.secho(f"Aviso sin Telegram ({r.detalle}): {titulo}", fg=typer.colors.YELLOW)


def _seccion(cuerpo: str, encabezado: str) -> str:
    """El texto de la sección `## <encabezado>…` de un Markdown, hasta la siguiente `## `."""
    m = re.search(rf"^## {re.escape(encabezado)}.*?$\n(.*?)(?=^## |\Z)", cuerpo, re.M | re.S)
    return m.group(1).strip() if m else ""


def _avisar_bomba(hid: int) -> None:
    conn = _conn()
    try:
        h, items = historias.ver(conn, hid)
    finally:
        conn.close()
    bomba = next((p for p in propuestas.listar(propuestas.semana_por_defecto())
                  if p.meta.get("formato") == "bomba" and hid in p.meta.get("historias", [])), None)
    texto = f"{h['titulo']}\n\n{h['resumen'] or ''}\n\nPor qué: {h['just_urgencia']}"
    if bomba:
        texto += f"\n\n— Short —\n{_seccion(bomba.cuerpo, 'Short')}\n\nPropuesta completa: {bomba.relativa}"
    texto += "\n\nFuente: " + (items[0]["url"] if items else "—")
    _avisar("💥 Historia bomba", texto)


avisos_app = typer.Typer(help="Configurar y probar los avisos (Telegram y macOS).", no_args_is_help=True)
app.add_typer(avisos_app, name="avisos")


@avisos_app.command("vincular")
def cmd_avisos_vincular() -> None:
    """Guarda en .env el chat de Telegram al que avisar (escríbele antes cualquier cosa a tu bot)."""
    token = os.environ.get("TN_TELEGRAM_TOKEN")
    if not token:
        _fallar(RuntimeError("Falta TN_TELEGRAM_TOKEN en .env (créalo con @BotFather y pégalo ahí)"))
    try:
        chat = avisos.buscar_chat(token)
    except Exception as e:  # noqa: BLE001
        _fallar(RuntimeError(f"Telegram no respondió bien ({type(e).__name__}). ¿El token es correcto?"))
    if not chat:
        _fallar(RuntimeError("El bot no tiene mensajes: abre Telegram, escríbele cualquier cosa y repite"))
    config.guardar_en_env("TN_TELEGRAM_CHAT", chat[0])
    typer.echo(f"Vinculado al chat de {chat[1] or chat[0]}. Prueba con `uv run tn avisos prueba`.")


@avisos_app.command("prueba")
def cmd_avisos_prueba() -> None:
    """Envía un aviso de prueba."""
    _avisar("✅ tech-news", "Los avisos funcionan. Aquí te llegarán las Historias bomba y los paquetes de la semana.")


avisar_app = typer.Typer(help="Avisos de la semana (los lanza el horario).", no_args_is_help=True)
app.add_typer(avisar_app, name="avisar")


@avisar_app.command("paquete")
def cmd_avisar_paquete() -> None:
    """Viernes: el Resumen semanal y las ideas didácticas están listos."""
    # La semana más reciente con Resumen (el viernes a las 08:00 ya ha empezado la semana nueva).
    todas = [p for p in propuestas.listar() if p.meta.get("formato") in ("resumen", "ideas-didacticas")]
    ultima = max((p.meta.get("semana_editorial", "") for p in todas), default=None)
    lista = [p for p in todas if p.meta.get("semana_editorial") == ultima]
    if not lista:
        _avisar("📦 Paquete semanal", "No hay Resumen semanal: el Redactor no lo escribió. Lánzalo con `uv run tn redactar --resumen`.")
        return
    texto = "\n".join(f"• {propuestas.FORMATOS[p.meta['formato']]}: {p.meta.get('titulo')}" for p in lista)
    resumen = next((p for p in lista if p.meta.get("formato") == "resumen"), None)
    if resumen:
        texto += "\n\n— Gancho —\n" + _seccion(resumen.cuerpo, "Gancho")
    texto += "\n\nRevísalo en `uv run tn ui` → Propuestas."
    _avisar("📦 Paquete semanal listo", texto)


@avisar_app.command("post")
def cmd_avisar_post() -> None:
    """El post de LinkedIn escrito hoy, para publicarlo mañana por la mañana."""
    hoy = db.ahora().date().isoformat()
    posts = [p for p in propuestas.listar(propuestas.semana_por_defecto())
             if p.meta.get("formato") == "linkedin" and str(p.meta.get("creada", "")).startswith(hoy)]
    if not posts:
        _avisar("✍️ Post de LinkedIn", "Hoy no se ha escrito post. Lánzalo con `uv run tn redactar --post`.")
        return
    for p in posts:
        enlace = p.meta.get("enlace_primer_comentario")
        _avisar(f"✍️ Post para mañana · {p.meta.get('titulo')}",
                p.cuerpo.strip() + (f"\n\n🔗 Primer comentario: {enlace}" if enlace else ""))


@avisar_app.command("posts")
def cmd_avisar_posts() -> None:
    """Lunes: los 3 Posts de LinkedIn, cada uno en su mensaje para copiarlo desde el móvil."""
    posts = [p for p in propuestas.listar(propuestas.semana_por_defecto()) if p.meta.get("formato") == "linkedin"
             and p.estado in ("propuesta", "aprobada")]
    if not posts:
        _avisar("✍️ Posts de LinkedIn", "No hay posts esta semana. Lánzalos con `uv run tn redactar --linkedin`.")
    else:
        _avisar("✍️ Posts de LinkedIn listos", f"{len(posts)} posts para martes, miércoles y jueves. Te los mando uno a uno.")
        for n, p in enumerate(posts, start=1):
            enlace = p.meta.get("enlace_primer_comentario")
            avisos.enviar_telegram(f"Post {n} · {p.meta.get('titulo')}\n\n{p.cuerpo.strip()}"
                                   + (f"\n\n🔗 Primer comentario: {enlace}" if enlace else ""))
    if perfil.hay_propuesta():
        _avisar("🧭 Perfil editorial", "Hay una propuesta de cambios al Perfil editorial: `uv run tn perfil diff`.")


# --- Copia de seguridad --------------------------------------------------------------


@app.command("respaldar")
def cmd_respaldar(
    destino: Annotated[str | None, typer.Option(help="Carpeta destino (por defecto TN_RESPALDOS o ~/Documents/tech-news-respaldos).")] = None,
) -> None:
    """Copia la SQLite y semanas/ (lo que no está en git) a un .tar.gz; conserva las 14 últimas."""
    archivo = respaldo.respaldar(Path(destino).expanduser() if destino else None)
    typer.echo(f"Copia de seguridad: {archivo}")


# --- Perfil editorial -----------------------------------------------------------------

perfil_app = typer.Typer(help="Revisar el Perfil editorial a partir de tus correcciones.", no_args_is_help=True)
app.add_typer(perfil_app, name="perfil")


@perfil_app.command("decisiones")
def cmd_perfil_decisiones() -> None:
    """JSON con tus correcciones desde la última revisión (lo usa el agente)."""
    conn = _conn()
    try:
        _json(perfil.decisiones_pendientes(conn), compacto=True)
    finally:
        conn.close()


@perfil_app.command("revisar")
def cmd_perfil_revisar(origen: OpcionOrigen = "manual") -> None:
    """Propone cambios al Perfil editorial si tus correcciones muestran un patrón. No cambia nada solo."""
    conn = _conn()
    try:
        n = len(perfil.decisiones_pendientes(conn))
    finally:
        conn.close()
    if perfil.hay_propuesta():
        typer.echo("Ya hay una propuesta pendiente: `tn perfil diff`, `tn perfil aceptar` o `tn perfil rechazar`.")
        return
    if n < 3:
        typer.echo(f"Solo hay {n} correcciones desde la última revisión: no basta para ver un patrón.")
        return
    _lanzar_agente("perfil", "", origen)
    if perfil.hay_propuesta():
        typer.echo("Propuesta lista: `uv run tn perfil diff`.")
        _avisar("🧭 Perfil editorial", "Hay una propuesta de cambios al Perfil editorial a partir de tus correcciones: `uv run tn perfil diff`.")


@perfil_app.command("diff")
def cmd_perfil_diff() -> None:
    """Muestra los cambios propuestos."""
    try:
        typer.echo(perfil.diff())
    except perfil.SinPropuesta as e:
        _fallar(e)


@perfil_app.command("aceptar")
def cmd_perfil_aceptar() -> None:
    """Aplica la propuesta a perfil-editorial.md (guarda una copia del anterior en data/)."""
    conn = _conn()
    try:
        perfil.aceptar(conn)
    except perfil.SinPropuesta as e:
        _fallar(e)
    finally:
        conn.close()
    typer.echo("perfil-editorial.md actualizado. Recuerda hacer commit del cambio.")


@perfil_app.command("rechazar")
def cmd_perfil_rechazar() -> None:
    """Descarta la propuesta."""
    conn = _conn()
    try:
        perfil.rechazar(conn)
    except perfil.SinPropuesta as e:
        _fallar(e)
    finally:
        conn.close()
    typer.echo("Propuesta descartada.")


# --- Horarios ---------------------------------------------------------------------------

horarios_app = typer.Typer(help="Instalar y ver las tareas programadas (launchd).", no_args_is_help=True)
app.add_typer(horarios_app, name="horarios")


@horarios_app.command("estado")
def cmd_horarios_estado() -> None:
    """Qué tareas hay, cuándo corren y si están cargadas."""
    for t in horarios.estado():
        marca = "●" if t.cargada else ("○" if t.instalada else "·")
        codigo = f" · último código {t.ultimo_codigo}" if t.ultimo_codigo else ""
        typer.echo(f"{marca} {t.tarea:<14} {t.cuando:<16} {t.que}{codigo}")
    typer.echo("● cargada · ○ instalada sin cargar · · sin instalar")


@horarios_app.command("instalar")
def cmd_horarios_instalar() -> None:
    """Instala (o reinstala) las tareas en ~/Library/LaunchAgents y las carga."""
    try:
        hechas = horarios.instalar()
    except RuntimeError as e:
        _fallar(e)
    typer.echo(f"Instaladas {len(hechas)} tareas. Míralas con `uv run tn horarios estado`.")


@horarios_app.command("desinstalar")
def cmd_horarios_desinstalar() -> None:
    """Quita todas las tareas programadas."""
    typer.echo(f"Quitadas: {', '.join(horarios.desinstalar()) or 'ninguna'}")


@horarios_app.command("lanzar")
def cmd_horarios_lanzar(tarea: str) -> None:
    """Ejecuta ya una tarea instalada, a través de launchd (para comprobar que funciona)."""
    if tarea not in horarios.TAREAS:
        raise typer.BadParameter(f"Tareas: {', '.join(horarios.TAREAS)}")
    try:
        horarios.lanzar_ahora(tarea)
    except RuntimeError as e:
        _fallar(e)
    typer.echo(f"Lanzada. Salida en data/registros/horario-{tarea}.log")


@app.command("programado", hidden=True)
def cmd_programado(tarea: str) -> None:
    """Punto de entrada de launchd: espera a que no haya nada en curso y ejecuta la tarea."""
    if tarea not in horarios.TAREAS:
        raise typer.BadParameter(f"Tareas: {', '.join(horarios.TAREAS)}")
    typer.echo(f"=== {db.ahora().isoformat(timespec='seconds')} · {tarea} ===")
    for _ in range(90):  # hasta 90 min: p. ej. al despertar coinciden diario y resumen
        conn = _conn()
        try:
            ocupado = db.ejecuciones_en_curso(conn)
        finally:
            conn.close()
        if not ocupado:
            break
        time.sleep(60)
    acciones = {
        "diario": lambda: cmd_diario(origen="horario"),
        "resumen": lambda: cmd_redactar(resumen=True, didactico=True, linkedin=False, post=False, semana=None, origen="horario"),
        "post-diario": lambda: (cmd_redactar(resumen=False, didactico=False, linkedin=False, post=True,
                                             semana=None, origen="horario"), cmd_avisar_post()),
        "perfil": lambda: cmd_perfil_revisar(origen="horario"),
        "aviso-paquete": cmd_avisar_paquete,
    }
    fallo = None
    try:
        acciones[tarea]()
    except (typer.Exit, SystemExit) as e:
        if getattr(e, "exit_code", getattr(e, "code", 0)) not in (0, None):
            fallo = "terminó con errores"
    except Exception as e:  # noqa: BLE001
        fallo = f"{type(e).__name__}: {e}"
    if tarea == "diario":
        try:
            cmd_respaldar(destino=None)
        except Exception as e:  # noqa: BLE001
            fallo = (fallo + " · " if fallo else "") + f"copia de seguridad: {e}"
    if fallo:
        _avisar(f"⚠️ tech-news: la tarea {tarea} falló", f"{fallo}\n\nMira `uv run tn ejecuciones` o data/registros/horario-{tarea}.log")
        raise typer.Exit(1)


# --- Montador (fase 2) -------------------------------------------------------------------

montaje_app = typer.Typer(help="Preparar el Montador: requisitos y plantillas de CapCut.", no_args_is_help=True)
app.add_typer(montaje_app, name="montaje")


def _requisitos_montador() -> bool:
    todo = True
    for r in capcut.requisitos():
        typer.secho(f"{'✓' if r.ok else '✗'} {r.texto}", fg=typer.colors.GREEN if r.ok else typer.colors.RED)
        if not r.ok:
            typer.echo(f"    → {r.arreglo}")
            todo = False
    return todo


@montaje_app.command("requisitos")
def cmd_montaje_requisitos() -> None:
    """Comprueba que CapCut, capcut-kit y las herramientas del Montador están listos."""
    if not _requisitos_montador():
        raise typer.Exit(1)


@montaje_app.command("plantillas")
def cmd_montaje_plantillas(
    desde: Annotated[str, typer.Option(help="Nombre del proyecto de CapCut que tiene al menos un texto.")],
) -> None:
    """Saca de un proyecto real de CapCut las plantillas de texto que necesita capcut-kit."""
    try:
        for ruta in capcut.extraer_plantillas(desde):
            typer.echo(f"Escrita {ruta}")
    except capcut.CapCutNoDisponible as e:
        _fallar(e)


@montaje_app.command("doctor")
def cmd_montaje_doctor() -> None:
    """Comprobación de solo lectura de capcut-kit contra tu CapCut (no toca proyectos)."""
    try:
        r = capcut.ejecutar("doctor", timeout=120)
    except capcut.CapCutNoDisponible as e:
        _fallar(e)
    typer.echo(r.stdout + r.stderr)
    if r.returncode != 0:
        raise typer.Exit(1)


@app.command("montar")
def cmd_montar(
    semana: Annotated[str, typer.Option(help="Semana editorial del guion (cualquier día, AAAA-MM-DD).")],
    hasta: Annotated[str, typer.Option(help=f"Último paso: {' | '.join(montaje.PASOS)}.")] = "transcribir",
    rehacer: Annotated[str | None, typer.Option(help="Rehacer desde este paso aunque ya esté hecho.")] = None,
    origen: OpcionOrigen = "manual",
) -> None:
    """Montador: de tu Grabación a un Montaje de CapCut (por ahora: preparar y transcribir)."""
    _validar_origen(origen)
    inicio = _semana(semana)
    conn = _conn()
    eid = db.abrir_ejecucion(conn, f"montar {inicio.isoformat()} --hasta {hasta}", origen, db.ahora())
    try:
        res = montaje.montar(inicio, hasta=hasta, rehacer=rehacer,
                             al_avanzar=lambda p: typer.echo(f"→ {p}…"))
    except montaje.MontajeInvalido as e:
        db.cerrar_ejecucion(conn, eid, "fallida", resultado=str(e))
        conn.close()
        _fallar(e)
    db.cerrar_ejecucion(conn, eid, "ok", resultado=json.dumps(res, ensure_ascii=False))
    conn.close()
    for paso, detalle in res.items():
        typer.echo(f"✓ {paso}: {detalle}")
    typer.echo(f"Carpeta del Montaje: {montaje.carpeta(inicio)}")


@app.command("diagnostico")
def cmd_diagnostico(
    con_claude: Annotated[bool, typer.Option("--claude", help="Comprueba también que claude responde (gasta muy poca cuota).")] = False,
) -> None:
    """Comprueba que todo lo que necesitan los horarios está en su sitio."""
    def linea(ok: bool, texto: str) -> None:
        typer.secho(f"{'✓' if ok else '✗'} {texto}", fg=typer.colors.GREEN if ok else typer.colors.RED)

    linea(bool(shutil.which("uv")), f"uv: {shutil.which('uv') or 'no encontrado'}")
    linea(bool(shutil.which("claude")), f"claude: {shutil.which('claude') or 'no encontrado'}")
    if con_claude and shutil.which("claude"):
        r = subprocess.run(["claude", "-p", "Responde solo: ok", "--model", "haiku", "--output-format", "json"],
                           capture_output=True, text=True, timeout=120, cwd=config.raiz())
        try:
            sal = json.loads(r.stdout)
            linea(not sal.get("is_error"), f"claude responde: {str(sal.get('result'))[:80]}")
        except json.JSONDecodeError:
            linea(False, f"claude no responde bien: {(r.stderr or r.stdout)[:120]}")
    tok, chat = os.environ.get("TN_TELEGRAM_TOKEN"), os.environ.get("TN_TELEGRAM_CHAT")
    linea(bool(tok and chat), "Telegram configurado" if tok and chat else
          ("Telegram: falta vincular el chat (`tn avisos vincular`)" if tok else "Telegram: falta TN_TELEGRAM_TOKEN en .env"))
    cargadas = sum(t.cargada for t in horarios.estado())
    linea(cargadas == len(horarios.TAREAS), f"Horarios cargados: {cargadas}/{len(horarios.TAREAS)}")
    faltan = [r.texto for r in capcut.requisitos() if not r.ok]
    linea(not faltan, "Montador listo" if not faltan else f"Montador: falta {', '.join(faltan)} (`tn montaje requisitos`)")
    copias = sorted(config.ruta_respaldos().glob("tech-news-*.tar.gz"))
    linea(bool(copias), f"Última copia de seguridad: {copias[-1].name if copias else 'ninguna'} ({config.ruta_respaldos()})")


# --- Redactor y Propuestas -------------------------------------------------------

redactor_app = typer.Typer(help="Entrada y salida del Redactor: contexto y entrega de Propuestas.", no_args_is_help=True)
app.add_typer(redactor_app, name="redactor")

OpcionSemana = Annotated[str | None, typer.Option(help="Cualquier día de la Semana editorial (AAAA-MM-DD). Por defecto, la actual.")]


def _semana(texto: str | None):
    if not texto:
        return None
    try:
        return propuestas.inicio_semana(date.fromisoformat(texto))
    except ValueError:
        raise typer.BadParameter("--semana debe ser AAAA-MM-DD") from None


@redactor_app.command("contexto")
def cmd_redactor_contexto(
    formato: Annotated[str, typer.Option(help=f"{' | '.join(propuestas.FORMATOS)}")],
    historia: Annotated[int | None, typer.Option(help="Para didactico y bomba.")] = None,
    semana: OpcionSemana = None,
    horas: Annotated[int | None, typer.Option(help="Solo Historias con noticias de las últimas N horas (post diario).")] = None,
) -> None:
    """JSON con las Historias candidatas y las Propuestas ya escritas esta semana."""
    conn = _conn()
    try:
        _json(propuestas.contexto(conn, formato, semana=_semana(semana), historia_id=historia, horas=horas), compacto=True)
    except (propuestas.PropuestaInvalida, historias.AccionInvalida) as e:
        _fallar(e)
    finally:
        conn.close()


@redactor_app.command("guardar")
def cmd_redactor_guardar(
    formato: Annotated[str, typer.Option()],
    titulo: Annotated[str, typer.Option()],
    historias_: Annotated[str, typer.Option("--historias", help="Ids separados por comas.")],
    contenido: Annotated[str | None, typer.Option(help="Markdown de la Propuesta.")] = None,
    desde: Annotated[str | None, typer.Option(help="Leer el Markdown de un borrador en data/borradores/ (se borra al guardar).")] = None,
    enlace: Annotated[str | None, typer.Option(help="LinkedIn: enlace para el primer comentario.")] = None,
    semana: OpcionSemana = None,
) -> None:
    """Guarda una Propuesta en semanas/<viernes>/ con estado `propuesta`."""
    try:
        ids = [int(x) for x in historias_.split(",") if x.strip()]
    except ValueError:
        _fallar(propuestas.PropuestaInvalida("--historias debe ser una lista de números separados por comas"))
    borrador = None
    if desde:
        base = (config.ruta_db().parent / "borradores").resolve()
        borrador = (config.raiz() / desde).resolve()
        if base not in borrador.parents or not borrador.is_file():
            _fallar(propuestas.PropuestaInvalida(f"El borrador debe ser un fichero dentro de data/borradores/ ({desde})"))
        contenido = borrador.read_text(encoding="utf-8")
    if not contenido:
        _fallar(propuestas.PropuestaInvalida("Indica --desde (borrador) o --contenido"))
    conn = _conn()
    try:
        p = propuestas.guardar(conn, formato, titulo, contenido, ids, semana=_semana(semana), enlace=enlace)
    except propuestas.PropuestaInvalida as e:
        _fallar(e)
    finally:
        conn.close()
    if borrador:
        borrador.unlink()
    typer.echo(f"Guardada: {p.relativa}")


def _redactar(formato: str, instrucciones: str, origen: str) -> None:
    if _lanzar_agente("redactor", f"Formato: {formato}. {instrucciones}".strip(), origen).estado != "ok":
        raise typer.Exit(1)


@app.command("redactar")
def cmd_redactar(
    resumen: Annotated[bool, typer.Option("--resumen", help="Guion del Resumen semanal.")] = False,
    linkedin: Annotated[bool, typer.Option("--linkedin", help="3 Posts de LinkedIn de la semana.")] = False,
    post: Annotated[bool, typer.Option("--post", help="El post de LinkedIn del día: lo más fuerte de las últimas 48 h.")] = False,
    didactico: Annotated[bool, typer.Option("--didactico", help="3 ideas de Vídeo didáctico.")] = False,
    semana: OpcionSemana = None,
    origen: OpcionOrigen = "manual",
) -> None:
    """Redactor: escribe las Propuestas de la Semana editorial."""
    formatos = [f for f, si in (("resumen", resumen), ("ideas-didacticas", didactico), ("linkedin", linkedin)) if si]
    if not formatos and not post:
        raise typer.BadParameter("Indica --resumen, --post, --linkedin y/o --didactico")
    extra = f"Semana editorial: la que contiene {semana} (pasa --semana {semana} a contexto y guardar)." if semana else ""
    for f in formatos:
        _redactar(f, extra, origen)
    if post:
        _redactar("linkedin", "Post diario: escribe UN solo post. Pide el contexto con "
                  "`uv run tn redactor contexto --formato linkedin --horas 48`.", origen)


propuesta_app = typer.Typer(help="Pedir, ver y aprobar Propuestas.", no_args_is_help=True)
app.add_typer(propuesta_app, name="propuesta")


@propuesta_app.command("pedir")
def cmd_propuesta_pedir(
    historia: int,
    formato: Annotated[str, typer.Option(help="linkedin | bomba | didactico")],
    origen: OpcionOrigen = "manual",
) -> None:
    """Propuesta fuera de calendario para una Historia concreta."""
    if formato not in ("linkedin", "bomba", "didactico"):
        raise typer.BadParameter("formato debe ser linkedin, bomba o didactico")
    if formato == "linkedin":
        _redactar("linkedin", f"Esta vez escribe UN solo post, sobre la Historia {historia}.", origen)
    else:
        _redactar(formato, f"Historia: {historia}.", origen)


@app.command("propuestas")
def cmd_propuestas(
    semana: OpcionSemana = None,
    todas: Annotated[bool, typer.Option("--todas", help="Todas las semanas.")] = False,
) -> None:
    """Propuestas de la Semana editorial con su estado."""
    lista = propuestas.listar(None if todas else (_semana(semana) or propuestas.semana_por_defecto()))
    if not lista:
        typer.echo("No hay Propuestas. Lanza `tn redactar --resumen --linkedin --didactico`.")
        return
    for p in lista:
        hist = ",".join(str(h) for h in p.meta.get("historias", []))
        typer.echo(f"{p.estado:<11} {propuestas.FORMATOS.get(p.meta.get('formato'), '?'):<26} {p.meta.get('titulo', '')}  [#{hist}]\n            {p.relativa}")


@propuesta_app.command("ver")
def cmd_propuesta_ver(fichero: str) -> None:
    """Muestra una Propuesta."""
    try:
        typer.echo(propuestas.resolver(fichero).read_text(encoding="utf-8"))
    except propuestas.PropuestaInvalida as e:
        _fallar(e)


@propuesta_app.command("estado")
def cmd_propuesta_estado(
    fichero: str,
    estado: Annotated[str, typer.Argument(help="propuesta | aprobada | descartada | publicada")],
    origen: OpcionOrigenAccion = "manual",
) -> None:
    """Aprueba, descarta o marca como publicada una Propuesta."""
    conn = _conn()
    try:
        p = propuestas.cambiar_estado(conn, propuestas.resolver(fichero), estado, _validar_origen(origen))
    except propuestas.PropuestaInvalida as e:
        _fallar(e)
    finally:
        conn.close()
    typer.echo(f"{p.relativa}: {p.estado}")


@app.command("ui")
def cmd_ui(
    puerto: Annotated[int, typer.Option(help="Puerto local.")] = 8765,
) -> None:
    """Interfaz web local para revisar Historias, Fuentes y Ejecuciones (solo en este Mac)."""
    import uvicorn

    typer.echo(f"tech-news en http://127.0.0.1:{puerto}  (Ctrl+C para parar)")
    uvicorn.run("tn.web.app:app", host="127.0.0.1", port=puerto, log_level="warning")


if __name__ == "__main__":
    app()
