"""Horarios con launchd (ADR-0002): cada tarea es un LaunchAgent que llama a `tn programado <tarea>`.

launchd ejecuta al despertar una tarea cuya hora pasó con el Mac dormido (no si estaba
apagado). Las tareas no hacen nada por su cuenta: solo llaman a la CLI (ADR-0004).
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tn import config

PREFIJO = "com.jpdev.tech-news"
CARPETA = Path.home() / "Library" / "LaunchAgents"

# launchd: Weekday 0 = domingo, 1 = lunes … 4 = jueves, 5 = viernes.
TAREAS: dict[str, dict] = {
    "diario": {"cuando": {"Hour": 16, "Minute": 0}, "que": "Recoger → editar → explorar → bomba → copia de seguridad"},
    "resumen": {"cuando": {"Weekday": 4, "Hour": 22, "Minute": 0}, "que": "Resumen semanal + ideas de Vídeo didáctico"},
    "linkedin": {"cuando": {"Weekday": 0, "Hour": 22, "Minute": 0}, "que": "3 Posts de LinkedIn"},
    "perfil": {"cuando": {"Weekday": 0, "Hour": 22, "Minute": 45}, "que": "Propuesta de cambios al Perfil editorial"},
    "aviso-paquete": {"cuando": {"Weekday": 5, "Hour": 8, "Minute": 0}, "que": "Aviso: paquete semanal listo"},
    "aviso-posts": {"cuando": {"Weekday": 1, "Hour": 8, "Minute": 0}, "que": "Aviso: posts de LinkedIn listos"},
}
DIAS = {0: "domingo", 1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado"}


def cuando_legible(c: dict) -> str:
    hora = f"{c['Hour']:02d}:{c.get('Minute', 0):02d}"
    return f"{DIAS[c['Weekday']]} {hora}" if "Weekday" in c else f"a diario {hora}"


def etiqueta(tarea: str) -> str:
    return f"{PREFIJO}.{tarea}"


def ruta_plist(tarea: str) -> Path:
    return CARPETA / f"{etiqueta(tarea)}.plist"


def _path_entorno() -> str:
    """PATH para launchd, que arranca con uno mínimo: uv y claude tienen que encontrarse."""
    carpetas = []
    for programa in ("uv", "claude"):
        if ruta := shutil.which(programa):
            carpetas.append(str(Path(ruta).parent))
    carpetas += [str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    return ":".join(dict.fromkeys(carpetas))


def generar_plist(tarea: str) -> dict:
    uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
    registros = config.ruta_db().parent / "registros"
    return {
        "Label": etiqueta(tarea),
        "ProgramArguments": [uv, "run", "--project", str(config.raiz()), "tn", "programado", tarea],
        "WorkingDirectory": str(config.raiz()),
        "EnvironmentVariables": {"PATH": _path_entorno(), "HOME": str(Path.home())},
        "StartCalendarInterval": TAREAS[tarea]["cuando"],
        "StandardOutPath": str(registros / f"horario-{tarea}.log"),
        "StandardErrorPath": str(registros / f"horario-{tarea}.log"),
        "ProcessType": "Background",
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def _dominio() -> str:
    return f"gui/{os.getuid()}"


def instalar() -> list[str]:
    CARPETA.mkdir(parents=True, exist_ok=True)
    (config.ruta_db().parent / "registros").mkdir(parents=True, exist_ok=True)
    hechas = []
    for tarea in TAREAS:
        ruta = ruta_plist(tarea)
        _launchctl("bootout", f"{_dominio()}/{etiqueta(tarea)}")  # si ya estaba, se recarga
        with ruta.open("wb") as f:
            plistlib.dump(generar_plist(tarea), f)
        r = _launchctl("bootstrap", _dominio(), str(ruta))
        if r.returncode != 0:
            raise RuntimeError(f"launchctl no cargó {tarea}: {r.stderr.strip() or r.stdout.strip()}")
        hechas.append(tarea)
    return hechas


def desinstalar() -> list[str]:
    quitadas = []
    for tarea in TAREAS:
        ruta = ruta_plist(tarea)
        _launchctl("bootout", f"{_dominio()}/{etiqueta(tarea)}")
        if ruta.exists():
            ruta.unlink()
            quitadas.append(tarea)
    return quitadas


@dataclass
class EstadoTarea:
    tarea: str
    cuando: str
    que: str
    instalada: bool
    cargada: bool
    ultimo_codigo: str | None


def estado() -> list[EstadoTarea]:
    res = []
    for tarea, t in TAREAS.items():
        r = _launchctl("print", f"{_dominio()}/{etiqueta(tarea)}")
        codigo = None
        if r.returncode == 0:
            for linea in r.stdout.splitlines():
                if "last exit code" in linea:
                    codigo = linea.split("=", 1)[1].strip()
        res.append(EstadoTarea(tarea, cuando_legible(t["cuando"]), t["que"], ruta_plist(tarea).exists(),
                               r.returncode == 0, codigo))
    return res


def lanzar_ahora(tarea: str) -> None:
    r = _launchctl("kickstart", f"{_dominio()}/{etiqueta(tarea)}")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "launchctl kickstart falló (¿está instalada?)")
