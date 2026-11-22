"""El Montador (docs/arnes.md §9): de la Grabación a un Montaje de CapCut.

Cada Montaje vive en `~/Movies/jpdev/<semana>/` (CapCut solo lee dentro de ~/Movies).
Los pasos se apuntan en `estado.json`: relanzar `tn montar` retoma donde se quedó.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tn.db import _iso, ahora

PASOS = ("preparar", "transcribir", "cortar", "graficos", "ensamblar", "revisar")
IMPLEMENTADOS = ("preparar", "transcribir", "cortar", "graficos")
EXTENSIONES = (".mp4", ".mov", ".m4v", ".mkv")

# Voz: paso alto, ruido suave fuera, compresión ligera, y −14 LUFS (estándar de YouTube).
FILTRO_VOZ = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2"
LOUDNORM = {"I": -14.0, "TP": -1.5, "LRA": 11.0}
MODELO_WHISPER = "mlx-community/whisper-large-v3-turbo"


class MontajeInvalido(RuntimeError):
    pass


def raiz_montajes() -> Path:
    return Path(os.environ.get("TN_MONTAJES", "~/Movies/jpdev")).expanduser()


def carpeta(semana: date) -> Path:
    return raiz_montajes() / semana.isoformat()


@dataclass
class Montaje:
    semana: date

    @property
    def carpeta(self) -> Path:
        return carpeta(self.semana)

    @property
    def grabacion(self) -> Path:
        """`grabacion.<ext>` o, si no la hay, el único vídeo de la carpeta (p. ej. IMG_6804.MOV del iPhone)."""
        for ext in EXTENSIONES:
            if (self.carpeta / f"grabacion{ext}").is_file():
                return self.carpeta / f"grabacion{ext}"
        videos = [f for f in self.carpeta.iterdir()
                  if f.suffix.lower() in EXTENSIONES and not f.stem.startswith(("grabacion-", "."))] \
            if self.carpeta.is_dir() else []
        if len(videos) == 1:
            return videos[0]
        if len(videos) > 1:
            raise MontajeInvalido(f"Hay {len(videos)} vídeos en {self.carpeta}: renombra el bueno a grabacion.mp4/.mov")
        raise MontajeInvalido(
            f"No encuentro la Grabación: déjala en {self.carpeta}/grabacion.mp4 (o .mov)")

    @property
    def limpia(self) -> Path:
        return self.carpeta / "grabacion-limpia.mp4"

    @property
    def transcripcion(self) -> Path:
        return self.carpeta / "transcripcion.json"

    @property
    def corte(self) -> Path:
        return self.carpeta / "corte.json"

    def ajustes_corte(self) -> dict:
        ruta = self.carpeta / "ajustes-corte.json"
        return json.loads(ruta.read_text()) if ruta.is_file() else {"quitar": [], "mantener": []}

    def guardar_ajustes_corte(self, quitar: list[int], mantener: list[int]) -> dict:
        a = self.ajustes_corte()
        a["quitar"] = sorted((set(a["quitar"]) | set(quitar)) - set(mantener))
        a["mantener"] = sorted((set(a["mantener"]) | set(mantener)) - set(quitar))
        (self.carpeta / "ajustes-corte.json").write_text(json.dumps(a, indent=1))
        return a

    @property
    def plan_graficos(self) -> Path:
        """Gráficos que decide el agente (rótulos, infografías, capturas)."""
        return self.carpeta / "plan-graficos.json"

    @property
    def trabajo(self) -> str:
        """Nombre del trabajo en capcut-kit y del proyecto de CapCut."""
        return f"jpdev-{self.semana.isoformat()}"

    def guion(self) -> str:
        """El guion del Resumen semanal de esa semana (vacío si no hay)."""
        from tn import propuestas

        ruta = propuestas.carpeta_semana(self.semana) / "resumen-semanal.md"
        return propuestas.leer(ruta).cuerpo if ruta.is_file() else ""

    @property
    def _estado_ruta(self) -> Path:
        return self.carpeta / "estado.json"

    def estado(self) -> dict:
        return json.loads(self._estado_ruta.read_text()) if self._estado_ruta.is_file() else {"pasos": {}}

    def marcar(self, paso: str, **detalle) -> None:
        e = self.estado()
        e["pasos"][paso] = {"hecho": _iso(ahora()), **detalle}
        self._estado_ruta.write_text(json.dumps(e, ensure_ascii=False, indent=1))

    def hecho(self, paso: str) -> bool:
        return paso in self.estado()["pasos"]


# --- 1. Preparar el audio -------------------------------------------------------------


def _ffmpeg(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise MontajeInvalido(f"ffmpeg falló: {r.stderr.strip()[-400:]}")
    return r


def _codec_video(ruta: Path) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                        "-of", "csv=p=0", str(ruta)], capture_output=True, text=True)
    # csv puede añadir una coma final (p. ej. "hevc," en los .MOV del iPhone)
    return r.stdout.strip().split("\n")[0].strip(",").strip()


def medir_loudness(ruta: Path, filtro_previo: str = "") -> dict:
    """Primera pasada de loudnorm: mide el audio (LUFS, pico, rango) sin escribir nada."""
    objetivo = f"loudnorm=I={LOUDNORM['I']}:TP={LOUDNORM['TP']}:LRA={LOUDNORM['LRA']}:print_format=json"
    filtro = f"{filtro_previo},{objetivo}" if filtro_previo else objetivo
    r = _ffmpeg("-i", str(ruta), "-vn", "-af", filtro, "-f", "null", "-")
    bloque = r.stderr[r.stderr.rindex("{"): r.stderr.rindex("}") + 1]
    return json.loads(bloque)


def preparar_audio(entrada: Path, salida: Path) -> dict:
    """Limpia la voz y la deja a −14 LUFS en dos pasadas. El vídeo se copia sin recodificar."""
    m = medir_loudness(entrada, FILTRO_VOZ)
    norm = (f"loudnorm=I={LOUDNORM['I']}:TP={LOUDNORM['TP']}:LRA={LOUDNORM['LRA']}"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    tmp = salida.with_suffix(".tmp.mp4")
    # hvc1: sin esta etiqueta, QuickTime y CapCut no abren el HEVC del iPhone copiado a .mp4.
    _ffmpeg("-y", "-i", str(entrada), "-map", "0:v:0?", "-map", "0:a:0", "-c:v", "copy", "-tag:v", "hvc1"
            if _codec_video(entrada) == "hevc" else "avc1",
            "-af", f"{FILTRO_VOZ},{norm}", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(tmp))
    tmp.replace(salida)
    final = medir_loudness(salida)
    return {"lufs_entrada": float(m["input_i"]), "lufs_salida": float(final["input_i"]),
            "pico_salida": float(final["input_tp"])}


# --- 2. Transcribir --------------------------------------------------------------------


def vocabulario(guion: str, maximo: int = 60) -> str:
    """Nombres propios, siglas y versiones del guion, como pista para Whisper.

    Sin pista, Whisper convierte "Postgres 19" en "post-cresta insinuiv": los términos
    técnicos en inglés dentro de una frase en español le cuestan. Se toman las palabras
    con mayúscula a mitad de frase (no la primera de cada frase), las siglas y lo que
    mezcla letras y números (versiones, modelos, CVE).
    """
    cuerpo = re.sub(r"https?://\S+|[#*_>|`]", " ", guion)
    vistos: dict[str, None] = {}
    for m in re.finditer(r"[\w][\w.+-]*[\w]|\w", cuerpo):
        t = m.group()
        letras, digitos = any(c.isalpha() for c in t), any(c.isdigit() for c in t)
        previo = cuerpo[: m.start()].rstrip()
        inicio_frase = not previo or previo[-1] in ".:;!?¿¡(\n-•«\"'"
        siglas = sum(c.isupper() for c in t) >= 2
        nombre = t[0].isupper() and not inicio_frase
        if (letras and digitos) or siglas or nombre:
            vistos.setdefault(t, None)
    return ", ".join(list(vistos)[:maximo])


def transcribir(entrada: Path, salida: Path, idioma: str = "es", modelo: str = MODELO_WHISPER,
                pista: str = "") -> dict:
    """Transcripción local con mlx-whisper, con tiempos por palabra."""
    import mlx_whisper  # import tardío: tarda en cargar y solo hace falta aquí

    r = mlx_whisper.transcribe(str(entrada), path_or_hf_repo=modelo, language=idioma,
                               word_timestamps=True, condition_on_previous_text=False,
                               initial_prompt=pista or None)
    palabras = [
        {"palabra": w["word"].strip(), "inicio": round(float(w["start"]), 3), "fin": round(float(w["end"]), 3),
         "confianza": round(w.get("probability", 0.0), 3)}
        for s in r.get("segments", []) for w in s.get("words", []) if w.get("word", "").strip()
    ]
    frases = [{"texto": s["text"].strip(), "inicio": round(s["start"], 3), "fin": round(s["end"], 3)}
              for s in r.get("segments", [])]
    datos = {"modelo": modelo, "idioma": idioma, "texto": r.get("text", "").strip(),
             "frases": frases, "palabras": palabras}
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    return {"palabras": len(palabras), "frases": len(frases),
            "duracion_s": float(palabras[-1]["fin"]) if palabras else 0.0}


# --- 3. Cortar ----------------------------------------------------------------------------


def cortar(m: "Montaje") -> dict:
    from tn import capcut, corte

    trans = json.loads(m.transcripcion.read_text())
    res = corte.cortar(trans, m.guion(), m.ajustes_corte())
    m.corte.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    # Transcripción en el tiempo del Corte: los Gráficos se colocan con ella.
    tramos = [corte.Tramo(t["inicio"], t["fin"], t["unidades"]) for t in res["tramos"]]
    palabras = []
    for p in trans["palabras"]:
        ini = corte.a_tiempo_corte(p["inicio"], tramos)
        fin = corte.a_tiempo_corte(p["fin"], tramos)
        if ini is not None and fin is not None:
            palabras.append({**p, "inicio": ini, "fin": fin})
    (m.carpeta / "transcripcion-corte.json").write_text(json.dumps({"palabras": palabras}, ensure_ascii=False, indent=1))
    capcut.preparar_trabajo(m.trabajo, m.limpia, res["tramos"])
    us = res["unidades"]
    return {
        "duracion_grabacion": res["duracion_grabacion"],
        "duracion_corte": res["duracion_corte"],
        "unidades": len(us),
        "otras_tomas": sum(u["decision"] == "otra-toma" for u in us),
        "errores": sum(u["decision"] == "error" for u in us),
        "dudosas": sum(u["dudosa_con"] is not None for u in us),
        "tramos": len(res["tramos"]),
        "bloques_situados": len(res["bloques"]),
        "bloques_dudosos": sum(b["dudoso"] for b in res["bloques"]),
    }


# --- 4. Gráficos ---------------------------------------------------------------------------


def contexto_graficos(m: "Montaje") -> dict:
    from tn import graficos

    if not m.corte.is_file():
        raise MontajeInvalido("Aún no hay Corte: primero `tn montar --hasta cortar`")
    corte_ = json.loads(m.corte.read_text())
    trans = json.loads((m.carpeta / "transcripcion-corte.json").read_text())
    return graficos.contexto_agente(corte_, trans, m.guion())


def guardar_plan_graficos(m: "Montaje", plan: list[dict]) -> list[str]:
    """Valida el plan del agente (sin estructurales) y lo guarda. Devuelve avisos."""
    from tn import graficos

    duracion = json.loads(m.corte.read_text())["duracion_corte"]
    prohibidos = [g for g in plan if g.get("tipo") in ("cabecera", "sello", "final")]
    if prohibidos:
        raise graficos.PlanInvalido("Cabeceras, sello y pantalla final los pone el código: quítalos del plan")
    validado = graficos.validar(plan, duracion)
    m.plan_graficos.write_text(json.dumps(validado, ensure_ascii=False, indent=1))
    completo = graficos.validar(validado + graficos.estructurales(json.loads(m.corte.read_text())), duracion)
    return graficos.solapes(completo)


def hacer_graficos(m: "Montaje", con_agente: bool = True, origen: str = "manual", al_avanzar=None) -> dict:
    from tn import agentes, capcut, config, db, graficos

    if con_agente and not m.plan_graficos.is_file():
        if al_avanzar:
            al_avanzar("graficos: el agente decide rótulos, infografías y capturas")
        conn = db.conectar(config.ruta_db())
        try:
            r = agentes.lanzar(conn, "montador-graficos", f"Semana: {m.semana.isoformat()}.", origen=origen)
        finally:
            conn.close()
        if r.estado != "ok" or not m.plan_graficos.is_file():
            raise MontajeInvalido(f"El agente no dejó plan de Gráficos: {r.resultado[-400:]}")
    corte_ = json.loads(m.corte.read_text())
    propios = json.loads(m.plan_graficos.read_text()) if m.plan_graficos.is_file() else []
    plan = graficos.validar(propios + graficos.estructurales(corte_), corte_["duracion_corte"])
    trabajo = capcut.carpeta_trabajos() / m.trabajo
    hechos, fallidos = [], []
    for g in plan:
        if al_avanzar:
            al_avanzar(f"graficos: {g['id']}")
        try:
            graficos.renderizar(g, m.carpeta / "graficos", trabajo / "assets")
            hechos.append(g)
        except graficos.PlanInvalido as e:
            fallidos.append(f"{g['id']}: {e}")
    # Lo que `capcut-bridge.py graphics` lee (INPUT-CONTRACT.md del kit)
    (trabajo / "graphics-plan.json").write_text(json.dumps(
        {"graphics": [{"id": g["id"], "file": f"{g['id']}.mov", "start": g["inicio"], "tipo": g["tipo"],
                       "duracion": g["duracion"]} for g in hechos]}, ensure_ascii=False, indent=1))
    (m.carpeta / "graficos.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    return {"graficos": len(hechos), "fallidos": fallidos, "solapes": graficos.solapes(plan),
            "por_tipo": {t: sum(g["tipo"] == t for g in hechos) for t in graficos.DURACIONES}}


# --- Orquestación ------------------------------------------------------------------------


def montar(semana: date, hasta: str = "cortar", rehacer: str | None = None, al_avanzar=None,
           con_agente: bool = True, origen: str = "manual") -> dict:
    """Ejecuta los pasos en orden hasta `hasta`; se salta los hechos salvo desde `rehacer`."""
    if hasta not in PASOS:
        raise MontajeInvalido(f"Paso desconocido: {hasta}. Pasos: {', '.join(PASOS)}")
    if hasta not in IMPLEMENTADOS:
        raise MontajeInvalido(f"El paso {hasta} aún no está construido (hechos: {', '.join(IMPLEMENTADOS)})")
    m = Montaje(semana)
    if not m.carpeta.is_dir():
        raise MontajeInvalido(f"No existe {m.carpeta}: créala y deja dentro grabacion.mp4")
    rehacer_desde = PASOS.index(rehacer) if rehacer else len(PASOS)
    resultados = {}
    for i, paso in enumerate(PASOS[: PASOS.index(hasta) + 1]):
        if m.hecho(paso) and i < rehacer_desde:
            resultados[paso] = "ya hecho"
            continue
        if al_avanzar:
            al_avanzar(paso)
        if paso == "preparar":
            detalle = preparar_audio(m.grabacion, m.limpia)
        elif paso == "transcribir":
            guion = m.guion()
            detalle = transcribir(m.limpia, m.transcripcion, pista=vocabulario(guion) if guion else "")
            detalle["con_vocabulario_del_guion"] = bool(guion)
        elif paso == "cortar":
            detalle = cortar(m)
        elif paso == "graficos":
            detalle = hacer_graficos(m, con_agente=con_agente, origen=origen, al_avanzar=al_avanzar)
        m.marcar(paso, **detalle)
        resultados[paso] = detalle
    return resultados


def previa_corte(m: Montaje) -> Path:
    """MP4 rápido del Corte, con los Gráficos encima si ya están hechos, para verlo sin CapCut.

    No es el montaje final (sin círculo, música ni efectos): sirve para revisar ritmo y tiempos.
    """
    from tn import capcut

    datos = json.loads(m.corte.read_text())
    partes, ref = [], []
    for i, t in enumerate(datos["tramos"]):
        partes.append(f"[0:v]trim={t['inicio']}:{t['fin']},setpts=PTS-STARTPTS,fps=30,scale=1920:1080[v{i}];"
                      f"[0:a]atrim={t['inicio']}:{t['fin']},asetpts=PTS-STARTPTS[a{i}];")
        ref.append(f"[v{i}][a{i}]")
    filtro = "".join(partes) + "".join(ref) + f"concat=n={len(ref)}:v=1:a=1[base][aud];"
    entradas = ["-i", str(m.limpia)]
    plan = json.loads((m.carpeta / "graficos.json").read_text()) if (m.carpeta / "graficos.json").is_file() else []
    assets = capcut.carpeta_trabajos() / m.trabajo / "assets"
    plan = [g for g in plan if (assets / f"{g['id']}.mov").is_file()]
    extra = max([g["inicio"] + g["duracion"] - datos["duracion_corte"] for g in plan] + [0])
    actual = "base"
    if extra > 0:  # la pantalla final dura más que el Corte: congela el último fotograma
        filtro += f"[base]tpad=stop_mode=clone:stop_duration={extra:.2f}[base2];[aud]apad=pad_dur={extra:.2f}[aud2];"
        actual, audio = "base2", "aud2"
    else:
        audio = "aud"
    for k, g in enumerate(plan, start=1):
        entradas += ["-i", str(assets / f"{g['id']}.mov")]
        fin = g["inicio"] + g["duracion"]
        filtro += (f"[{k}:v]setpts=PTS+{g['inicio']}/TB[g{k}];"
                   f"[{actual}][g{k}]overlay=0:0:eof_action=pass:enable='between(t,{g['inicio']},{fin})'[o{k}];")
        actual = f"o{k}"
    filtro += f"[{actual}]scale=-2:720[vout]"
    salida = m.carpeta / "corte-previa.mp4"
    _ffmpeg("-y", *entradas, "-filter_complex", filtro, "-map", "[vout]", "-map", f"[{audio}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", str(salida))
    return salida
