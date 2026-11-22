from tn.modelo import ItemRecogido
from tn.prefiltro import prefiltrar
from tn.urls import normalizar_url


def test_quita_seguimiento_fragmento_y_barra_final():
    assert (
        normalizar_url("http://WWW.Example.com/Post/?utm_source=tldrai&b=2&a=1#comentarios")
        == "https://example.com/Post?a=1&b=2"
    )


def test_conserva_parametros_con_significado():
    assert normalizar_url("https://news.ycombinator.com/item?id=42") == "https://news.ycombinator.com/item?id=42"


def test_misma_url_con_distinto_seguimiento_es_igual():
    a = normalizar_url("https://blog.example.com/x?utm_source=tldrai")
    b = normalizar_url("https://blog.example.com/x/?utm_source=tldr&utm_campaign=nov20&fbclid=abc")
    assert a == b


def _item(url, titulo="Titular", fuente="f1"):
    return ItemRecogido(fuente_id=fuente, url=url, titulo=titulo)


def test_prefiltro_descarta_patrocinios_y_duplicados():
    res = prefiltrar([
        _item("https://a.example/1"),
        _item("https://a.example/1?utm_source=x"),  # duplicado tras normalizar
        _item("https://b.example/2", "Compra esto (Sponsor)"),
        _item("https://c.example/3", "Encuesta (TLDR Community)"),
        _item("", "Sin URL"),
        _item("https://d.example/4", "   "),
        _item("https://e.example/5", "Bueno"),
    ])
    assert [f.item.url for f in res.aceptados] == ["https://a.example/1", "https://e.example/5"]
    assert res.descartados == 5


def test_misma_url_en_fuentes_distintas_no_es_duplicado_del_prefiltro():
    res = prefiltrar([_item("https://a.example/1", fuente="f1"), _item("https://a.example/1", fuente="f2")])
    assert len(res.aceptados) == 2
    assert res.aceptados[0].url_normalizada == res.aceptados[1].url_normalizada


def test_conservar_fragmento_distingue_entradas_de_un_changelog():
    a = "https://aistudio.google.com/docs/changelog#2026-11-19-genie-4"
    b = "https://aistudio.google.com/docs/changelog#2026-11-18-tool-retrieval"
    assert normalizar_url(a) == normalizar_url(b)
    assert normalizar_url(a, conservar_fragmento=True) != normalizar_url(b, conservar_fragmento=True)
