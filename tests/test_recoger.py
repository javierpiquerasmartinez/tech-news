from tn import db
from tn.modelo import Fuente, ItemRecogido
from tn.recoger import recoger

BUENA = Fuente(id="buena", nombre="Buena", grupo="x", tipo="falso", url="https://buena")
OTRA = Fuente(id="otra", nombre="Otra", grupo="x", tipo="falso", url="https://otra")
ROTA = Fuente(id="rota", nombre="Rota", grupo="x", tipo="roto", url="https://rota")
EXPLORADA = Fuente(id="anthropic", nombre="Anthropic", grupo="x", tipo="explorador")
PAUSADA = Fuente(id="pausada", nombre="Pausada", grupo="x", tipo="falso", activa=False)


def falso(fuente, desde, http):
    return [
        ItemRecogido(fuente_id=fuente.id, url="https://a.example/1?utm_source=x", titulo="Uno"),
        ItemRecogido(fuente_id=fuente.id, url="https://a.example/2", titulo="Dos"),
        ItemRecogido(fuente_id=fuente.id, url="https://a.example/3", titulo="Anuncio (Sponsor)"),
    ]


def roto(fuente, desde, http):
    raise ConnectionError("timeout")


COLECTORES = {"falso": falso, "roto": roto}


def _conn(tmp_path):
    return db.conectar(tmp_path / "t.db")


def test_recoger_dos_veces_no_duplica(tmp_path):
    conn = _conn(tmp_path)
    r1 = recoger(conn, [BUENA], origen="manual", http=None, colectores=COLECTORES)
    r2 = recoger(conn, [BUENA], origen="manual", http=None, colectores=COLECTORES)
    assert r1.nuevos == 2 and r2.nuevos == 0
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2
    assert r1.fuentes[0].descartados == 1


def test_una_fuente_rota_no_tumba_la_ejecucion(tmp_path):
    conn = _conn(tmp_path)
    res = recoger(conn, [ROTA, BUENA], origen="horario", http=None, colectores=COLECTORES)
    assert res.estado == "con_errores"
    assert res.nuevos == 2
    rota = next(f for f in res.fuentes if f.fuente_id == "rota")
    assert "timeout" in rota.error
    # El cursor de la rota no avanza; el de la buena sí.
    assert db.leer_cursor(conn, "rota") is None
    assert db.leer_cursor(conn, "buena") is not None


def test_todas_rotas_es_fallida(tmp_path):
    res = recoger(_conn(tmp_path), [ROTA], origen="manual", http=None, colectores=COLECTORES)
    assert res.estado == "fallida"


def test_ignora_explorador_y_pausadas_y_respeta_solo(tmp_path):
    conn = _conn(tmp_path)
    res = recoger(conn, [BUENA, OTRA, EXPLORADA, PAUSADA], origen="manual", http=None,
                  colectores=COLECTORES, solo={"otra"})
    assert [f.fuente_id for f in res.fuentes] == ["otra"]


def test_queda_registrada_la_ejecucion(tmp_path):
    conn = _conn(tmp_path)
    res = recoger(conn, [ROTA, BUENA], origen="claude", http=None, colectores=COLECTORES)
    [fila] = db.ultimas_ejecuciones(conn)
    assert fila["id"] == res.ejecucion_id
    assert fila["origen"] == "claude"
    assert fila["estado"] == "con_errores"
    assert fila["nuevos"] == 2 and fila["errores"] == 1 and fila["fuentes"] == 2
    assert fila["fin"] is not None


def test_misma_url_desde_dos_fuentes_queda_agrupada(tmp_path):
    conn = _conn(tmp_path)
    recoger(conn, [BUENA, OTRA], origen="manual", http=None, colectores=COLECTORES)
    grupo = conn.execute(
        "SELECT fuentes, items FROM grupos_url WHERE url_normalizada = 'https://a.example/1'"
    ).fetchone()
    assert (grupo["fuentes"], grupo["items"]) == (2, 2)
