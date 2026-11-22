"""El Corte (docs/arnes.md §9, paso 3): qué tramos de la Grabación se quedan.

Determinista y sin gastar cuota para lo claro:
- La Grabación se divide en **unidades** (frases), cortando por puntuación final o pausas largas.
- Una unidad que se vuelve a decir justo después (otra Toma) se descarta: gana la última.
- Una unidad con una marca de error ("perdón", "repito", "otra vez") se descarta.
- Muletillas sueltas ("eh", "mmm") y silencios largos dentro de una frase se quitan.
Lo dudoso (dos frases parecidas pero no iguales) se deja dentro y se marca para revisar.

También sitúa cada bloque del guion en el tiempo del Corte, para colocar los Gráficos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

PAUSA_FRASE = 0.7       # una pausa así separa dos unidades aunque no haya punto
PAUSA_INTERNA = 0.4     # silencios más largos dentro de una frase se acortan
MARGEN_ANTES = 0.08
MARGEN_DESPUES = 0.15
UNIR_SI_HUECO = 0.25    # dos tramos tan cerca se dejan juntos
SIMILAR = 0.6           # a partir de aquí, la unidad anterior era otra Toma
DUDOSO = 0.4            # entre DUDOSO y SIMILAR: se queda, pero se marca
MARCAS_ERROR = ("perdon", "repito", "otra vez", "de nuevo", "corta", "me he liado", "me equivoque")
MULETILLAS = {"eh", "ehm", "em", "emm", "mm", "mmm", "hmm", "uh", "um"}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())


def _tokens(texto: str) -> list[str]:
    return normalizar(texto).split()


@dataclass
class Unidad:
    id: int
    palabras: list[dict]
    decision: str = "queda"          # queda | otra-toma | error
    motivo: str = ""
    dudosa_con: int | None = None

    @property
    def texto(self) -> str:
        return " ".join(p["palabra"] for p in self.palabras)

    @property
    def inicio(self) -> float:
        return self.palabras[0]["inicio"]

    @property
    def fin(self) -> float:
        return self.palabras[-1]["fin"]


def unidades(palabras: list[dict]) -> list[Unidad]:
    res: list[Unidad] = []
    actual: list[dict] = []
    for i, p in enumerate(palabras):
        if actual and p["inicio"] - actual[-1]["fin"] >= PAUSA_FRASE:
            res.append(Unidad(len(res), actual))
            actual = []
        actual.append(p)
        fin_frase = p["palabra"].rstrip().endswith((".", "?", "!", "…"))
        if fin_frase and i + 1 < len(palabras):
            res.append(Unidad(len(res), actual))
            actual = []
    if actual:
        res.append(Unidad(len(res), actual))
    return res


def _parecido(a: Unidad, b: Unidad) -> float:
    """Cuánto se parece el arranque de `a` al de `b` (las Tomas repetidas empiezan igual)."""
    ta, tb = _tokens(a.texto), _tokens(b.texto)
    if not ta or not tb:
        return 0.0
    n = min(len(ta), len(tb), 8)
    if len(ta) <= len(tb) and tb[: len(ta)] == ta:  # a es un arranque cortado de b
        return 1.0
    return SequenceMatcher(None, ta[:n], tb[:n]).ratio()


def decidir(us: list[Unidad], ventana: int = 3) -> list[Unidad]:
    for u in us:
        texto = normalizar(u.texto)
        if any(re.search(rf"\b{m}\b", texto) for m in MARCAS_ERROR):
            u.decision, u.motivo = "error", "contiene una marca de error"
    for i, u in enumerate(us):
        if u.decision != "queda":
            continue
        for j in range(i + 1, min(i + 1 + ventana, len(us))):
            if us[j].decision == "error":
                continue
            s = _parecido(u, us[j])
            if s >= SIMILAR:
                u.decision, u.motivo = "otra-toma", f"se repite en la unidad {us[j].id} ({s:.0%})"
                break
            if s >= DUDOSO and u.dudosa_con is None:
                u.dudosa_con = us[j].id
    return us


def _sin_muletillas(palabras: list[dict]) -> list[dict]:
    res = []
    for k, p in enumerate(palabras):
        aislada = (k == 0 or p["inicio"] - palabras[k - 1]["fin"] > 0.15) and \
                  (k == len(palabras) - 1 or palabras[k + 1]["inicio"] - p["fin"] > 0.15)
        if normalizar(p["palabra"]) in MULETILLAS and aislada:
            continue
        res.append(p)
    return res


@dataclass
class Tramo:
    inicio: float
    fin: float
    unidades: list[int] = field(default_factory=list)


def tramos(us: list[Unidad], todas: list[dict]) -> list[Tramo]:
    """Tramos de la Grabación que se quedan, con márgenes y sin silencios largos."""
    limites = [p["inicio"] for p in todas] + [float("inf")]
    finales = [float("-inf")] + [p["fin"] for p in todas]

    def antes(t):  # final de la palabra anterior a t
        return max([f for f in finales if f <= t + 1e-6] or [float("-inf")])

    def despues(t):  # inicio de la palabra siguiente a t
        return min([s for s in limites if s >= t - 1e-6] or [float("inf")])

    res: list[Tramo] = []
    for u in us:
        if u.decision != "queda":
            continue
        ps = _sin_muletillas(u.palabras)
        if not ps:
            continue
        grupos, actual = [], [ps[0]]
        for a, b in zip(ps, ps[1:]):
            if b["inicio"] - a["fin"] > PAUSA_INTERNA:
                grupos.append(actual)
                actual = []
            actual.append(b)
        grupos.append(actual)
        for g in grupos:
            ini = max(g[0]["inicio"] - MARGEN_ANTES, antes(g[0]["inicio"] - 1e-3), 0.0)
            fin = min(g[-1]["fin"] + MARGEN_DESPUES, despues(g[-1]["fin"] + 1e-3) - 0.02)
            if res and ini - res[-1].fin < UNIR_SI_HUECO:
                res[-1].fin = max(res[-1].fin, fin)
                if u.id not in res[-1].unidades:
                    res[-1].unidades.append(u.id)
            else:
                res.append(Tramo(round(ini, 3), round(fin, 3), [u.id]))
    for t in res:
        t.inicio, t.fin = round(t.inicio, 3), round(t.fin, 3)
    return res


def a_tiempo_corte(t: float, ts: list[Tramo]) -> float | None:
    """Pasa un instante de la Grabación al tiempo del Corte (None si cae en algo cortado)."""
    acumulado = 0.0
    for tr in ts:
        if tr.inicio <= t <= tr.fin:
            return round(acumulado + (t - tr.inicio), 3)
        acumulado += tr.fin - tr.inicio
    return None


# --- Bloques del guion ------------------------------------------------------------------

_SIN_BLOQUE = ("título y miniatura", "descripción de youtube")


def bloques_guion(guion: str) -> list[dict]:
    """Secciones `## …` del guion que se graban (gancho, bloques numerados, cierre)."""
    res = []
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", guion, re.M | re.S):
        titulo = m.group(1).strip()
        if titulo.lower().startswith(_SIN_BLOQUE):
            continue
        cuerpo = re.sub(r"\*\*(Visual|Fuentes)[^\n]*", "", m.group(2))
        res.append({"id": len(res), "titulo": re.sub(r"\s*·.*$", "", titulo), "texto": cuerpo, "original": m.group(2)})
    return res


def _palabras_clave(texto: str) -> set[str]:
    return {t for t in _tokens(texto) if len(t) >= 4 or any(c.isdigit() for c in t)}


def situar_bloques(us: list[Unidad], bloques: list[dict], ts: list[Tramo]) -> list[dict]:
    """Asigna cada unidad que queda a un bloque, en orden (nunca se vuelve a un bloque anterior)."""
    quedan = [u for u in us if u.decision == "queda"]
    if not bloques or not quedan:
        return []
    claves = [_palabras_clave(b["texto"]) for b in bloques]

    def puntos(u, b):
        cu = _palabras_clave(u.texto)
        return len(cu & claves[b]) / max(len(cu), 1)

    # Programación dinámica: máxima coincidencia con bloques no decrecientes.
    n, m = len(quedan), len(bloques)
    mejor = [[0.0] * m for _ in range(n)]
    desde = [[0] * m for _ in range(n)]
    for b in range(m):
        mejor[0][b] = puntos(quedan[0], b)
    for i in range(1, n):
        mejor_prev, arg = float("-inf"), 0
        for b in range(m):
            if mejor[i - 1][b] > mejor_prev:
                mejor_prev, arg = mejor[i - 1][b], b
            mejor[i][b] = mejor_prev + puntos(quedan[i], b)
            desde[i][b] = arg
    b = max(range(m), key=lambda k: mejor[n - 1][k])
    asignado = [0] * n
    for i in range(n - 1, -1, -1):
        asignado[i] = b
        b = desde[i][b]

    res = []
    for k, bl in enumerate(bloques):
        mias = [quedan[i] for i in range(n) if asignado[i] == k]
        if not mias:
            continue
        ini = _primer_instante(mias[0], ts)
        fin = _ultimo_instante(mias[-1], ts)
        confianza = sum(puntos(u, k) for u in mias) / len(mias)
        res.append({"bloque": bl["id"], "titulo": bl["titulo"], "inicio": ini, "fin": fin,
                    "unidades": [u.id for u in mias], "confianza": round(confianza, 2),
                    "dudoso": confianza < CONFIANZA_BLOQUE})
    return res


def _primer_instante(u: Unidad, ts: list[Tramo]) -> float:
    """Inicio de la unidad en el tiempo del Corte (su primera palabra que sobrevive)."""
    for p in u.palabras:
        t = a_tiempo_corte(p["inicio"], ts)
        if t is not None:
            return t
    return a_tiempo_corte(next(t.inicio for t in ts if u.id in t.unidades), ts) or 0.0


def _ultimo_instante(u: Unidad, ts: list[Tramo]) -> float:
    for p in reversed(u.palabras):
        t = a_tiempo_corte(p["fin"], ts)
        if t is not None:
            return t
    return a_tiempo_corte([t for t in ts if u.id in t.unidades][-1].fin, ts) or 0.0


CONFIANZA_BLOQUE = 0.35  # por debajo, la grabación no parece decir lo que pone el guion


def cortar(transcripcion: dict, guion: str = "", ajustes: dict | None = None) -> dict:
    """`ajustes`: {"quitar": [ids], "mantener": [ids]} decididos por la persona editora."""
    todas = transcripcion["palabras"]
    us = decidir(unidades(todas))
    ajustes = ajustes or {}
    for u in us:
        if u.id in ajustes.get("quitar", []):
            u.decision, u.motivo = "quitada", "a mano"
        elif u.id in ajustes.get("mantener", []):
            u.decision, u.motivo = "queda", "a mano"
    ts = tramos(us, todas)
    bloques = situar_bloques(us, bloques_guion(guion), ts) if guion else []
    duracion = round(sum(t.fin - t.inicio for t in ts), 3)
    return {
        "duracion_grabacion": round(todas[-1]["fin"], 3) if todas else 0.0,
        "duracion_corte": duracion,
        "unidades": [{"id": u.id, "texto": u.texto, "inicio": u.inicio, "fin": u.fin, "decision": u.decision,
                      "motivo": u.motivo, "dudosa_con": u.dudosa_con} for u in us],
        "tramos": [{"inicio": t.inicio, "fin": t.fin, "unidades": t.unidades} for t in ts],
        "bloques": bloques,
    }
