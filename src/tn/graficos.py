"""Gráficos del Montador (docs/arnes.md §9, paso 4; estilo-edicion.md).

Plantillas HTML de `graficos/plantillas/` rellenadas con datos y renderizadas con HyperFrames
a `.mov` con transparencia (ProRes 4444). El plan dice qué Gráfico va, con qué datos y en qué
segundo del Corte. Lo estructural (cabeceras de bloque, sello, pantalla final) lo pone el
código; el agente `montador-graficos` solo decide rótulos, infografías y capturas.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tn import config

HYPERFRAMES = "hyperframes@0.9.81"
DURACIONES = {"cabecera": 2.6, "rotulo": 4.0, "tabla": 8.0, "pasos": 8.0, "captura": 6.0, "sello": 3.0, "final": 15.0}
CAMPOS = {
    "cabecera": ("numero", "titulo"),
    "rotulo": ("valor",),
    "tabla": ("titulo", "columnas", "filas"),
    "pasos": ("titulo", "pasos"),
    "captura": ("url", "fuente"),
    "sello": (),
    "final": (),
}
# Los que ocupan la pantalla: la persona editora pasa al círculo (lo hace el ensamblado).
PANTALLA_COMPLETA = ("tabla", "pasos", "captura", "sello", "final")


class PlanInvalido(ValueError):
    pass


def carpeta_plantillas() -> Path:
    return config.raiz() / "graficos"


# --- Plan --------------------------------------------------------------------------------


def estructurales(corte: dict) -> list[dict]:
    """Cabecera al empezar cada bloque numerado, sello tras el gancho y pantalla final."""
    res = []
    bloques = corte.get("bloques", [])
    for b in bloques:
        m = re.match(r"(\d+)\.\s*(.+)", b["titulo"])
        if m and not b.get("dudoso") and b["fin"] - b["inicio"] >= 4:
            titulo = re.sub(r"\s*\(.*?\)\s*$", "", m.group(2))
            res.append({"tipo": "cabecera", "inicio": round(b["inicio"] + 0.3, 2),
                        "datos": {"numero": m.group(1), "titulo": titulo}})
    gancho = next((b for b in bloques if b["titulo"].lower().startswith("gancho")), None)
    if gancho:
        res.append({"tipo": "sello", "inicio": round(gancho["fin"], 2), "datos": {"lema": "Noticias DEV cada semana"}})
    res.append({"tipo": "final", "inicio": round(corte.get("duracion_corte", 0), 2),
                "datos": {"texto": "Sigue aprendiendo", "lema": "Noticias DEV cada semana"}})
    return res


def validar(plan: list[dict], duracion_corte: float) -> list[dict]:
    """Comprueba tipos, campos y tiempos; completa duración e id. Devuelve el plan ordenado."""
    res = []
    for n, g in enumerate(sorted(plan, key=lambda g: g.get("inicio", 0)), start=1):
        donde = f"Gráfico {n} ({g.get('tipo')})"
        if g.get("tipo") not in DURACIONES:
            raise PlanInvalido(f"{donde}: tipo desconocido; usa {', '.join(DURACIONES)}")
        datos = g.get("datos") or {}
        faltan = [c for c in CAMPOS[g["tipo"]] if not datos.get(c)]
        if faltan:
            raise PlanInvalido(f"{donde}: faltan datos: {', '.join(faltan)}")
        inicio = float(g.get("inicio", -1))
        if not 0 <= inicio <= duracion_corte + 0.01:
            raise PlanInvalido(f"{donde}: inicio {inicio} fuera del Corte (0–{duracion_corte:.1f} s)")
        dur = float(g.get("duracion") or DURACIONES[g["tipo"]])
        if g["tipo"] != "final" and inicio + dur > duracion_corte + 0.01:
            dur = round(duracion_corte - inicio, 2)
        if dur < 1.0:
            raise PlanInvalido(f"{donde}: demasiado corto ({dur:.1f} s)")
        res.append({**g, "id": f"g{n:02d}-{g['tipo']}", "inicio": round(inicio, 2), "duracion": round(dur, 2), "datos": datos})
    return res


def solapes(plan: list[dict]) -> list[str]:
    """La guía pide un Gráfico a la vez: lista los que se pisan (aviso, no error)."""
    avisos = []
    for a, b in zip(plan, plan[1:]):
        if a["tipo"] == "final":
            continue
        if b["inicio"] < a["inicio"] + a["duracion"] - 0.05:
            avisos.append(f"{a['id']} y {b['id']} se solapan")
    return avisos


def contexto_agente(corte: dict, transcripcion_corte: dict, guion: str) -> dict:
    """Lo que necesita el agente para decidir los Gráficos: por bloque, su ventana de tiempo,
    la línea Visual y las Fuentes del guion, y las frases dichas con sus tiempos en el Corte."""
    from tn import corte as corte_mod

    secciones = {b["titulo"]: b["original"] for b in corte_mod.bloques_guion(guion)}
    palabras = transcripcion_corte.get("palabras", [])
    bloques = []
    for b in corte.get("bloques", []):
        texto = secciones.get(b["titulo"], "")
        visual = re.search(r"\*\*Visual:\*\*\s*(.+)", texto)
        fuentes = re.findall(r"https?://[^\s·)]+", re.search(r"\*\*Fuentes:\*\*(.+)", texto).group(1)) \
            if re.search(r"\*\*Fuentes:\*\*(.+)", texto) else []
        # Frases dentro de la ventana del bloque, cortando en la puntuación
        frases, actual = [], []
        for p in palabras:
            if b["inicio"] - 0.01 <= p["inicio"] <= b["fin"] + 0.01:
                actual.append(p)
                if p["palabra"].endswith((".", "?", "!", ":")):
                    frases.append(actual)
                    actual = []
        if actual:
            frases.append(actual)
        bloques.append({
            "titulo": b["titulo"], "inicio": b["inicio"], "fin": b["fin"], "dudoso": b.get("dudoso", False),
            "visual": visual.group(1).strip() if visual else "", "fuentes": fuentes,
            "frases": [{"t": f[0]["inicio"], "texto": " ".join(w["palabra"] for w in f)} for f in frases],
            "puntos_clave": [l.strip("- ").strip() for l in texto.splitlines() if l.strip().startswith("- ")][:6],
        })
    return {"duracion_corte": corte.get("duracion_corte"), "estructurales": estructurales(corte), "bloques": bloques}


# --- Gráficos previstos en el guion (modelo híbrido) -------------------------------------
#
# El Redactor cierra el QUÉ al escribir el guion (sección ~~~graficos de cada bloque, con una
# `ancla`: palabras que se dirán). El Montador solo decide el CUÁNDO buscando el ancla en la
# transcripción. El agente entra solo para lo que no cuadra o para aplicar feedback.

_BLOQUE_GRAFICOS = re.compile(r"^(?:~~~|```)graficos\s*\n(.*?)^(?:~~~|```)\s*$", re.M | re.S)
UMBRAL_ANCLA = 0.6


def previstos_de_guion(guion: str) -> dict[str, list[dict]]:
    """{titulo del bloque: [{tipo, ancla, datos}]} leído de las secciones ~~~graficos del guion."""
    import yaml

    from tn import corte as corte_mod

    res = {}
    for b in corte_mod.bloques_guion(guion):
        lista = []
        for m in _BLOQUE_GRAFICOS.finditer(b["original"]):
            try:
                datos = yaml.safe_load(m.group(1)) or []
            except yaml.YAMLError as e:
                raise PlanInvalido(f"Bloque «{b['titulo']}»: la sección de Gráficos no es YAML válido ({e})") from None
            for g in datos if isinstance(datos, list) else []:
                if isinstance(g, dict) and g.get("tipo") in DURACIONES:
                    lista.append({"tipo": g["tipo"], "ancla": str(g.get("ancla") or ""),
                                  "datos": g.get("datos") or {}, **({"duracion": g["duracion"]} if g.get("duracion") else {})})
        if lista:
            res[b["titulo"]] = lista
    return res


def buscar_ancla(ancla: str, palabras: list[dict], desde: float, hasta: float) -> tuple[float | None, float]:
    """Segundo (en el Corte) en el que se dicen las palabras del ancla, y lo bien que casan (0–1)."""
    from difflib import SequenceMatcher

    from tn.corte import normalizar

    objetivo = normalizar(ancla).split()
    if not objetivo:
        return None, 0.0
    ventana = [p for p in palabras if desde - 2 <= p["inicio"] <= hasta + 2]
    # Se compara token a token: "1.30.7" son tres tokens (1, 30, 7) tanto en el ancla como dicho.
    tokens, de_palabra = [], []
    for i, p in enumerate(ventana):
        for t in normalizar(p["palabra"]).split():
            tokens.append(t)
            de_palabra.append(i)
    mejor, cuando = 0.0, None
    n = len(objetivo)
    for i in range(len(tokens)):
        for largo in (n - 1, n, n + 1, n + 2):
            trozo = tokens[i:i + max(largo, 1)]
            r = SequenceMatcher(None, objetivo, trozo).ratio()
            if r > mejor:
                mejor, cuando = r, ventana[de_palabra[i]]["inicio"]
    return (cuando, mejor) if mejor >= UMBRAL_ANCLA else (None, mejor)


def anclar(previstos: dict[str, list[dict]], bloques: list[dict], palabras: list[dict]) -> tuple[list[dict], list[dict]]:
    """Coloca los Gráficos previstos en el tiempo. Devuelve (anclados, sin_ancla)."""
    anclados, sin = [], []
    por_titulo = {b["titulo"]: b for b in bloques}
    for titulo, lista in previstos.items():
        b = por_titulo.get(titulo)
        for g in lista:
            if not b or b.get("dudoso"):
                sin.append({**g, "bloque": titulo, "motivo": "el bloque no se encontró en la grabación"})
                continue
            t, parecido = buscar_ancla(g["ancla"], palabras, b["inicio"], b["fin"])
            if t is None:
                sin.append({**g, "bloque": titulo, "motivo": f"no se dijo el ancla (parecido {parecido:.0%})"})
            else:
                anclados.append({**g, "inicio": round(t, 2), "bloque": titulo, "origen": "guion"})
    return anclados, sin


# --- Capturas ----------------------------------------------------------------------------


def _chrome() -> Path:
    base = Path.home() / ".cache" / "hyperframes" / "chrome"
    for p in sorted(base.glob("**/chrome-headless-shell"), reverse=True):
        if p.is_file() and os.access(p, os.X_OK):
            return p
    mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac.exists():
        return mac
    raise PlanInvalido("No encuentro Chrome para las capturas (lanza un render de HyperFrames una vez)")


def capturar(url: str, destino: Path) -> Path:
    """Captura de la parte de arriba de la página (1380 px de ancho, como el marco)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(_chrome()), "--headless", "--hide-scrollbars", "--disable-gpu", "--no-first-run",
                        "--window-size=1380,1900", "--virtual-time-budget=8000", f"--screenshot={destino}", url],
                       capture_output=True, text=True, timeout=90)
    if not destino.is_file() or destino.stat().st_size < 5000:
        raise PlanInvalido(f"No se pudo capturar {url}: {(r.stderr or '')[-200:]}")
    return destino


# --- Render -------------------------------------------------------------------------------


def renderizar(g: dict, trabajo: Path, salida_dir: Path) -> Path:
    """Rellena la plantilla del Gráfico y la renderiza a `<salida_dir>/<id>.mov`."""
    base = carpeta_plantillas()
    carpeta = trabajo / g["id"]
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)
    html = (base / "plantillas" / f"{g['tipo']}.html").read_text().replace("__DURACION__", f"{g['duracion']:.2f}")
    (carpeta / "index.html").write_text(html)
    # El servidor de HyperFrames no sigue enlaces simbólicos: enlaces físicos (no ocupan espacio).
    for rel in ["comun.css", "node_modules/gsap/dist/gsap.min.js", *[f"fuentes/{f.name}" for f in (base / "fuentes").glob("*.otf")]]:
        origen = base / rel
        if not origen.is_file():
            raise PlanInvalido(f"Falta {origen}: lanza `npm install` en graficos/")
        (carpeta / rel).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(origen, carpeta / rel)
        except OSError:
            shutil.copy2(origen, carpeta / rel)
    datos = dict(g["datos"])
    if g["tipo"] == "captura":
        capturar(datos["url"], carpeta / "captura.png")
        datos["imagen"] = "captura.png"
    (carpeta / "variables.json").write_text(json.dumps({"datos": json.dumps(datos, ensure_ascii=False)}, ensure_ascii=False))
    salida_dir.mkdir(parents=True, exist_ok=True)
    salida = salida_dir / f"{g['id']}.mov"
    r = subprocess.run(["npx", "-y", HYPERFRAMES, "render", str(carpeta), "--format", "mov", "--fps", "30",
                        "--quality", "standard", "-o", str(salida), "--variables-file", str(carpeta / "variables.json")],
                       capture_output=True, text=True, timeout=600, cwd=carpeta,
                       env={**os.environ, "HYPERFRAMES_TELEMETRY": "0", "DO_NOT_TRACK": "1"})
    if r.returncode != 0 or not salida.is_file():
        raise PlanInvalido(f"HyperFrames no renderizó {g['id']}: {(r.stderr or r.stdout)[-400:]}")
    return salida


@dataclass
class ResultadoGraficos:
    renderizados: list[str]
    fallidos: list[str]
    avisos: list[str]
