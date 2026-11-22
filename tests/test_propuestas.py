from datetime import date

import pytest
from fastapi.testclient import TestClient

from tn import db, historias, propuestas
from tn.modelo import ItemRecogido
from tn.prefiltro import prefiltrar


def _p(u=5, d=5, s=5):
    return {"urgencia": u, "just_urgencia": "j", "valor_didactico": d, "just_didactico": "j",
            "peso_semanal": s, "just_peso": "j"}


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_HOME", str(tmp_path))
    monkeypatch.setenv("TN_DB", str(tmp_path / "t.db"))
    c = db.conectar(tmp_path / "t.db")
    eid = db.abrir_ejecucion(c, "recoger", "manual", db.ahora())
    crudos = [ItemRecogido(fuente_id="hn", url=f"https://x.example/{n}", titulo=f"Item {n}", publicado_en=db.ahora())
              for n in range(1, 4)]
    db.insertar_items(c, eid, prefiltrar(crudos).aceptados, db.ahora())
    historias.aplicar_lote(c, {"nuevas": [
        {"titulo": "PostgreSQL 19", "area": "desarrollo", "items": [1], **_p(5, 8, 7)},
        {"titulo": "RCE en NGINX", "area": "seguridad", "items": [2], **_p(9, 5, 9), "bomba": True},
        {"titulo": "Squircles", "area": "otros", "items": [3], **_p(1, 1, 1)},
    ]})
    yield c
    c.close()


@pytest.mark.parametrize("dia, viernes", [
    (date(2026, 11, 20), date(2026, 11, 20)),  # viernes
    (date(2026, 11, 22), date(2026, 11, 20)),  # domingo
    (date(2026, 11, 26), date(2026, 11, 20)),  # jueves: aún la misma semana
    (date(2026, 11, 27), date(2026, 11, 27)),  # viernes siguiente
])
def test_semana_editorial_va_de_viernes_a_jueves(dia, viernes):
    assert propuestas.inicio_semana(dia) == viernes


def test_contexto_ordena_por_peso_y_no_repite_en_linkedin(conn):
    ctx = propuestas.contexto(conn, "linkedin")
    assert [h["titulo"] for h in ctx["historias_candidatas"]][:2] == ["RCE en NGINX", "PostgreSQL 19"]
    assert ctx["historias_candidatas"][0]["items"][0]["url"] == "https://x.example/2"
    propuestas.guardar(conn, "linkedin", "Post NGINX", "Texto del post", [2], enlace="https://x.example/2")
    ctx = propuestas.contexto(conn, "linkedin")
    assert "RCE en NGINX" not in [h["titulo"] for h in ctx["historias_candidatas"]]
    assert ctx["propuestas_ya_escritas_esta_semana"][0]["titulo"] == "Post NGINX"


def test_guardar_escribe_markdown_con_cabecera_y_marca_usada(conn, tmp_path):
    p = propuestas.guardar(conn, "linkedin", "PostgreSQL 19 llega", "Hola **mundo**", [1], enlace="https://pg.example")
    assert p.ruta.parent.parent == tmp_path / "semanas"
    assert p.ruta.name.startswith("linkedin-1-postgresql-19-llega")
    leida = propuestas.leer(p.ruta)
    assert leida.meta["estado"] == "propuesta" and leida.meta["historias"] == [1]
    assert leida.meta["enlace_primer_comentario"] == "https://pg.example"
    assert leida.cuerpo.strip() == "Hola **mundo**"
    assert historias.ver(conn, 1)[0]["estado"] == "nueva"  # escribirla no la usa
    propuestas.cambiar_estado(conn, p.ruta, "aprobada", "manual")
    assert historias.ver(conn, 1)[0]["estado"] == "usada"  # aprobarla sí
    segundo = propuestas.guardar(conn, "linkedin", "Otro", "x", [3])
    assert segundo.ruta.name.startswith("linkedin-2-")


def test_ideas_no_marcan_usada_y_formatos_por_historia_exigen_una(conn):
    ideas = propuestas.guardar(conn, "ideas-didacticas", "Ideas", "## Idea 1", [1, 2])
    propuestas.cambiar_estado(conn, ideas.ruta, "aprobada", "manual")
    assert historias.ver(conn, 1)[0]["estado"] == "nueva"
    with pytest.raises(propuestas.PropuestaInvalida, match="exactamente una"):
        propuestas.guardar(conn, "bomba", "X", "y", [1, 2])
    with pytest.raises(propuestas.PropuestaInvalida, match="--historia"):
        propuestas.contexto(conn, "didactico")


def test_estados_y_no_sobrescribir_lo_aprobado(conn):
    p = propuestas.guardar(conn, "resumen", "Resumen", "v1", [1, 2])
    propuestas.guardar(conn, "resumen", "Resumen", "v2", [1, 2])  # mientras es propuesta, se reemplaza
    assert propuestas.leer(p.ruta).cuerpo.strip() == "v2"
    propuestas.cambiar_estado(conn, p.ruta, "aprobada", "manual")
    with pytest.raises(propuestas.PropuestaInvalida, match="aprobada"):
        propuestas.guardar(conn, "resumen", "Resumen", "v3", [1])
    propuestas.cambiar_estado(conn, p.ruta, "publicada", "web")
    with pytest.raises(propuestas.PropuestaInvalida):
        propuestas.cambiar_estado(conn, p.ruta, "aprobada", "web")
    with pytest.raises(propuestas.PropuestaInvalida, match="publicada"):
        propuestas.editar(p.ruta, "cambio")
    assert [h["estado"] for h in propuestas.leer(p.ruta).meta["historial"]] == ["aprobada", "publicada"]


def test_bombas_sin_propuesta(conn):
    assert propuestas.bombas_sin_propuesta(conn) == [2]
    propuestas.guardar(conn, "bomba", "RCE en NGINX", "Short", [2])
    assert propuestas.bombas_sin_propuesta(conn) == []


def test_resolver_no_sale_de_semanas(conn, tmp_path):
    (tmp_path / "voz.md").write_text("x")
    with pytest.raises(propuestas.PropuestaInvalida):
        propuestas.resolver("voz.md")
    with pytest.raises(propuestas.PropuestaInvalida):
        propuestas.resolver("semanas/../voz.md")


def test_pantalla_de_propuestas(conn):
    p = propuestas.guardar(conn, "linkedin", "Post NGINX", "Texto <script>alert(1)</script> **fuerte**", [2])
    from tn.web.app import app
    cliente = TestClient(app)
    r = cliente.get("/propuestas")
    assert r.status_code == 200 and "Post NGINX" in r.text
    assert "<script>alert" not in r.text and "<strong>fuerte</strong>" in r.text
    r = cliente.post("/propuesta/estado", data={"f": p.relativa, "estado": "aprobada"})
    assert "aprobada" in r.text
    r = cliente.post("/propuesta/editar", data={"f": p.relativa, "cuerpo": "Nuevo texto"})
    assert "Nuevo texto" in r.text
    assert cliente.get("/propuesta", params={"f": "voz.md"}).status_code == 404


def test_regenerar_el_resumen_no_excluye_lo_que_ya_usaba(conn):
    propuestas.guardar(conn, "resumen", "Resumen v1", "v1", [1, 2])
    ctx = propuestas.contexto(conn, "resumen")
    assert {1, 2} <= {h["id"] for h in ctx["historias_candidatas"]}
