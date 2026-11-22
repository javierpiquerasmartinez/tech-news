"""Lanza los roles que son agentes (skills de Claude Code) en modo headless (ADR-0002).

Cada lanzamiento es una Ejecución: queda registrado quién lo pidió, cuánto consumió y qué
respondió el agente. El agente solo puede usar la CLI `tn` (ADR-0004) y, si su rol lo
necesita, leer la web.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass

from tn import config, db

# Modelo por defecto: con plan Pro, Sonnet rinde de sobra para estas tareas y gasta menos cuota.
MODELO_POR_DEFECTO = "sonnet"
TIEMPO_MAXIMO = 45 * 60

HERRAMIENTAS = {
    "editor": [
        "Bash(uv run tn editor:*)",
        "Bash(uv run tn historias:*)",
        "Bash(uv run tn historia ver:*)",
        "Read(perfil-editorial.md)",
        "WebFetch",
        # Los lotes grandes no pasan como argumento del shell en dontAsk: van en un borrador.
        "Edit(./data/borradores/**)",
    ],
    "explorador": [
        "Bash(uv run tn item anadir:*)",
        "Bash(uv run tn historias:*)",
        "Bash(uv run tn historia ver:*)",
        "Bash(uv run tn fuentes:*)",
        "WebFetch",
        "WebSearch",
    ],
    "redactor": [
        "Bash(uv run tn redactor:*)",
        "Bash(uv run tn historia ver:*)",
        # Los textos largos no pasan bien como argumento del shell: el Redactor escribe un
        # borrador aquí y `tn redactor guardar --desde` lo recoge.
        "Edit(./data/borradores/**)",
        "Read(voz.md)",
        "Read(perfil-editorial.md)",
        "WebFetch",
    ],
    "perfil": [
        "Bash(uv run tn perfil decisiones:*)",
        "Read(perfil-editorial.md)",
        "Edit(./data/borradores/**)",
    ],
}


@dataclass
class ResultadoAgente:
    ejecucion_id: int
    estado: str
    resultado: str
    uso: dict


def _resumir_uso(salida: dict) -> dict:
    u = salida.get("usage") or {}
    return {
        "modelo": next(iter(salida.get("modelUsage") or {}), None),
        "turnos": salida.get("num_turns"),
        "duracion_s": round((salida.get("duration_ms") or 0) / 1000),
        "tokens_entrada": u.get("input_tokens"),
        "tokens_cache_lectura": u.get("cache_read_input_tokens"),
        "tokens_cache_escritura": u.get("cache_creation_input_tokens"),
        "tokens_salida": u.get("output_tokens"),
        "coste_equivalente_usd": salida.get("total_cost_usd"),
    }


def lanzar(conn: sqlite3.Connection, rol: str, instrucciones: str, *, origen: str) -> ResultadoAgente:
    if rol not in HERRAMIENTAS:
        raise ValueError(f"Rol desconocido: {rol}")
    if not shutil.which("claude"):
        raise RuntimeError("No encuentro el comando `claude` (Claude Code) en el PATH")
    ejecucion_id = db.abrir_ejecucion(conn, rol, origen, db.ahora())
    comando = [
        "claude", "-p", f"/{rol} {instrucciones}".strip(),
        "--output-format", "json",
        "--model", os.environ.get("TN_MODELO", MODELO_POR_DEFECTO),
        "--permission-mode", "dontAsk",
        "--allowedTools", *HERRAMIENTAS[rol],
    ]
    entorno = {**os.environ, "TN_EJECUCION": str(ejecucion_id), "TN_ORIGEN": "editor" if rol == "editor" else rol}
    try:
        proc = subprocess.run(
            comando, cwd=config.raiz(), env=entorno, capture_output=True, text=True, timeout=TIEMPO_MAXIMO,
        )
        try:
            salida = json.loads(proc.stdout)
        except json.JSONDecodeError:
            salida = {"is_error": True, "result": (proc.stderr or proc.stdout or "sin salida")[-2000:]}
        error = proc.returncode != 0 or salida.get("is_error")
        estado = "fallida" if error else "ok"
        resultado = str(salida.get("result") or "")
        uso = _resumir_uso(salida)
    except subprocess.TimeoutExpired:
        estado, resultado, uso = "fallida", f"Tiempo agotado ({TIEMPO_MAXIMO // 60} min)", {}
    db.cerrar_ejecucion(conn, ejecucion_id, estado, uso=json.dumps(uso), resultado=resultado[:20000])
    return ResultadoAgente(ejecucion_id=ejecucion_id, estado=estado, resultado=resultado, uso=uso)
