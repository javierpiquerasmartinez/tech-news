"""CLI `tn`: el único punto de entrada al sistema (ADR-0004)."""

from __future__ import annotations

from typing import Annotated

import typer

from tn import config, db
from tn.fuentes import cargar_fuentes
from tn.http import Http
from tn.modelo import ORIGENES
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
        typer.echo(f"{'#':>4}  {'inicio (UTC)':<20} {'origen':<8} {'comando':<18} {'estado':<12} {'nuevos':>6}  errores")
        for e in filas:
            typer.echo(
                f"{e['id']:>4}  {e['inicio'][:19]:<20} {e['origen']:<8} {e['comando'][:18]:<18} "
                f"{e['estado']:<12} {e['nuevos']:>6}  {e['errores'] or 0}/{e['fuentes']}"
            )
    finally:
        conn.close()


@app.command("fuentes")
def cmd_fuentes() -> None:
    """Catálogo de Fuentes (fuentes.yaml) y quién recoge cada una."""
    for f in cargar_fuentes(config.ruta_fuentes()):
        quien = "Explorador" if f.tipo == "explorador" else "Recolector"
        estado = "" if f.activa else " (pausada)"
        typer.echo(f"{f.grupo:<12} {f.id:<22} {f.tipo:<10} {quien}{estado}")


if __name__ == "__main__":
    app()
