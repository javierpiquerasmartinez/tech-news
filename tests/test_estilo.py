from datetime import date

import pytest

from tn import config, db, estilo, feedback


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_HOME", str(tmp_path))
    monkeypatch.setenv("TN_DB", str(tmp_path / "data" / "t.db"))
    (tmp_path / "estilo-edicion.md").write_text("# Guía\n\nRótulos abajo a la derecha.\n")
    return tmp_path


def test_nota_con_minuto_version_y_sin_minuto(raiz):
    s = date(2026, 11, 13)
    n = feedback.anadir(s, "2:15 - el rótulo tapa la barbilla", "v1")
    assert (n.minuto, n.texto, n.version, n.segundos) == ("02:15", "el rótulo tapa la barbilla", "v1", 135)
    feedback.anadir(s, "en general, demasiados efectos · bájalos")
    notas = feedback.leer(s)
    assert [x.minuto for x in notas] == ["02:15", "—"]
    assert notas[1].texto == "en general, demasiados efectos - bájalos"  # el separador no rompe la línea
    with pytest.raises(ValueError):
        feedback.anadir(s, "   ")


def test_notas_pendientes_desde_la_ultima_revision_y_ciclo_de_propuesta(raiz):
    conn = db.conectar(config.ruta_db())
    for semana in (date(2026, 11, 13), date(2026, 11, 20)):
        feedback.anadir(semana, "01:00 el rótulo tapa la cara", "v1")
    assert len(estilo.notas_pendientes(conn)) == 2
    estilo.ruta_propuesta().parent.mkdir(parents=True, exist_ok=True)
    estilo.ruta_propuesta().write_text("# Guía\n\nRótulos arriba a la derecha.\n")
    assert "+Rótulos arriba a la derecha." in estilo.diff()
    estilo.aceptar(conn)
    assert "arriba" in (raiz / "estilo-edicion.md").read_text()
    assert list((raiz / "data").glob("estilo-edicion.*.md"))
    # Las notas de hoy ya no cuentan: la revisión las ha considerado (por fecha)
    assert estilo.notas_pendientes(conn) == []
    with pytest.raises(estilo.SinPropuesta):
        estilo.rechazar(conn)
