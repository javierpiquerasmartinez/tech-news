"""Avisos al móvil (Telegram) y al Mac (notificación del sistema).

Sin configuración de Telegram, los avisos se quedan en la notificación de macOS y en la
salida del comando: nunca hacen fallar una Ejecución.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

import httpx

API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_TELEGRAM = 4000  # el máximo real es 4096 caracteres por mensaje


@dataclass
class ResultadoAviso:
    telegram: bool
    mac: bool
    detalle: str = ""


def _telegram_configurado() -> tuple[str, str] | None:
    token, chat = os.environ.get("TN_TELEGRAM_TOKEN", ""), os.environ.get("TN_TELEGRAM_CHAT", "")
    return (token, chat) if token and chat else None


def _trocear(texto: str) -> list[str]:
    trozos, actual = [], ""
    for parrafo in texto.split("\n"):
        if len(actual) + len(parrafo) + 1 > LIMITE_TELEGRAM and actual:
            trozos.append(actual)
            actual = ""
        actual += parrafo[:LIMITE_TELEGRAM] + "\n"
    return trozos + ([actual] if actual.strip() else [])


def enviar_telegram(texto: str, cliente: httpx.Client | None = None) -> str | None:
    """Envía `texto` (texto plano). Devuelve None si fue bien o el error."""
    conf = _telegram_configurado()
    if not conf:
        return "Telegram sin configurar (TN_TELEGRAM_TOKEN y TN_TELEGRAM_CHAT en .env)"
    token, chat = conf
    c = cliente or httpx.Client(timeout=20)
    try:
        for trozo in _trocear(texto):
            r = c.post(API.format(token=token, metodo="sendMessage"),
                       data={"chat_id": chat, "text": trozo, "disable_web_page_preview": "true"})
            if r.status_code != 200:
                return f"Telegram respondió {r.status_code}: {r.text[:200]}"
    except httpx.HTTPError as e:
        return f"No se pudo contactar con Telegram: {type(e).__name__}"
    finally:
        if cliente is None:
            c.close()
    return None


def notificar_mac(titulo: str, texto: str) -> bool:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')[:240]

    try:
        r = subprocess.run(
            ["osascript", "-e", f'display notification "{esc(texto)}" with title "{esc(titulo)}"'],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def avisar(titulo: str, texto: str) -> ResultadoAviso:
    error = enviar_telegram(f"{titulo}\n\n{texto}")
    mac = notificar_mac(titulo, texto.split("\n", 1)[0])
    return ResultadoAviso(telegram=error is None, mac=mac, detalle=error or "")


def buscar_chat(token: str, cliente: httpx.Client | None = None) -> tuple[str, str] | None:
    """El chat del último mensaje recibido por el bot: (chat_id, nombre)."""
    c = cliente or httpx.Client(timeout=20)
    try:
        r = c.get(API.format(token=token, metodo="getUpdates"))
        r.raise_for_status()
        for u in reversed(r.json().get("result", [])):
            chat = (u.get("message") or u.get("edited_message") or {}).get("chat")
            if chat:
                nombre = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
                return str(chat["id"]), nombre
    finally:
        if cliente is None:
            c.close()
    return None
