"""Audio: pronuncia nativa do Wikimedia Commons (Wiktionary e Lingua Libre); para o japones
sem gravacao, voz sintetica do VOICEVOX marcada como "sintetico". Junta tudo em pacotes MP3
de ate 10 MB (~300 palavras) + indice com inicio e fim (ms) de cada palavra no pacote.
"""
import concurrent.futures as cf
import os
import subprocess
import time

import requests

import comum

TAXA = 22050                  # Hz, mono
PAUSA = 0.35                  # s de silencio entre palavras
MAX_SEG = 4.0                 # corta gravacao longa
POR_PACOTE = 300
LIMITE_MP3 = 10 * 1024 * 1024
VOICEVOX = os.environ.get("VOICEVOX_URL", "http://localhost:50021")
VOZ = int(os.environ.get("VOICEVOX_VOZ", "2"))           # 2 = 四国めたん (normal)
CREDITO_VOZ = os.environ.get("VOICEVOX_CREDITO", "VOICEVOX:四国めたん")
LINGUA_LIBRE = {"ja": "Lingua Libre pronunciation-jpn", "de": "Lingua Libre pronunciation-deu"}
FILTRO = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-18:TP=-2")


def palavra_lingua_libre(arquivo):
    """'LL-Q5287 (jpn)-Fulano-猫.wav' -> '猫' (o falante pode ter hifen; a palavra fica no fim)."""
    base = arquivo.rsplit(".", 1)[0]
    return base.rsplit("-", 1)[-1].strip() if base.startswith("LL-") else None


def mapa_lingua_libre(lingua):
    mapa = {}
    for a in comum.categoria(LINGUA_LIBRE[lingua]):
        w = palavra_lingua_libre(a)
        if w:
            mapa.setdefault(w, a)
    comum.log(f"Lingua Libre {lingua}: {len(mapa)} palavras gravadas")
    return mapa


def para_pcm(dados, entrada="pipe:0"):
    """Qualquer audio -> PCM 16 bits mono 22050 Hz, sem silencio nas pontas, ate MAX_SEG."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", entrada, "-t", str(MAX_SEG + 1), "-af", FILTRO,
                        "-t", str(MAX_SEG), "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "pipe:1"],
                       input=dados, capture_output=True, check=True)
    return r.stdout


RECUSAS = {"429": 0, "erro": 0}          # so para o log de progresso


def baixar_nativo(url):
    for n in range(4):
        try:
            r = requests.get(url, headers=comum.UA, timeout=60)
            if r.status_code == 429:
                RECUSAS["429"] += 1
                time.sleep(float(r.headers.get("Retry-After") or 10 * (n + 1)))
                continue
            r.raise_for_status()
            return para_pcm(r.content)
        except Exception:
            RECUSAS["erro"] += 1
            time.sleep(3 * (n + 1))
    return None


def sintetizar(texto):
    q = requests.post(f"{VOICEVOX}/audio_query", params={"text": texto, "speaker": VOZ}, timeout=60)
    q.raise_for_status()
    w = requests.post(f"{VOICEVOX}/synthesis", params={"speaker": VOZ}, json=q.json(), timeout=120)
    w.raise_for_status()
    return para_pcm(w.content)


def anexar_audio(dados, lingua, sintetico=False):
    """Escolhe o arquivo nativo de cada palavra, baixa, converte e (ja) sintetiza o que faltar.
    Devolve {id: (pcm, info)}; info = tipo/autor/licenca/fonte."""
    palavras = dados["palavras"]
    ll = mapa_lingua_libre(lingua)
    escolha = {}
    for p in palavras:
        chaves = [p["palavra"]] if lingua == "de" else [p["escrita"], p["leitura"]]
        arq = next(iter(p.pop("audios_wiktionary", []) or []), None) or next((ll[k] for k in chaves if k in ll), None)
        if arq:
            escolha[p["id"]] = arq
    meta = comum.metadados(sorted(set(escolha.values())))
    sons = {}

    def um(item):
        pid, arq = item
        m = meta.get(arq) or {}
        if not m.get("url"):
            return pid, None
        pcm = baixar_nativo(m["url"])
        return pid, (pcm, {"tipo": "nativo", "arquivo": arq, "autor": m["autor"], "licenca": m["licenca"],
                           "pagina": m["pagina"]}) if pcm else None

    comum.log(f"{lingua}: baixando {len(escolha)} gravacoes nativas")
    with cf.ThreadPoolExecutor(6) as ex:
        for n, (pid, r) in enumerate(ex.map(um, escolha.items()), 1):
            if r:
                sons[pid] = r
            if n % 500 == 0:
                comum.log(f"{lingua}: {n}/{len(escolha)} gravacoes processadas, {len(sons)} ok, "
                         f"recusas 429: {RECUSAS['429']}, erros: {RECUSAS['erro']}")
    comum.log(f"{lingua}: audio nativo para {len(sons)} de {len(palavras)} palavras")
    if sintetico:
        faltam = [p for p in palavras if p["id"] not in sons]
        feitos = 0
        for p in faltam:
            try:
                sons[p["id"]] = (sintetizar(p["escrita"] if p["escrita"] else p["leitura"]),
                                 {"tipo": "sintetico", "autor": CREDITO_VOZ, "licenca": "termos do VOICEVOX e da voz"})
                feitos += 1
                if feitos % 500 == 0:
                    comum.log(f"{lingua}: {feitos}/{len(faltam)} sinteticos")
            except Exception as e:
                comum.log(f"VOICEVOX falhou em {p['id']}: {e}")
        comum.log(f"{lingua}: audio sintetico para {feitos} palavras")
    return sons


def empacotar(dados, lingua, sons):
    """Pacotes MP3 + indice. Grava em saida/ e marca p['audio'] em cada palavra."""
    comum.SAIDA.mkdir(parents=True, exist_ok=True)
    com_audio = [p for p in dados["palavras"] if p["id"] in sons]
    pausa = b"\x00\x00" * int(TAXA * PAUSA)
    indice, creditos = {"pacotes": []}, []
    for k in range(0, len(com_audio), POR_PACOTE):
        lote = com_audio[k:k + POR_PACOTE]
        nome = f"{lingua}-audio-{k // POR_PACOTE + 1:03d}.mp3"
        buf, pos, itens = bytearray(), 0, {}
        for p in lote:
            pcm, info = sons[p["id"]]
            ini = pos / 2 / TAXA * 1000
            buf += pcm + pausa
            pos += len(pcm) + len(pausa)
            fim = ini + len(pcm) / 2 / TAXA * 1000
            itens[p["id"]] = [round(ini), round(fim)]
            p["audio"] = {"pacote": nome, "ini_ms": round(ini), "fim_ms": round(fim), "tipo": info["tipo"]}
            if info["tipo"] == "nativo":
                p["audio"] |= {"autor": info["autor"], "licenca": info["licenca"]}
                creditos.append((p["id"], info))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(TAXA), "-ac", "1", "-i", "pipe:0",
                        "-c:a", "libmp3lame", "-b:a", "64k", str(comum.SAIDA / nome)], input=bytes(buf), check=True)
        tam = (comum.SAIDA / nome).stat().st_size
        if tam > LIMITE_MP3:
            raise RuntimeError(f"{nome} tem {tam} bytes (> 10 MB): reduza POR_PACOTE")
        indice["pacotes"].append({"arquivo": nome, "bytes": tam, "palavras": itens})
    nome_ind = f"{lingua}-audio-indice.json"
    import json
    (comum.SAIDA / nome_ind).write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    nativos = sum(1 for p in com_audio if p["audio"]["tipo"] == "nativo")
    return {"pacotes": [x["arquivo"] for x in indice["pacotes"]], "indice": nome_ind,
            "nativos": nativos, "sinteticos": len(com_audio) - nativos, "creditos": creditos}
