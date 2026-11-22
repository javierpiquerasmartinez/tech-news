import pytest

from tn import db, historias
from tn.modelo import ItemRecogido
from tn.prefiltro import prefiltrar


def _p(u=5, d=5, s=5):
    return {"urgencia": u, "just_urgencia": "j", "valor_didactico": d, "just_didactico": "j",
            "peso_semanal": s, "just_peso": "j"}


@pytest.fixture
def conn(tmp_path):
    c = db.conectar(tmp_path / "t.db")
    eid = db.abrir_ejecucion(c, "recoger", "manual", db.ahora())
    crudos = [
        ItemRecogido(fuente_id="tldr-ai", url="https://a.example/modelo", titulo="Modelo nuevo"),
        ItemRecogido(fuente_id="tldr-tech", url="https://a.example/modelo?utm_source=x", titulo="Modelo nuevo"),
        ItemRecogido(fuente_id="hn", url="https://b.example/prensa", titulo="Cobertura del modelo"),
        ItemRecogido(fuente_id="hn", url="https://c.example/gta", titulo="GTA VI"),
        ItemRecogido(fuente_id="hn", url="https://d.example/cve", titulo="CVE en NGINX"),
    ]
    db.insertar_items(c, eid, prefiltrar(crudos).aceptados, db.ahora())
    c.commit()
    return c


def test_pendientes_agrupa_por_url_y_prioriza_las_citadas_por_mas_fuentes(conn):
    p = historias.pendientes(conn)
    assert p["items_pendientes_total"] == 5
    assert p["grupos"][0]["url"] == "https://a.example/modelo"
    assert len(p["grupos"][0]["items"]) == 2


def test_lote_crea_historias_y_marca_ruido_y_vacia_pendientes(conn):
    res = historias.aplicar_lote(conn, {
        "nuevas": [
            {"titulo": "Sale un modelo", "area": "ia", "items": [1, 2, 3], **_p(8, 6, 9)},
            {"titulo": "RCE en NGINX", "area": "seguridad", "items": [5], **_p(9, 5, 8), "bomba": True},
        ],
        "ruido": [4],
    })
    assert len(res["historias_creadas"]) == 2 and res["items_ruido"] == 1
    assert historias.pendientes(conn)["items_pendientes_total"] == 0
    filas = historias.listar(conn)
    assert filas[0]["titulo"] == "RCE en NGINX"  # las bombas primero
    assert filas[1]["n_items"] == 3 and filas[1]["n_fuentes"] == 3


@pytest.mark.parametrize("lote, error", [
    ({"nuevas": [{"titulo": "X", "items": [1], **_p(11)}]}, "entre 0 y 10"),
    ({"nuevas": [{"titulo": "X", "items": [1], "urgencia": 5}]}, "just_urgencia"),
    ({"nuevas": [{"titulo": "X", "items": [99], **_p()}]}, "no existe"),
    ({"nuevas": [{"titulo": "X", "items": [1], **_p()}], "ruido": [1]}, "dos veces"),
    ({"anadir": [{"historia": 42, "items": [1]}]}, "no está abierta"),
    ({"otra": []}, "claves desconocidas"),
])
def test_lote_invalido_no_aplica_nada(conn, lote, error):
    with pytest.raises(historias.LoteInvalido, match=error):
        historias.aplicar_lote(conn, lote)
    assert conn.execute("SELECT COUNT(*) FROM historias").fetchone()[0] == 0
    assert historias.pendientes(conn)["items_pendientes_total"] == 5


def test_anadir_a_historia_abierta_y_repuntuar(conn):
    [hid] = historias.aplicar_lote(conn, {"nuevas": [{"titulo": "Modelo", "area": "ia", "items": [1], **_p(5, 5, 5)}]})["historias_creadas"]
    historias.aplicar_lote(conn, {"anadir": [{"historia": hid, "items": [2, 3], "urgencia": 9, "just_urgencia": "Se confirma"}]})
    h, items = historias.ver(conn, hid)
    assert len(items) == 3 and h["urgencia"] == 9 and h["just_urgencia"] == "Se confirma"
    assert h["valor_didactico"] == 5


def test_un_item_ya_revisado_no_se_puede_reasignar(conn):
    historias.aplicar_lote(conn, {"ruido": [4]})
    with pytest.raises(historias.LoteInvalido, match="ya está revisado"):
        historias.aplicar_lote(conn, {"nuevas": [{"titulo": "GTA", "items": [4], **_p()}]})


def test_correcciones_quedan_registradas_como_decisiones(conn):
    a, b = historias.aplicar_lote(conn, {"nuevas": [
        {"titulo": "Modelo", "area": "ia", "items": [1, 2], **_p()},
        {"titulo": "Prensa del modelo", "area": "ia", "items": [3], **_p(7, 2, 2)},
    ]})["historias_creadas"]
    historias.fusionar(conn, a, b, "claude")
    h, items = historias.ver(conn, a)
    assert len(items) == 3 and h["urgencia"] == 7  # se queda con la puntuación más alta
    assert [r["id"] for r in historias.listar(conn)] == [a]  # la absorbida no se ve

    historias.puntuar(conn, a, {"valor_didactico": 9}, "da para vídeo", "manual")
    historias.destacar(conn, a, "web")
    historias.restaurar(conn, a, "web")
    historias.descartar(conn, a, "ya está muy contada", "manual")
    assert historias.ver(conn, a)[0]["estado"] == "descartada"
    with pytest.raises(historias.AccionInvalida):
        historias.destacar(conn, a, "manual")  # descartada → destacada no vale; antes hay que restaurar

    acciones = [r["accion"] for r in conn.execute("SELECT accion FROM decisiones ORDER BY id")]
    assert acciones == ["fusionar", "puntuar", "destacar", "restaurar", "descartar"]


def test_separar(conn):
    [hid] = historias.aplicar_lote(conn, {"nuevas": [{"titulo": "Mezcla", "area": "ia", "items": [1, 2, 5], **_p()}]})["historias_creadas"]
    nueva = historias.separar(conn, hid, [5], "RCE en NGINX", "manual")
    assert [i["id"] for i in historias.ver(conn, nueva)[1]] == [5]
    assert [i["id"] for i in historias.ver(conn, hid)[1]] == [1, 2]
    with pytest.raises(historias.AccionInvalida):
        historias.separar(conn, hid, [1, 2], "Todo", "manual")


def test_prefiltro_quita_formularios_de_la_newsletter():
    res = prefiltrar([ItemRecogido(fuente_id="tldr-tech", url="https://x.example",
                                   titulo="Become a founding member of TLDR's AI community (2 minute form)")])
    assert res.aceptados == []
