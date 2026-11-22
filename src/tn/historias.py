"""Historias: agrupar Items, puntuarlas y las correcciones de la persona editora.

El Editor (agente) no escribe en la base de datos: pide `pendientes()` y devuelve un lote
de decisiones que aplica `aplicar_lote()`. Las correcciones humanas pasan por las
funciones de abajo y quedan registradas en `decisiones` (alimentan `tn perfil revisar`).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from tn.db import _iso, ahora

# Una Historia sigue abierta (acepta Items) 7 días desde su último Item.
VENTANA_ABIERTA = timedelta(days=7)
ESTADOS_VISIBLES = ("nueva", "destacada", "descartada", "usada")
AREAS = ("ia", "desarrollo", "seguridad", "cloud-devops", "industria", "otros")
PUNTUACIONES = {"urgencia": "just_urgencia", "valor_didactico": "just_didactico", "peso_semanal": "just_peso"}
LONGITUD_RESUMEN_PENDIENTE = 280


class LoteInvalido(ValueError):
    pass


class AccionInvalida(ValueError):
    pass


# --- Lo que ve el Editor ---------------------------------------------------------


def pendientes(conn: sqlite3.Connection, limite: int = 120, momento: datetime | None = None) -> dict:
    """Items sin Historia ni marca de ruido, agrupados por URL, más las Historias abiertas."""
    momento = momento or ahora()
    filas = conn.execute(
        """
        SELECT i.id, i.fuente_id, i.url_normalizada, i.titulo, i.resumen, i.seccion, i.publicado_en
        FROM items i
        WHERE i.id NOT IN (SELECT item_id FROM historia_items)
          AND i.id NOT IN (SELECT item_id FROM items_ruido)
        ORDER BY i.url_normalizada, i.id
        """
    ).fetchall()
    grupos: dict[str, list[dict]] = {}
    for f in filas:
        grupos.setdefault(f["url_normalizada"], []).append(
            {
                "id": f["id"],
                "fuente": f["fuente_id"],
                "titulo": f["titulo"],
                "resumen": (f["resumen"] or "")[:LONGITUD_RESUMEN_PENDIENTE] or None,
                "seccion": f["seccion"],
                "publicado": (f["publicado_en"] or "")[:10] or None,
            }
        )
    # Los enlaces citados por más Fuentes primero: son los que más probablemente importan.
    ordenados = sorted(grupos.items(), key=lambda kv: (-len({i["fuente"] for i in kv[1]}), kv[1][0]["id"]))
    lote, total_items = [], 0
    for url, items in ordenados:
        if total_items and total_items + len(items) > limite:
            break
        lote.append({"url": url, "items": items})
        total_items += len(items)
    return {
        "grupos": lote,
        "items_en_este_lote": total_items,
        "items_pendientes_total": len(filas),
        "historias_abiertas": historias_abiertas(conn, momento),
    }


def historias_abiertas(conn: sqlite3.Connection, momento: datetime | None = None) -> list[dict]:
    corte = _iso((momento or ahora()) - VENTANA_ABIERTA)
    filas = conn.execute(
        "SELECT id, titulo, resumen, area, estado, urgencia, valor_didactico, peso_semanal, ultimo_item_en "
        "FROM historias WHERE estado != 'fusionada' AND ultimo_item_en >= ? ORDER BY id",
        (corte,),
    ).fetchall()
    return [dict(f) for f in filas]


# --- Lo que decide el Editor ------------------------------------------------------


def _entero(valor, campo: str) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool) or not 0 <= valor <= 10:
        raise LoteInvalido(f"{campo} debe ser un entero entre 0 y 10 (recibido {valor!r})")
    return valor


def _puntuaciones(d: dict, donde: str, obligatorias: bool) -> dict:
    res = {}
    for campo, just in PUNTUACIONES.items():
        if campo in d:
            res[campo] = _entero(d[campo], f"{donde}.{campo}")
            texto = (d.get(just) or "").strip()
            if not texto:
                raise LoteInvalido(f"{donde}: falta {just} (una línea que justifique {campo})")
            res[just] = texto
        elif obligatorias:
            raise LoteInvalido(f"{donde}: falta {campo}")
    return res


def _items_libres(conn: sqlite3.Connection, ids, donde: str, ya_usados: set[int]) -> list[int]:
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise LoteInvalido(f"{donde}: items debe ser una lista de ids")
    for i in ids:
        if i in ya_usados:
            raise LoteInvalido(f"{donde}: el Item {i} aparece dos veces en el lote")
        fila = conn.execute(
            "SELECT (SELECT 1 FROM items WHERE id = ?) AS existe, "
            "(SELECT 1 FROM historia_items WHERE item_id = ?) AS asignado, "
            "(SELECT 1 FROM items_ruido WHERE item_id = ?) AS ruido",
            (i, i, i),
        ).fetchone()
        if not fila["existe"]:
            raise LoteInvalido(f"{donde}: el Item {i} no existe")
        if fila["asignado"] or fila["ruido"]:
            raise LoteInvalido(f"{donde}: el Item {i} ya está revisado")
        ya_usados.add(i)
    return ids


def _ultimo_item(conn: sqlite3.Connection, ids: list[int], por_defecto: str) -> str:
    fila = conn.execute(
        f"SELECT MAX(COALESCE(publicado_en, recogido_en)) AS m FROM items WHERE id IN ({','.join('?' * len(ids))})",
        ids,
    ).fetchone()
    return max(fila["m"] or por_defecto, por_defecto) if ids else por_defecto


def aplicar_lote(conn: sqlite3.Connection, lote: dict, ejecucion_id: int | None = None) -> dict:
    """Aplica un lote del Editor de forma atómica: todo o nada.

    Formato:
      {"nuevas":  [{titulo, resumen, area, items:[ids], urgencia, just_urgencia,
                    valor_didactico, just_didactico, peso_semanal, just_peso,
                    bomba?: bool, continua_a?: id}],
       "anadir":  [{historia: id, items:[ids], + puntuaciones opcionales, bomba?}],
       "ruido":   [ids]}
    """
    if not isinstance(lote, dict):
        raise LoteInvalido("el lote debe ser un objeto JSON")
    desconocidas = set(lote) - {"nuevas", "anadir", "ruido"}
    if desconocidas:
        raise LoteInvalido(f"claves desconocidas en el lote: {', '.join(sorted(desconocidas))}")
    momento = _iso(ahora())
    usados: set[int] = set()
    abiertas = {h["id"] for h in historias_abiertas(conn)}
    creadas, ampliadas = [], []

    try:
        for n, h in enumerate(lote.get("nuevas", []), start=1):
            donde = f"nuevas[{n}]"
            titulo = (h.get("titulo") or "").strip()
            if not titulo:
                raise LoteInvalido(f"{donde}: falta titulo")
            area = h.get("area") or "otros"
            if area not in AREAS:
                raise LoteInvalido(f"{donde}: area debe ser una de {', '.join(AREAS)}")
            ids = _items_libres(conn, h.get("items"), donde, usados)
            if not ids:
                raise LoteInvalido(f"{donde}: una Historia necesita al menos un Item")
            p = _puntuaciones(h, donde, obligatorias=True)
            continua_a = h.get("continua_a")
            if continua_a is not None and not conn.execute("SELECT 1 FROM historias WHERE id = ?", (continua_a,)).fetchone():
                raise LoteInvalido(f"{donde}: continua_a={continua_a} no existe")
            cur = conn.execute(
                """INSERT INTO historias (titulo, resumen, area, continua_a, urgencia, just_urgencia,
                       valor_didactico, just_didactico, peso_semanal, just_peso, es_bomba,
                       creada_en, actualizada_en, ultimo_item_en, ejecucion_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (titulo, (h.get("resumen") or "").strip() or None, area, continua_a,
                 p["urgencia"], p["just_urgencia"], p["valor_didactico"], p["just_didactico"],
                 p["peso_semanal"], p["just_peso"], int(bool(h.get("bomba"))),
                 momento, momento, _ultimo_item(conn, ids, ""), ejecucion_id),
            )
            hid = int(cur.lastrowid)
            conn.executemany("INSERT INTO historia_items (historia_id, item_id) VALUES (?, ?)", [(hid, i) for i in ids])
            creadas.append(hid)

        for n, a in enumerate(lote.get("anadir", []), start=1):
            donde = f"anadir[{n}]"
            hid = a.get("historia")
            if hid not in abiertas:
                raise LoteInvalido(f"{donde}: la Historia {hid} no existe o ya no está abierta")
            ids = _items_libres(conn, a.get("items"), donde, usados)
            p = _puntuaciones(a, donde, obligatorias=False)
            sets = ", ".join(f"{k} = ?" for k in p) + (", " if p else "")
            actual = conn.execute("SELECT ultimo_item_en, es_bomba FROM historias WHERE id = ?", (hid,)).fetchone()
            bomba = int(bool(a.get("bomba"))) or actual["es_bomba"]
            conn.execute(
                f"UPDATE historias SET {sets}es_bomba = ?, actualizada_en = ?, ultimo_item_en = ? WHERE id = ?",
                (*p.values(), bomba, momento, _ultimo_item(conn, ids, actual["ultimo_item_en"]), hid),
            )
            conn.executemany("INSERT INTO historia_items (historia_id, item_id) VALUES (?, ?)", [(hid, i) for i in ids])
            ampliadas.append(hid)

        ruido = _items_libres(conn, lote.get("ruido", []), "ruido", usados)
        conn.executemany("INSERT INTO items_ruido (item_id, ejecucion_id) VALUES (?, ?)", [(i, ejecucion_id) for i in ruido])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"historias_creadas": creadas, "historias_ampliadas": ampliadas, "items_ruido": len(ruido)}


# --- Lectura -----------------------------------------------------------------------


def listar(
    conn: sqlite3.Connection,
    *,
    desde: datetime | None = None,
    estados: tuple[str, ...] = ("nueva", "destacada", "usada"),
    solo_bombas: bool = False,
    orden: str = "peso_semanal",
    limite: int = 50,
) -> list[sqlite3.Row]:
    if orden not in PUNTUACIONES:
        raise AccionInvalida(f"orden debe ser uno de {', '.join(PUNTUACIONES)}")
    condiciones = [f"h.estado IN ({','.join('?' * len(estados))})"]
    params: list = list(estados)
    if desde:
        condiciones.append("h.ultimo_item_en >= ?")
        params.append(_iso(desde))
    if solo_bombas:
        condiciones.append("h.es_bomba = 1")
    params.append(limite)
    return conn.execute(
        f"""SELECT h.*, COUNT(hi.item_id) AS n_items,
                   COUNT(DISTINCT i.fuente_id) AS n_fuentes
            FROM historias h
            LEFT JOIN historia_items hi ON hi.historia_id = h.id
            LEFT JOIN items i ON i.id = hi.item_id
            WHERE {' AND '.join(condiciones)}
            GROUP BY h.id
            ORDER BY h.es_bomba DESC, h.estado = 'destacada' DESC, h.{orden} DESC, h.id DESC
            LIMIT ?""",
        params,
    ).fetchall()


def ver(conn: sqlite3.Connection, hid: int) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
    h = conn.execute("SELECT * FROM historias WHERE id = ?", (hid,)).fetchone()
    if not h:
        raise AccionInvalida(f"No existe la Historia {hid}")
    items = conn.execute(
        "SELECT i.* FROM items i JOIN historia_items hi ON hi.item_id = i.id WHERE hi.historia_id = ? ORDER BY i.publicado_en, i.id",
        (hid,),
    ).fetchall()
    return h, items


# --- Correcciones de la persona editora ------------------------------------------


def _historia(conn: sqlite3.Connection, hid: int) -> sqlite3.Row:
    h = conn.execute("SELECT * FROM historias WHERE id = ?", (hid,)).fetchone()
    if not h or h["estado"] == "fusionada":
        raise AccionInvalida(f"No existe la Historia {hid}")
    return h


def _decision(conn: sqlite3.Connection, hid: int, accion: str, detalle: dict, origen: str) -> None:
    conn.execute(
        "INSERT INTO decisiones (historia_id, accion, detalle, origen, momento) VALUES (?, ?, ?, ?, ?)",
        (hid, accion, json.dumps(detalle, ensure_ascii=False), origen, _iso(ahora())),
    )


def _cambiar_estado(conn, hid: int, nuevo: str, *, permitido_desde: tuple[str, ...], extra: dict | None = None) -> sqlite3.Row:
    h = _historia(conn, hid)
    if h["estado"] not in permitido_desde:
        raise AccionInvalida(f"La Historia {hid} está {h['estado']}: no se puede pasar a {nuevo}")
    campos = {"estado": nuevo, "actualizada_en": _iso(ahora()), **(extra or {})}
    conn.execute(
        f"UPDATE historias SET {', '.join(f'{k} = ?' for k in campos)} WHERE id = ?",
        (*campos.values(), hid),
    )
    return h


def descartar(conn: sqlite3.Connection, hid: int, motivo: str | None, origen: str) -> None:
    h = _cambiar_estado(conn, hid, "descartada", permitido_desde=("nueva", "destacada"),
                        extra={"motivo_descarte": motivo})
    _decision(conn, hid, "descartar", {"motivo": motivo, "estado_anterior": h["estado"]}, origen)
    conn.commit()


def destacar(conn: sqlite3.Connection, hid: int, origen: str) -> None:
    # También una usada: puede ir en un post y además en el Resumen semanal.
    _cambiar_estado(conn, hid, "destacada", permitido_desde=("nueva", "usada"))
    _decision(conn, hid, "destacar", {}, origen)
    conn.commit()


def restaurar(conn: sqlite3.Connection, hid: int, origen: str) -> None:
    h = _cambiar_estado(conn, hid, "nueva", permitido_desde=("descartada", "destacada"),
                        extra={"motivo_descarte": None})
    _decision(conn, hid, "restaurar", {"estado_anterior": h["estado"]}, origen)
    conn.commit()


def marcar_usada(conn: sqlite3.Connection, hid: int) -> None:
    """La usa el Redactor al construir una Propuesta. No es una decisión de criterio."""
    _cambiar_estado(conn, hid, "usada", permitido_desde=("nueva", "destacada", "usada"))
    conn.commit()


def puntuar(conn: sqlite3.Connection, hid: int, cambios: dict[str, int], motivo: str | None, origen: str) -> None:
    h = _historia(conn, hid)
    if not cambios:
        raise AccionInvalida("Indica al menos una puntuación")
    antes, sets, params = {}, [], []
    for campo, valor in cambios.items():
        if campo not in PUNTUACIONES:
            raise AccionInvalida(f"Puntuación desconocida: {campo}")
        try:
            _entero(valor, campo)
        except LoteInvalido as e:
            raise AccionInvalida(str(e)) from None
        antes[campo] = h[campo]
        sets += [f"{campo} = ?", f"{PUNTUACIONES[campo]} = ?"]
        params += [valor, f"Corregida por la persona editora{': ' + motivo if motivo else ''}"]
    conn.execute(
        f"UPDATE historias SET {', '.join(sets)}, actualizada_en = ? WHERE id = ?",
        (*params, _iso(ahora()), hid),
    )
    _decision(conn, hid, "puntuar", {"antes": antes, "despues": cambios, "motivo": motivo}, origen)
    conn.commit()


def fusionar(conn: sqlite3.Connection, destino: int, origen_id: int, origen: str) -> None:
    """Mueve los Items de `origen_id` a `destino`; `origen_id` deja de verse."""
    if destino == origen_id:
        raise AccionInvalida("No se puede fusionar una Historia consigo misma")
    d, o = _historia(conn, destino), _historia(conn, origen_id)
    conn.execute("UPDATE historia_items SET historia_id = ? WHERE historia_id = ?", (destino, origen_id))
    momento = _iso(ahora())
    conn.execute(
        "UPDATE historias SET urgencia = MAX(urgencia, ?), valor_didactico = MAX(valor_didactico, ?), "
        "peso_semanal = MAX(peso_semanal, ?), es_bomba = MAX(es_bomba, ?), "
        "ultimo_item_en = MAX(ultimo_item_en, ?), actualizada_en = ? WHERE id = ?",
        (o["urgencia"], o["valor_didactico"], o["peso_semanal"], o["es_bomba"], o["ultimo_item_en"], momento, destino),
    )
    conn.execute("UPDATE historias SET estado = 'fusionada', fusionada_en = ?, actualizada_en = ? WHERE id = ?",
                 (destino, momento, origen_id))
    _decision(conn, destino, "fusionar", {"absorbe": origen_id, "titulo_absorbida": o["titulo"], "titulo": d["titulo"]}, origen)
    conn.commit()


def separar(conn: sqlite3.Connection, hid: int, item_ids: list[int], titulo: str, origen: str) -> int:
    """Saca `item_ids` de la Historia `hid` a una Historia nueva con las mismas puntuaciones."""
    h, items = ver(conn, hid)
    actuales = {i["id"] for i in items}
    if not item_ids or not set(item_ids) <= actuales:
        raise AccionInvalida(f"Los Items deben pertenecer a la Historia {hid} (tiene: {sorted(actuales)})")
    if set(item_ids) == actuales:
        raise AccionInvalida("No se pueden separar todos los Items: renombra la Historia en su lugar")
    momento = _iso(ahora())
    cur = conn.execute(
        """INSERT INTO historias (titulo, area, urgencia, just_urgencia, valor_didactico, just_didactico,
               peso_semanal, just_peso, creada_en, actualizada_en, ultimo_item_en)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (titulo, h["area"], h["urgencia"], "Heredada al separar de #%d" % hid, h["valor_didactico"],
         "Heredada al separar de #%d" % hid, h["peso_semanal"], "Heredada al separar de #%d" % hid,
         momento, momento, _ultimo_item(conn, item_ids, "")),
    )
    nueva = int(cur.lastrowid)
    conn.executemany("UPDATE historia_items SET historia_id = ? WHERE item_id = ?", [(nueva, i) for i in item_ids])
    _decision(conn, hid, "separar", {"items": item_ids, "nueva": nueva, "titulo_nueva": titulo}, origen)
    conn.commit()
    return nueva
