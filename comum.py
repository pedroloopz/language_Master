"""Funcoes comuns: download com cache, Commons, gravacao de JSON com limite de tamanho."""
import json
import os
import pathlib
import time
import urllib.parse

import requests

CACHE = pathlib.Path(os.environ.get("CACHE", "cache"))
SAIDA = pathlib.Path(os.environ.get("SAIDA", "saida"))
UA = {"User-Agent": "LanguageMasterDados/1.1 (https://github.com/pedroloopz/language_Master) python-requests"}  # politica de UA da Wikimedia: nome/versao (URL de contato)
LIMITE_JSON = 8 * 1024 * 1024        # 8 MB por arquivo JSON
COMMONS = "https://commons.wikimedia.org/w/api.php"


def log(msg):
    print(msg, flush=True)


def baixar(url, nome=None, tentativas=4):
    """Baixa para cache/ (uma vez so). Devolve o caminho."""
    CACHE.mkdir(parents=True, exist_ok=True)
    destino = CACHE / (nome or urllib.parse.unquote(url.rsplit("/", 1)[-1]).split("?")[0])
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    log(f"baixando {url}")
    for n in range(tentativas):
        try:
            with requests.get(url, headers=UA, stream=True, timeout=120) as r:
                r.raise_for_status()
                tmp = destino.with_suffix(destino.suffix + ".part")
                with open(tmp, "wb") as f:
                    for bloco in r.iter_content(1 << 20):
                        f.write(bloco)
                tmp.rename(destino)
                return destino
        except Exception as e:
            log(f"download falhou ({n + 1}/{tentativas}) {url}: {e}")
            time.sleep(5 * (n + 1))
    raise RuntimeError(f"nao consegui baixar {url}")


def ultima_release(repo, padrao):
    """URL do asset mais recente de um repositorio do GitHub cujo nome contem `padrao`."""
    cab = {**UA}
    if os.environ.get("GITHUB_TOKEN"):
        cab["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=cab, timeout=60)
    r.raise_for_status()
    rel = r.json()
    for a in rel["assets"]:
        if padrao(a["name"]):
            return a["browser_download_url"], rel["tag_name"]
    raise RuntimeError(f"{repo}: nenhum asset casa com o padrao em {rel['tag_name']}")


def commons(params):
    params = {"format": "json", "formatversion": 2, **params}
    for n in range(5):
        try:
            r = requests.get(COMMONS, params=params, headers=UA, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (n + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log(f"Commons falhou ({e}); tentando de novo")
            time.sleep(5 * (n + 1))
    raise RuntimeError("Commons nao respondeu")


def categoria(nome):
    """Todos os arquivos de uma categoria do Commons (nome sem 'Category:')."""
    arquivos, cont = [], {}
    while True:
        j = commons({"action": "query", "list": "categorymembers", "cmtitle": f"Category:{nome}",
                     "cmtype": "file", "cmlimit": 500, **cont})
        arquivos += [m["title"][5:] for m in j["query"]["categorymembers"]]   # tira "File:"
        if "continue" not in j:
            return arquivos
        cont = j["continue"]


def metadados(arquivos):
    """{arquivo: {"url", "autor", "licenca"}} via imageinfo, em lotes de 50."""
    import html
    import re
    out = {}
    for i in range(0, len(arquivos), 50):
        lote = arquivos[i:i + 50]
        j = commons({"action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata",
                     "titles": "|".join("File:" + a for a in lote)})
        for p in j["query"]["pages"]:
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            limpar = lambda k: re.sub(r"<[^>]+>", "", html.unescape(meta.get(k, {}).get("value", ""))).strip()
            out[p["title"][5:]] = {"url": info.get("url"), "autor": limpar("Artist") or "desconhecido",
                                   "licenca": limpar("LicenseShortName") or "ver Commons",
                                   "pagina": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))}
    return out


def gravar_json(nome, dados, dividir_por=None):
    """Grava saida/<nome>.json; se passar de 8 MB, divide pelo campo `dividir_por`
    (ex.: nivel) em <nome>-<valor>.json. Devolve a lista de arquivos gravados."""
    SAIDA.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    if len(texto.encode()) <= LIMITE_JSON or not dividir_por:
        (SAIDA / f"{nome}.json").write_text(texto, encoding="utf-8")
        return [f"{nome}.json"]
    grupos = {}
    for p in dados["palavras"]:
        grupos.setdefault(str(p.get(dividir_por, "outros")).lower().replace(" ", "-"), []).append(p)
    arquivos = []
    for g, lista in grupos.items():
        parte = {k: v for k, v in dados.items() if k != "palavras"} | {"palavras": lista}
        if g != list(grupos)[0]:
            parte.pop("kanji", None)          # kanji vai so no primeiro arquivo
        nomearq = f"{nome}-{g}.json"
        t = json.dumps(parte, ensure_ascii=False, separators=(",", ":"))
        if len(t.encode()) > LIMITE_JSON:
            raise RuntimeError(f"{nomearq} passou de 8 MB mesmo dividido")
        (SAIDA / nomearq).write_text(t, encoding="utf-8")
        arquivos.append(nomearq)
    return arquivos
