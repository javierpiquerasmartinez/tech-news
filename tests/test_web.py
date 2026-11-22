import pytest
from fastapi.testclient import TestClient

from tn import db, historias
from tn.modelo import ItemRecogido
from tn.prefiltro import prefiltrar


def _p(u=5, d=5, s=5):
    return {"urgencia": u, "just_urgencia": "porque sí", "valor_didactico": d, "just_didactico": "j",
            "peso_semanal": s, "just_peso": "j"}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_DB", str(tmp_path / "t.db"))
    conn = db.conectar(tmp_path / "t.db")
    eid = db.abrir_ejecucion(conn, "recoger", "manual", db.ahora())
    crudos = [ItemRecogido(fuente_id="hn", url=f"https://x.example/{n}", titulo=f"Item {n}", publicado_en=db.ahora())
              for n in range(1, 5)]
    db.insertar_items(conn, eid, prefiltrar(crudos).aceptados, db.ahora())
    db.cerrar_ejecucion(conn, eid, "ok")
    historias.aplicar_lote(conn, {"nuevas": [
        {"titulo": "Sale PostgreSQL 19", "area": "desarrollo", "items": [1, 2], **_p(5, 8, 7)},
        {"titulo": "RCE en NGINX", "area": "seguridad", "items": [3], **_p(9, 5, 9), "bomba": True},
    ]})
    conn.close()
    from tn.web.app import app
    return TestClient(app)


def test_paginas_cargan(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Sale PostgreSQL 19" in r.text and "Historia bomba" in r.text
    assert "1 Items sin editar" in r.text
    assert cliente.get("/fuentes").status_code == 200
    r = cliente.get("/ejecuciones")
    assert r.status_code == 200 and "recoger" in r.text
    assert cliente.get("/ejecuciones/1").status_code == 200


def test_descartar_desde_la_web_queda_registrado_con_origen_web(cliente):
    r = cliente.post("/historia/1/descartar", data={"motivo": "Ya está muy contada"})
    assert r.status_code == 200 and "Descartada" in r.text and "Ya está muy contada" in r.text
    assert "Sale PostgreSQL 19" in cliente.get("/?vista=descartadas").text
    assert "Sale PostgreSQL 19" not in cliente.get("/?vista=semana").text
    r = cliente.post("/historia/1/restaurar")
    assert "Destacar" in r.text


def test_puntuar_solo_cambia_lo_que_cambia(cliente):
    r = cliente.post("/historia/1/puntuar", data={"urgencia": 5, "valor_didactico": 10, "peso_semanal": 7, "motivo": "da para vídeo"})
    assert r.status_code == 200 and 'role="alert"' not in r.text
    r = cliente.post("/historia/1/puntuar", data={"urgencia": 5, "valor_didactico": 10, "peso_semanal": 7})
    assert "No has cambiado ninguna puntuación" in r.text


def test_errores_de_dominio_se_muestran_en_la_tarjeta(cliente):
    cliente.post("/historia/1/descartar", data={"motivo": ""})
    r = cliente.post("/historia/1/destacar")
    assert 'role="alert"' in r.text


def test_fusionar_y_separar_recargan_la_pagina(cliente):
    r = cliente.post("/historia/1/separar", data={"items": [2], "titulo": "Otra cosa"})
    assert r.status_code == 204 and r.headers["HX-Refresh"] == "true"
    r = cliente.post("/historia/1/fusionar", data={"otra": 3})
    assert r.status_code == 204
    r = cliente.post("/historia/1/fusionar", data={"otra": 1})
    assert "consigo misma" in r.text


def test_lanzar_accion_desconocida_es_404(cliente):
    assert cliente.post("/lanzar/borrar-todo").status_code == 404
