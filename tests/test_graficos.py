import json
from datetime import date

import pytest

from tn import graficos, montaje

CORTE = {"duracion_corte": 120.0, "bloques": [
    {"titulo": "Gancho", "inicio": 0.0, "fin": 20.0},
    {"titulo": "1. NGINX: dos fallos críticos", "inicio": 21.0, "fin": 60.0},
    {"titulo": "2. Postgres 19 (dos Historias)", "inicio": 61.0, "fin": 63.0},   # muy corto: sin cabecera
    {"titulo": "3. Bloque raro", "inicio": 64.0, "fin": 110.0, "dudoso": True},  # dudoso: sin cabecera
]}


def test_estructurales_cabeceras_sello_y_final():
    e = graficos.estructurales(CORTE)
    assert [(g["tipo"], g["inicio"]) for g in e] == [("cabecera", 21.3), ("sello", 20.0), ("final", 120.0)]
    assert e[0]["datos"] == {"numero": "1", "titulo": "NGINX: dos fallos críticos"}


def test_validar_completa_ids_y_duraciones_y_recorta_al_corte():
    plan = graficos.validar([
        {"tipo": "tabla", "inicio": 115, "datos": {"titulo": "T", "columnas": ["a"], "filas": [["1"]]}},
        {"tipo": "rotulo", "inicio": 30, "datos": {"valor": "1.30.7"}},
    ], 120.0)
    assert [g["id"] for g in plan] == ["g01-rotulo", "g02-tabla"]
    assert plan[0]["duracion"] == 4.0 and plan[1]["duracion"] == 5.0


@pytest.mark.parametrize("g, error", [
    ({"tipo": "video", "inicio": 1, "datos": {}}, "tipo desconocido"),
    ({"tipo": "rotulo", "inicio": 1, "datos": {}}, "faltan datos: valor"),
    ({"tipo": "rotulo", "inicio": 500, "datos": {"valor": "x"}}, "fuera del Corte"),
    ({"tipo": "captura", "inicio": 1, "datos": {"url": "https://x"}}, "faltan datos: fuente"),
])
def test_validar_rechaza(g, error):
    with pytest.raises(graficos.PlanInvalido, match=error):
        graficos.validar([g], 120.0)


def test_solapes():
    plan = graficos.validar([{"tipo": "rotulo", "inicio": 10, "datos": {"valor": "a"}},
                             {"tipo": "rotulo", "inicio": 12, "datos": {"valor": "b"}}], 120.0)
    assert graficos.solapes(plan) == ["g01-rotulo y g02-rotulo se solapan"]


def test_el_agente_no_puede_poner_estructurales(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_MONTAJES", str(tmp_path))
    m = montaje.Montaje(date(2026, 11, 13))
    m.carpeta.mkdir()
    m.corte.write_text(json.dumps(CORTE))
    with pytest.raises(graficos.PlanInvalido, match="los pone el código"):
        montaje.guardar_plan_graficos(m, [{"tipo": "sello", "inicio": 1, "datos": {}}])
    avisos = montaje.guardar_plan_graficos(m, [{"tipo": "rotulo", "inicio": 21.5, "datos": {"valor": "9.2"}}])
    assert any("cabecera" in a for a in avisos)  # pisa la cabecera del bloque 1
    assert json.loads(m.plan_graficos.read_text())[0]["id"] == "g01-rotulo"


def test_las_plantillas_tienen_los_campos_que_valida_el_codigo():
    base = graficos.carpeta_plantillas() / "plantillas"
    for tipo in graficos.DURACIONES:
        html = (base / f"{tipo}.html").read_text()
        assert "__DURACION__" in html and 'data-composition-id="root"' in html
        for campo in graficos.CAMPOS[tipo]:
            if tipo != "captura":  # url se convierte en imagen antes de renderizar
                assert f"d.{campo}" in html, f"{tipo} no usa {campo}"
