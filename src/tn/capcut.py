"""Único punto de contacto con CapCut (ADR-0005).

capcut-kit vive fuera del repo (no tiene licencia) en `TN_CAPCUT_KIT`, por defecto
`~/git/jpdev/capcut-kit`, fijado a `COMMIT_FIJADO`. Todo lo demás de `tn` habla con
CapCut a través de este módulo, así que cambiar de herramienta solo toca este fichero.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

COMMIT_FIJADO = "78944f7"
REPO_KIT = "https://github.com/matt-j-penny/capcut-kit.git"
APP = Path("/Applications/CapCut.app")
PLANTILLAS = ("text-material.json", "text-segment.json", "text-ref-material_animations.json")


class CapCutNoDisponible(RuntimeError):
    pass


def ruta_kit() -> Path:
    return Path(os.environ.get("TN_CAPCUT_KIT", "~/git/jpdev/capcut-kit")).expanduser()


def carpeta_proyectos() -> Path:
    if env := os.environ.get("CAPCUT_DRAFTS"):
        return Path(env).expanduser()
    return Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"


@dataclass
class Requisito:
    ok: bool
    texto: str
    arreglo: str = ""


def requisitos() -> list[Requisito]:
    kit = ruta_kit()
    res = [Requisito(APP.exists(), "CapCut instalado", "Instala CapCut desde capcut.com")]
    res.append(Requisito(carpeta_proyectos().is_dir(), f"Proyectos de CapCut en {carpeta_proyectos()}",
                         "Abre CapCut, crea un proyecto y guárdalo"))
    commit = ""
    if (kit / ".git").is_dir():
        r = subprocess.run(["git", "-C", str(kit), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        commit = r.stdout.strip()
    res.append(Requisito(bool(commit), f"capcut-kit en {kit}" + (f" ({commit})" if commit else ""),
                         f"git clone {REPO_KIT} {kit} && git -C {kit} checkout {COMMIT_FIJADO}"))
    if commit:
        res.append(Requisito(commit.startswith(COMMIT_FIJADO[:7]), f"capcut-kit en el commit fijado {COMMIT_FIJADO}",
                             f"git -C {kit} checkout {COMMIT_FIJADO} (o actualiza COMMIT_FIJADO tras probar la versión nueva)"))
    faltan = [p for p in PLANTILLAS if not (kit / "capcut-templates" / p).is_file()]
    res.append(Requisito(not faltan, "Plantillas de texto de CapCut (capcut-templates/)",
                         "uv run tn montaje plantillas --desde <proyecto de CapCut con un texto>"))
    for programa in ("ffmpeg", "ffprobe", "node", "npx", "uv"):
        res.append(Requisito(bool(shutil.which(programa)), programa, f"brew install {programa}"))
    return res


def ejecutar(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    """Llama a `uv run capcut-bridge.py <args>` en el kit."""
    kit = ruta_kit()
    if not (kit / "capcut-bridge.py").is_file():
        raise CapCutNoDisponible(f"No encuentro capcut-bridge.py en {kit}")
    return subprocess.run(["uv", "run", "capcut-bridge.py", *args], cwd=kit, capture_output=True,
                          text=True, timeout=timeout)


def extraer_plantillas(proyecto: str) -> list[Path]:
    """Saca de un proyecto real de CapCut las tres piezas que `add-text`/`graphics` necesitan.

    Toma el primer texto del proyecto: su material, su segmento y la animación que
    referencia. CapCut tiene que haberlo guardado (draft_info.json en disco).
    """
    carpeta = carpeta_proyectos() / proyecto
    fichero = next((carpeta / n for n in ("draft_info.json", "draft_content.json") if (carpeta / n).is_file()), None)
    if not fichero:
        raise CapCutNoDisponible(f"No encuentro el proyecto {proyecto!r} en {carpeta_proyectos()}")
    d = json.loads(fichero.read_text(encoding="utf-8-sig"))
    textos = d.get("materials", {}).get("texts", [])
    pista = next((t for t in d.get("tracks", []) if t.get("type") == "text" and t.get("segments")), None)
    if not textos or not pista:
        raise CapCutNoDisponible(f"El proyecto {proyecto!r} no tiene ningún texto: añade uno y guarda")
    segmento = pista["segments"][0]
    material = next((t for t in textos if t.get("id") == segmento.get("material_id")), textos[0])
    animaciones = {a.get("id"): a for a in d["materials"].get("material_animations", [])}
    animacion = next((animaciones[r] for r in segmento.get("extra_material_refs", []) if r in animaciones), None)
    if animacion is None:
        raise CapCutNoDisponible("El texto no referencia ninguna animación de material; prueba con otro texto")
    destino = ruta_kit() / "capcut-templates"
    destino.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nombre, pieza in zip(PLANTILLAS, (material, segmento, animacion)):
        ruta = destino / nombre
        ruta.write_text(json.dumps(pieza, ensure_ascii=False, indent=1), encoding="utf-8")
        escritos.append(ruta)
    return escritos


def carpeta_trabajos() -> Path:
    """capcut-kit busca cada trabajo en `<padre del kit>/projects/<trabajo>/`."""
    return ruta_kit().parent / "projects"


def preparar_trabajo(trabajo: str, grabacion: Path, tramos: list[dict], fps: float = 30.0) -> Path:
    """Deja el Corte donde `capcut-bridge.py replay` lo espera (INPUT-CONTRACT.md del kit).

    La grabación se enlaza (hardlink) en `raw/`: no ocupa espacio extra y sigue dentro del
    mismo disco que `~/Movies`, que es lo que CapCut puede leer.
    """
    carpeta = carpeta_trabajos() / trabajo
    (carpeta / "transcript").mkdir(parents=True, exist_ok=True)
    (carpeta / "raw").mkdir(parents=True, exist_ok=True)
    destino = carpeta / "raw" / grabacion.name
    if destino.exists():
        destino.unlink()
    try:
        os.link(grabacion, destino)
    except OSError:
        shutil.copy2(grabacion, destino)
    cuts = {"clip": grabacion.name, "fps": fps,
            "segments": [{"clip": grabacion.name, "start": t["inicio"], "end": t["fin"],
                          "note": f"unidades {', '.join(map(str, t['unidades']))}"} for t in tramos]}
    (carpeta / "transcript" / "cuts.json").write_text(json.dumps(cuts, ensure_ascii=False, indent=1))
    return carpeta
