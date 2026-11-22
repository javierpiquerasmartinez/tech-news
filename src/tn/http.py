"""Cliente HTTP del Recolector: educado con cada host (pausas y reintento ante 429)."""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; tn-recolector/0.1)"

# Pausa mínima entre peticiones al mismo host. TLDR responde 429 a ~1 req/s.
PAUSAS_POR_HOST = {"tldr.tech": 3.0}


class Http:
    def __init__(self, timeout: float = 20.0, pausas: dict[str, float] | None = None, dormir=time.sleep):
        self._cliente = httpx.Client(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self._pausas = PAUSAS_POR_HOST if pausas is None else pausas
        self._ultima: dict[str, float] = {}
        self._dormir = dormir

    def _esperar_turno(self, host: str) -> None:
        pausa = self._pausas.get(host, 0.0)
        if pausa and host in self._ultima:
            falta = pausa - (time.monotonic() - self._ultima[host])
            if falta > 0:
                self._dormir(falta)
        self._ultima[host] = time.monotonic()

    def get(self, url: str) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        for intento in range(2):
            self._esperar_turno(host)
            r = self._cliente.get(url)
            if r.status_code == 429 and intento == 0:
                self._dormir(15.0)
                continue
            r.raise_for_status()
            return r
        r.raise_for_status()
        return r

    def texto(self, url: str) -> str:
        return self.get(url).text

    def json(self, url: str):
        return self.get(url).json()

    def cerrar(self) -> None:
        self._cliente.close()
