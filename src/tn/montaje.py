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
IMPLEMENTADOS = ("preparar", "transcribir")
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
        for ext in EXTENSIONES:
            if (self.carpeta / f"grabacion{ext}").is_file():
                return self.carpeta / f"grabacion{ext}"
        raise MontajeInvalido(
            f"No encuentro la Grabación: déjala en {self.carpeta}/grabacion.mp4 (o .mov)")

    @property
    def limpia(self) -> Path:
        return self.carpeta / "grabacion-limpia.mp4"

    @property
    def transcripcion(self) -> Path:
        return self.carpeta / "transcripcion.json"

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


def medir_loudness(ruta: Path, filtro_previo: str = "") -> dict:
    """Primera pasada de loudnorm: mide el audio (LUFS, pico, rango) sin escribir nada."""
    objetivo = f"loudnorm=I={LOUDNORM['I']}:TP={LOUDNORM['TP']}:LRA={LOUDNORM['LRA']}:print_format=json"
    filtro = f"{filtro_previo},{objetivo}" if filtro_previo else objetivo
    r = _ffmpeg("-i", str(ruta), "-af", filtro, "-f", "null", "-")
    bloque = r.stderr[r.stderr.rindex("{"): r.stderr.rindex("}") + 1]
    return json.loads(bloque)


def preparar_audio(entrada: Path, salida: Path) -> dict:
    """Limpia la voz y la deja a −14 LUFS en dos pasadas. El vídeo se copia sin recodificar."""
    m = medir_loudness(entrada, FILTRO_VOZ)
    norm = (f"loudnorm=I={LOUDNORM['I']}:TP={LOUDNORM['TP']}:LRA={LOUDNORM['LRA']}"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    tmp = salida.with_suffix(".tmp.mp4")
    _ffmpeg("-y", "-i", str(entrada), "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy",
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


# --- Orquestación ------------------------------------------------------------------------


def montar(semana: date, hasta: str = "transcribir", rehacer: str | None = None, al_avanzar=None) -> dict:
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
        m.marcar(paso, **detalle)
        resultados[paso] = detalle
    return resultados
