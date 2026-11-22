import json
import shutil
import subprocess
from datetime import date

import pytest

from tn import capcut, montaje

hay_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="necesita ffmpeg")


def test_vocabulario_toma_nombres_siglas_y_versiones_no_inicios_de_frase():
    guion = ("Esta semana ha salido Postgres 19 y GPT-6.2. Parchea NGINX hoy: dos CVE-2026-123633. "
             "Lo dice Simon Willison en https://simonwillison.net/x.")
    v = montaje.vocabulario(guion).split(", ")
    for esperado in ("Postgres", "GPT-6.2", "NGINX", "CVE-2026-123633", "Simon", "Willison"):
        assert esperado in v
    assert "Esta" not in v and "Parchea" not in v and "Lo" not in v
    assert not any("simonwillison" in t for t in v)


@hay_ffmpeg
def test_preparar_audio_deja_la_voz_a_menos_14_lufs(tmp_path):
    entrada = tmp_path / "grabacion.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=6",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-filter:a", "volume=0.05",
                    "-shortest", "-c:v", "libx264", "-c:a", "aac", str(entrada)], check=True)
    r = montaje.preparar_audio(entrada, tmp_path / "limpia.mp4")
    assert r["lufs_entrada"] < -25
    assert abs(r["lufs_salida"] - (-14)) < 1.5
    # El vídeo se copia sin recodificar
    sondeo = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                             str(tmp_path / "limpia.mp4")], capture_output=True, text=True).stdout.split()
    assert sondeo.count("video") == 1 and sondeo.count("audio") == 1


def test_montar_retoma_y_rehace(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_MONTAJES", str(tmp_path))
    monkeypatch.setenv("TN_HOME", str(tmp_path))
    (tmp_path / "2026-11-13").mkdir()
    (tmp_path / "2026-11-13" / "grabacion.mov").write_bytes(b"x")
    llamadas = []
    monkeypatch.setattr(montaje, "preparar_audio", lambda e, s: llamadas.append("preparar") or {"lufs_salida": -14})
    monkeypatch.setattr(montaje, "transcribir", lambda e, s, pista="": llamadas.append("transcribir") or {"palabras": 3})
    semana = date(2026, 11, 13)
    montaje.montar(semana)
    montaje.montar(semana)  # ya hecho: no repite
    assert llamadas == ["preparar", "transcribir"]
    montaje.montar(semana, rehacer="transcribir")
    assert llamadas == ["preparar", "transcribir", "transcribir"]
    with pytest.raises(montaje.MontajeInvalido, match="aún no está construido"):
        montaje.montar(semana, hasta="ensamblar")


def test_sin_grabacion_dice_donde_dejarla(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_MONTAJES", str(tmp_path))
    (tmp_path / "2026-11-13").mkdir()
    with pytest.raises(montaje.MontajeInvalido, match="grabacion.mp4"):
        montaje.montar(date(2026, 11, 13))


def test_extraer_plantillas_de_un_proyecto(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPCUT_DRAFTS", str(tmp_path / "drafts"))
    monkeypatch.setenv("TN_CAPCUT_KIT", str(tmp_path / "kit"))
    proyecto = tmp_path / "drafts" / "demo"
    proyecto.mkdir(parents=True)
    (proyecto / "draft_info.json").write_text(json.dumps({
        "materials": {"texts": [{"id": "T1", "content": "{}"}], "material_animations": [{"id": "A1"}]},
        "tracks": [{"type": "video", "segments": []},
                   {"type": "text", "segments": [{"id": "S1", "material_id": "T1", "extra_material_refs": ["A1"]}]}],
    }))
    rutas = capcut.extraer_plantillas("demo")
    assert [r.name for r in rutas] == list(capcut.PLANTILLAS)
    assert json.loads(rutas[1].read_text())["id"] == "S1"
    with pytest.raises(capcut.CapCutNoDisponible):
        capcut.extraer_plantillas("no-existe")


def test_acepta_el_unico_video_de_la_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_MONTAJES", str(tmp_path))
    c = tmp_path / "2026-11-13"
    c.mkdir()
    (c / "IMG_6804.MOV").write_bytes(b"x")
    (c / "grabacion-limpia.mp4").write_bytes(b"x")  # salida nuestra: no cuenta
    assert montaje.Montaje(date(2026, 11, 13)).grabacion.name == "IMG_6804.MOV"
    (c / "otro.mp4").write_bytes(b"x")
    with pytest.raises(montaje.MontajeInvalido, match="renombra"):
        montaje.Montaje(date(2026, 11, 13)).grabacion
