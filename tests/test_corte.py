from tn import corte


def _palabras(frases, pausa=0.3, inicio=1.0):
    """Construye palabras con tiempos: cada frase tras `pausa` segundos de silencio."""
    res, t = [], inicio
    for frase in frases:
        for w in frase.split():
            res.append({"palabra": w, "inicio": round(t, 3), "fin": round(t + 0.3, 3), "confianza": 0.9})
            t += 0.35
        t += pausa
    return res


def test_se_queda_la_ultima_toma_y_quita_las_marcadas_como_error():
    ps = _palabras([
        "Esta semana ha salido Postgres.",
        "Esta semana ha salido, perdón.",
        "Esta semana ha salido Postgres diecinueve.",
        "Y OpenAI lanza GPT.",
    ], pausa=1.0)
    r = corte.cortar({"palabras": ps})
    decisiones = [(u["texto"], u["decision"]) for u in r["unidades"]]
    assert decisiones[0][1] == "otra-toma"
    assert decisiones[1][1] == "error"
    assert decisiones[2][1] == "queda" and decisiones[3][1] == "queda"
    assert r["duracion_corte"] < r["duracion_grabacion"]


def test_arranque_cortado_cuenta_como_otra_toma():
    ps = _palabras(["Por otro lado tenemos", "Por otro lado tenemos que hablar de Google."], pausa=0.9)
    us = corte.decidir(corte.unidades(ps))
    assert [u.decision for u in us] == ["otra-toma", "queda"]


def test_frases_distintas_se_quedan_aunque_empiecen_parecido():
    ps = _palabras(["Esto es solamente una prueba.", "Esto es todo lo que hemos visto hoy."], pausa=0.9)
    us = corte.decidir(corte.unidades(ps))
    assert [u.decision for u in us] == ["queda", "queda"]


def test_silencios_largos_se_acortan_y_muletillas_sueltas_fuera():
    ps = _palabras(["Hola a todos."], inicio=0.5)
    ps += [{"palabra": "eh", "inicio": ps[-1]["fin"] + 0.5, "fin": ps[-1]["fin"] + 0.8, "confianza": 0.5}]
    ps += _palabras(["Seguimos con lo siguiente."], inicio=ps[-1]["fin"] + 2.0)
    r = corte.cortar({"palabras": ps})
    huecos = [b["inicio"] - a["fin"] for a, b in zip(r["tramos"], r["tramos"][1:])]
    assert all(h > 0 for h in huecos)
    total_palabras = sum(p["fin"] - p["inicio"] for p in ps if p["palabra"] != "eh")
    assert r["duracion_corte"] < total_palabras + 1.5  # sin los 2 s de silencio ni la muletilla


def test_tiempo_del_corte():
    ts = [corte.Tramo(1.0, 3.0, [0]), corte.Tramo(5.0, 6.0, [1])]
    assert corte.a_tiempo_corte(2.0, ts) == 1.0
    assert corte.a_tiempo_corte(5.5, ts) == 2.5
    assert corte.a_tiempo_corte(4.0, ts) is None


GUION = """# Título

## Título y miniatura
- Título: algo

## Gancho · literal · ~30 s
Esta semana NGINX tiene dos fallos críticos.

## 1. NGINX: dos fallos críticos · ~1:45
**Entrada · literal:** Wiz ha encontrado dos fallos en HTTP/2 de NGINX.
**Visual:** captura

## 2. PostgreSQL 19 · ~1:45
**Entrada · literal:** Postgres diecinueve trae REPACK concurrente.

## Cierre · literal
Nos vemos la semana que viene.

## Descripción de YouTube
nada
"""


def test_bloques_del_guion_en_orden_y_en_el_tiempo_del_corte():
    assert [b["titulo"] for b in corte.bloques_guion(GUION)] == [
        "Gancho", "1. NGINX: dos fallos críticos", "2. PostgreSQL 19", "Cierre"]
    ps = _palabras([
        "Esta semana NGINX tiene dos fallos críticos.",
        "Wiz ha encontrado dos fallos en HTTP/2 de NGINX.",
        "Postgres diecinueve trae REPACK concurrente.",
        "Nos vemos la semana que viene.",
    ], pausa=1.5)
    r = corte.cortar({"palabras": ps}, GUION)
    titulos = [b["titulo"] for b in r["bloques"]]
    assert titulos == ["Gancho", "1. NGINX: dos fallos críticos", "2. PostgreSQL 19", "Cierre"]
    inicios = [b["inicio"] for b in r["bloques"]]
    assert inicios == sorted(inicios) and len(set(inicios)) == 4


def test_ajustes_a_mano():
    ps = _palabras(["Por otro lado tenemos", "Por otro lado tenemos que hablar de Google.", "Fin."], pausa=0.9)
    r = corte.cortar({"palabras": ps}, ajustes={"mantener": [0], "quitar": [2]})
    assert [u["decision"] for u in r["unidades"]] == ["queda", "queda", "quitada"]
