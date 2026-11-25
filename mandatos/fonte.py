"""Acesso aos Dados Abertos da Câmara: coleta lenta, identificada e que para diante de qualquer bloqueio."""
import csv
import io
import time
from urllib.parse import urlparse

import requests

from . import config


class Bloqueio(Exception):
    """A coleta deve parar (403/429, CAPTCHA, login ou redirecionamento estranho). Nunca contornar."""


class FalhaColeta(Exception):
    """A fonte não respondeu como esperado depois das retentativas."""


class Cliente:
    def __init__(self, sessao=None):
        self.s = sessao or requests.Session()
        self.s.headers.update({"User-Agent": config.USER_AGENT, "Accept-Language": "pt-BR"})
        self._ultima = 0.0
        self.requisicoes = 0

    def get(self, url):
        erro = None
        for _ in range(config.MAX_RETENTATIVAS + 1):
            espera = config.INTERVALO_S - (time.monotonic() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            self._ultima = time.monotonic()
            self.requisicoes += 1
            try:
                r = self.s.get(url, timeout=config.TIMEOUT_S)
            except requests.RequestException as e:
                erro = repr(e)
                continue
            final = r.url.lower()
            if urlparse(r.url).netloc != config.DOMINIO_PERMITIDO:
                raise Bloqueio(f"redirecionamento para fora do domínio: {url} -> {r.url}")
            if "captcha" in final or "login" in final:
                raise Bloqueio(f"CAPTCHA ou login: {url} -> {r.url}")
            if r.status_code in (403, 429):
                raise Bloqueio(f"HTTP {r.status_code} em {url}")
            if r.status_code >= 500:
                erro = f"HTTP {r.status_code}"
                continue
            if r.status_code != 200:
                raise FalhaColeta(f"HTTP {r.status_code} em {url}")
            return r
        raise FalhaColeta(f"{url}: {erro}")

    def indice(self):
        return self.get(config.INDICE_DADOS_ABERTOS).json()

    def csv(self, url, colunas):
        texto = self.get(url).content.decode("utf-8-sig")
        return ler_csv(texto, colunas, url)


def ler_csv(texto, colunas, origem="csv"):
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    campos = leitor.fieldnames or []
    faltando = [c for c in colunas if c not in campos]
    if colunas is config.COLUNAS_DOCUMENTOS and not any(all(c in campos for c in f) for f in config.FORMATOS_AUTORIA):
        faltando.append("Autores+Ids dos Autores ou Autoria")
    if faltando:
        raise FalhaColeta(f"{origem}: colunas ausentes {faltando}; o formato do CSV mudou")
    return list(leitor)


class ClienteLocal:
    """Lê os arquivos oficiais já baixados (mesmos nomes do site), sem nenhuma requisição.
    Serve para desenvolvimento e testes."""

    def __init__(self, pasta):
        from pathlib import Path
        self.pasta = Path(pasta)
        self.requisicoes = 0

    def indice(self):
        import json
        return json.loads((self.pasta / "dados-abertos.json").read_text(encoding="utf-8"))

    def momento_coleta(self, tz):
        """Horário do download manual = data de modificação mais recente dos arquivos baixados."""
        from datetime import datetime
        arquivos = [f for f in self.pasta.iterdir() if f.suffix in (".csv", ".json")]
        return datetime.fromtimestamp(max(f.stat().st_mtime for f in arquivos), tz).isoformat(timespec="seconds")

    def csv(self, url, colunas):
        arq = self.pasta / url.rsplit("/", 1)[-1]
        if not arq.exists():
            raise FalhaColeta(f"arquivo local ausente: {arq.name}")
        return ler_csv(arq.read_text(encoding="utf-8-sig"), colunas, arq.name)
