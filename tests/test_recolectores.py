from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tn.fuentes import cargar_fuentes
from tn.modelo import Fuente
from tn.recolectores.cisa_kev import parsear_kev
from tn.recolectores.rss import parsear_feed
from tn.recolectores.tldr import ediciones_disponibles, es_edicion, parsear_edicion

FIX = Path(__file__).parent / "fixtures"
AHORA = datetime(2026, 11, 22, 16, 0, tzinfo=UTC)
TLDR_AI = Fuente(id="tldr-ai", nombre="TLDR AI", grupo="tldr", tipo="tldr", slug="ai")


def test_tldr_parsea_edicion_con_secciones():
    html = (FIX / "tldr_edicion.html").read_text()
    items = parsear_edicion(TLDR_AI, html, "https://tldr.tech/ai/2026-11-20", date(2026, 11, 20))
    titulos = [i.titulo for i in items]
    # El parser no filtra patrocinios (eso es del prefiltro), pero quita "(N minute read)".
    assert "Example Labs lanza un modelo nuevo" in titulos
    assert "Por qué los agentes fallan" in titulos
    assert "Compra nuestro producto (Sponsor)" in titulos
    modelo = next(i for i in items if i.titulo.startswith("Example Labs"))
    assert modelo.seccion == "Headlines & Launches"
    assert modelo.resumen.startswith("Example Labs ha publicado un modelo")
    assert modelo.publicado_en == datetime(2026, 11, 20, tzinfo=UTC)
    assert modelo.origen == "https://tldr.tech/ai/2026-11-20"
    assert next(i for i in items if i.titulo.startswith("Por qué")).seccion == "Deep Dives & Analysis"


def test_tldr_detecta_soft_404():
    portada = (FIX / "tldr_portada.html").read_text()
    assert not es_edicion(portada)
    assert parsear_edicion(TLDR_AI, portada, "https://tldr.tech/ai/2026-11-22", date(2026, 11, 22)) == []
    assert es_edicion((FIX / "tldr_edicion.html").read_text())


RSS_TLDR = """<?xml version="1.0"?><rss version="2.0"><channel><title>TLDR AI</title>
<item><title>Hoy</title><link>https://tldr.tech/ai/2026-11-20</link><pubDate>Fri, 20 Nov 2026 00:00:00 GMT</pubDate></item>
<item><title>Ayer</title><link>https://tldr.tech/ai/2026-11-19</link><pubDate>Thu, 19 Nov 2026 00:00:00 GMT</pubDate></item>
<item><title>Viejo</title><link>https://tldr.tech/ai/2026-10-01</link><pubDate>Thu, 01 Oct 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_tldr_ediciones_desde_el_cursor_con_margen():
    desde = datetime(2026, 11, 21, 16, 0, tzinfo=UTC)  # margen de 2 días → desde el 19 a las 16:00
    eds = ediciones_disponibles(TLDR_AI, RSS_TLDR, desde, AHORA)
    assert [d for d, _ in eds] == [date(2026, 11, 20)]


def test_tldr_primera_vez_recoge_la_ultima_semana():
    eds = ediciones_disponibles(TLDR_AI, RSS_TLDR, None, AHORA)
    assert [d for d, _ in eds] == [date(2026, 11, 19), date(2026, 11, 20)]


ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Post &lt;b&gt;nuevo&lt;/b&gt;</title><link href="https://blog.example.com/nuevo"/><updated>2026-11-21T10:00:00Z</updated>
<summary type="html">&lt;p&gt;Resumen   con   espacios&lt;/p&gt;</summary></entry>
<entry><title>Post viejo</title><link href="https://blog.example.com/viejo"/><updated>2026-01-01T10:00:00Z</updated></entry>
</feed>"""


def test_rss_filtra_por_fecha_y_limpia_html():
    f = Fuente(id="blog", nombre="Blog", grupo="x", tipo="rss", url="https://blog.example.com/feed")
    items = parsear_feed(f, ATOM, None, AHORA)
    assert [i.url for i in items] == ["https://blog.example.com/nuevo"]
    assert items[0].titulo == "Post nuevo"
    assert items[0].resumen == "Resumen con espacios"


def test_cisa_kev():
    f = Fuente(id="cisa-kev", nombre="CISA KEV", grupo="seguridad", tipo="cisa-kev", url="https://x")
    hoy = AHORA.date().isoformat()
    viejo = (AHORA - timedelta(days=60)).date().isoformat()
    datos = {"vulnerabilities": [
        {"cveID": "CVE-2026-0001", "vendorProject": "Acme", "product": "Gateway", "vulnerabilityName": "Acme Gateway RCE",
         "dateAdded": hoy, "shortDescription": "Ejecución remota.", "knownRansomwareCampaignUse": "Known"},
        {"cveID": "CVE-2020-0002", "vulnerabilityName": "Vieja", "dateAdded": viejo},
    ]}
    items = parsear_kev(f, datos, None, AHORA)
    assert len(items) == 1
    assert items[0].titulo == "CVE-2026-0001: Acme Gateway RCE"
    assert items[0].url == "https://nvd.nist.gov/vuln/detail/CVE-2026-0001"
    assert items[0].resumen.startswith("[Usada en campañas de ransomware]")


def test_el_catalogo_real_es_valido():
    fuentes = cargar_fuentes(Path(__file__).parents[1] / "fuentes.yaml")
    assert len(fuentes) >= 25
    assert {f.tipo for f in fuentes} <= {"rss", "tldr", "cisa-kev", "explorador"}
