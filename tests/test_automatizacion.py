import plistlib
import tarfile

import httpx
import pytest

from tn import avisos, config, db, horarios, perfil, respaldo


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    monkeypatch.setenv("TN_HOME", str(tmp_path))
    monkeypatch.setenv("TN_DB", str(tmp_path / "data" / "t.db"))
    monkeypatch.setenv("TN_RESPALDOS", str(tmp_path / "respaldos"))
    for k in ("TN_TELEGRAM_TOKEN", "TN_TELEGRAM_CHAT"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "perfil-editorial.md").write_text("# Perfil\n\nIA primero.\n")
    return tmp_path


def test_env_carga_sin_pisar_y_guarda(raiz, monkeypatch):
    (raiz / ".env").write_text("# comentario\nTN_TELEGRAM_TOKEN=abc\nTN_MODELO='haiku'\n")
    monkeypatch.setenv("TN_MODELO", "sonnet")
    config.cargar_env()
    import os
    assert os.environ["TN_TELEGRAM_TOKEN"] == "abc" and os.environ["TN_MODELO"] == "sonnet"
    config.guardar_en_env("TN_TELEGRAM_CHAT", "42")
    assert "TN_TELEGRAM_CHAT=42" in (raiz / ".env").read_text()
    assert (raiz / ".env").read_text().count("TN_TELEGRAM_TOKEN") == 1


def test_telegram_sin_configurar_no_falla(raiz):
    assert "sin configurar" in avisos.enviar_telegram("hola")


def test_telegram_trocea_y_envia(raiz, monkeypatch):
    monkeypatch.setenv("TN_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("TN_TELEGRAM_CHAT", "42")
    enviados = []

    def manejador(request):
        enviados.append(request.content.decode())
        return httpx.Response(200, json={"ok": True})

    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    texto = "\n".join("línea larga " * 30 for _ in range(30))  # ~10k caracteres
    assert avisos.enviar_telegram(texto, cliente) is None
    assert len(enviados) >= 3 and all("chat_id=42" in e for e in enviados)


def test_buscar_chat(raiz):
    def manejador(request):
        return httpx.Response(200, json={"result": [{"message": {"chat": {"id": 99, "first_name": "Javi"}}}]})

    assert avisos.buscar_chat("t", httpx.Client(transport=httpx.MockTransport(manejador))) == ("99", "Javi")


def test_respaldo_incluye_db_y_semanas_y_rota(raiz):
    conn = db.conectar(config.ruta_db())
    conn.close()
    (raiz / "semanas" / "2026-11-20").mkdir(parents=True)
    (raiz / "semanas" / "2026-11-20" / "linkedin-1.md").write_text("post")
    archivo = respaldo.respaldar()
    with tarfile.open(archivo) as tar:
        nombres = tar.getnames()
    assert "data/tech-news.db" in nombres and "semanas/2026-11-20/linkedin-1.md" in nombres
    for n in range(20):
        (raiz / "respaldos" / f"tech-news-2020-01-{n + 1:02d}_0000.tar.gz").write_text("x")
    respaldo.respaldar(conservar=5)
    assert len(list((raiz / "respaldos").glob("*.tar.gz"))) == 5


def test_perfil_propuesta_diff_aceptar_y_rechazar(raiz):
    conn = db.conectar(config.ruta_db())
    with pytest.raises(perfil.SinPropuesta):
        perfil.diff()
    perfil.ruta_propuesta().parent.mkdir(parents=True, exist_ok=True)
    perfil.ruta_propuesta().write_text("# Perfil\n\nIA primero. Cripto nunca.\n")
    assert "+IA primero. Cripto nunca." in perfil.diff()
    perfil.aceptar(conn)
    assert "Cripto nunca" in (raiz / "perfil-editorial.md").read_text()
    assert list((raiz / "data").glob("perfil-editorial.*.md"))  # copia del anterior
    assert perfil.ultima_revision(conn) is not None
    perfil.ruta_propuesta().write_text("otra")
    perfil.rechazar(conn)
    assert not perfil.hay_propuesta()


def test_plist_de_cada_tarea(raiz):
    for tarea in horarios.TAREAS:
        p = horarios.generar_plist(tarea)
        plistlib.dumps(p)  # serializable
        assert p["ProgramArguments"][-2:] == ["programado", tarea]
        assert "--project" in p["ProgramArguments"]
        assert "/opt/homebrew/bin" in p["EnvironmentVariables"]["PATH"]
    assert horarios.TAREAS["resumen"]["cuando"]["Weekday"] == 4  # jueves
    assert horarios.cuando_legible(horarios.TAREAS["aviso-paquete"]["cuando"]) == "viernes 08:00"
    assert horarios.cuando_legible(horarios.TAREAS["post-diario"]["cuando"]) == "lun/mar/mié 16:30"


def test_seccion_de_markdown():
    from tn.cli import _seccion
    md = "# T\n\n## Gancho · literal · ~30 s\nHola gancho\n\n## 1. Bloque\notro"
    assert _seccion(md, "Gancho") == "Hola gancho"
    assert _seccion(md, "Short") == ""
