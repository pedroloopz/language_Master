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
MINUTOS_NATIVO = float(os.environ.get("MINUTOS_NATIVO", "200"))   # o que nao baixar nesse tempo fica sem gravacao
MINUTOS_SINTETICO = float(os.environ.get("MINUTOS_SINTETICO", "120"))
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


def para_pcm(dados, entrada="pipe:0", max_seg=MAX_SEG):
    """Qualquer audio -> PCM 16 bits mono 22050 Hz, sem silencio nas pontas, ate max_seg."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", entrada, "-t", str(max_seg + 1), "-af", FILTRO,
                        "-t", str(max_seg), "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "pipe:1"],
                       input=dados, capture_output=True, check=True)
    return r.stdout


RECUSAS = {"429": 0, "erro": 0}          # so para o log de progresso


def baixar_nativo(url, prazo=float("inf")):
    for n in range(3):
        if time.time() > prazo:
            return None
        try:
            r = requests.get(url, headers=comum.UA, timeout=(10, 30))
            if r.status_code == 429:
                RECUSAS["429"] += 1
                if RECUSAS["429"] == 1:
                    comum.log(f"primeira recusa 429: Retry-After={r.headers.get('Retry-After')} {url}")
                time.sleep(min(120.0, float(r.headers.get("Retry-After") or 10 * (n + 1))))
                continue
            r.raise_for_status()
            time.sleep(1)                     # 1 arquivo por vez, com pausa: o Commons recusa (429) quem baixa rapido
            return para_pcm(r.content)
        except Exception as e:
            RECUSAS["erro"] += 1
            if RECUSAS["erro"] == 1:
                comum.log(f"primeiro erro de download: {e!r} {url}")
            time.sleep(3 * (n + 1))
    return None


def consulta(texto):
    q = requests.post(f"{VOICEVOX}/audio_query", params={"text": texto, "speaker": VOZ}, timeout=60)
    q.raise_for_status()
    return q.json()


VOGAL = {c: v for v, linha in zip("AIUEO", ["アカサタナハマヤラワガザダバパァャ", "イキシチニヒミリギジヂビピィ",
                                         "ウクスツヌフムユルグズヅブプゥュ", "エケセテネヘメレゲゼデベペェ",
                                         "オコソトノホモヨロヲゴゾドボポォョ"]) for c in linha}


def so_kana(s):
    """Leitura comparavel: katakana sem espaco/pontuacao/ー; は/へ/を como soam; vogal longa (こう, けい, おお) = curta."""
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    s = "".join(c for c in s if "ァ" <= c <= "ヶ").translate(str.maketrans("ハヘヲヅヂ", "ワエオズジ"))
    out = []
    for c in s:
        v = VOGAL.get(out[-1]) if out else None
        if c in "アイウエオ" and v and (VOGAL[c] == v or (c, v) in (("ウ", "O"), ("イ", "E"))):
            continue
        out.append(c)
    return "".join(out)


TROCAS = {"kana": 0}


def sintetizar(texto, kana="", max_seg=MAX_SEG):
    """VOICEVOX le o texto com kanji (melhor entonacao); se a leitura dele nao bate com a do dicionario,
    sintetiza a partir do kana (o kanji sozinho pode ser lido errado: 生物 せいぶつ/なまもの)."""
    q = consulta(texto)
    lida = "".join(m["text"] for ap in q["accent_phrases"] for m in ap["moras"])
    if kana and so_kana(lida) != so_kana(kana):
        TROCAS["kana"] += 1
        q = consulta(kana.replace(" ", ""))
    w = requests.post(f"{VOICEVOX}/synthesis", params={"speaker": VOZ}, json=q, timeout=120)
    w.raise_for_status()
    return para_pcm(w.content, max_seg=max_seg)


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

    estado = {"desistir": False}

    def um(item):
        pid, arq = item
        m = meta.get(arq) or {}
        if not m.get("url") or estado["desistir"]:
            return pid, None
        pcm = baixar_nativo(m["url"], prazo)
        return pid, (pcm, {"tipo": "nativo", "arquivo": arq, "autor": m["autor"], "licenca": m["licenca"],
                           "pagina": m["pagina"]}) if pcm else None

    comum.log(f"{lingua}: baixando {len(escolha)} gravacoes nativas (no maximo {MINUTOS_NATIVO:.0f} min)")
    t0 = time.time()
    prazo = t0 + MINUTOS_NATIVO * 60
    with cf.ThreadPoolExecutor(1) as ex:
        for n, (pid, r) in enumerate(ex.map(um, escolha.items()), 1):
            if r:
                sons[pid] = r
            if n == 40 and not sons:          # o Commons nao esta entregando: segue sem audio nativo
                estado["desistir"] = True
                comum.log(f"{lingua}: 0 de 40 downloads deram certo; desisto do audio nativo nesta rodada")
            if n % 50 == 0:
                comum.log(f"{lingua}: {n}/{len(escolha)} gravacoes em {(time.time() - t0) / 60:.0f} min, {len(sons)} ok, "
                         f"recusas 429: {RECUSAS['429']}, erros: {RECUSAS['erro']}")
    comum.log(f"{lingua}: audio nativo para {len(sons)} de {len(palavras)} palavras")
    if sintetico:
        faltam = [p for p in palavras if p["id"] not in sons]
        feitos = 0
        prazo = time.time() + MINUTOS_SINTETICO * 60
        for p in faltam:
            if time.time() > prazo:
                comum.log(f"{lingua}: tempo do VOICEVOX esgotado")
                break
            try:
                sons[p["id"]] = (sintetizar(p["escrita"] or p["leitura"], p["leitura"]),
                                 {"tipo": "sintetico", "autor": CREDITO_VOZ, "licenca": "termos do VOICEVOX e da voz"})
                feitos += 1
                if feitos % 200 == 0:
                    comum.log(f"{lingua}: {feitos}/{len(faltam)} sinteticos ({TROCAS['kana']} lidos pelo kana)")
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


PIPER = os.environ.get("PIPER_VOZ", "voz/de_DE-thorsten-medium.onnx")
CREDITO_PIPER = "Piper, voz de_DE-thorsten-medium (dados Thorsten-Voice, CC0)"


def falar_de():
    """Voz sintetica do alemao (Piper). Devolve texto -> bytes WAV."""
    import io
    import wave
    from piper import PiperVoice
    voz = PiperVoice.load(PIPER)

    def f(texto):
        b = io.BytesIO()
        with wave.open(b, "wb") as w:
            voz.synthesize_wav(texto, w)
        return b.getvalue()
    return f


def frases(lingua, lista, falar=None):
    """Audio das frases fixas do app (lista de [texto, kana], de frases.js) em pacotes
    <lingua>-frases-NNN.mp3 (32 kbps). Grava saida/<lingua>-frases.json
    {"pacotes": [...], "frases": [[texto, kana, pacote, ini_ms, fim_ms]]} e devolve os arquivos."""
    import json
    comum.SAIDA.mkdir(parents=True, exist_ok=True)
    falar = falar or (falar_de() if lingua == "de" else None)
    pausa = b"\x00\x00" * int(TAXA * PAUSA)
    pacotes, saida, buf, pos = [], [], bytearray(), 0

    def fechar():
        nonlocal buf, pos
        if not buf:
            return
        nome = f"{lingua}-frases-{len(pacotes) + 1:03d}.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(TAXA), "-ac", "1", "-i", "pipe:0",
                        "-c:a", "libmp3lame", "-b:a", "32k", str(comum.SAIDA / nome)], input=bytes(buf), check=True)
        pacotes.append(nome)
        buf, pos = bytearray(), 0

    t0, falhas = time.time(), 0
    for n, (texto, kana) in enumerate(lista, 1):
        try:
            pcm = sintetizar(texto, kana, max_seg=30) if lingua == "ja" else para_pcm(falar(texto), max_seg=30)
        except Exception as e:
            falhas += 1
            if falhas == 1:
                comum.log(f"frase falhou: {e!r} {texto}")
            continue
        ini = pos / 2 / TAXA * 1000
        buf += pcm + pausa
        pos += len(pcm) + len(pausa)
        saida.append([texto, kana, len(pacotes), round(ini), round(ini + len(pcm) / 2 / TAXA * 1000)])
        if pos > TAXA * 2 * 600:              # ~10 min por pacote (~2,4 MB)
            fechar()
        if n % 200 == 0:
            comum.log(f"{lingua}: {n}/{len(lista)} frases em {(time.time() - t0) / 60:.0f} min")
    fechar()
    nome = f"{lingua}-frases.json"
    (comum.SAIDA / nome).write_text(json.dumps({"pacotes": pacotes, "frases": saida}, ensure_ascii=False,
                                               separators=(",", ":")), encoding="utf-8")
    comum.log(f"{lingua}: audio para {len(saida)} de {len(lista)} frases, {len(pacotes)} pacotes, {falhas} falhas"
              + (f", {TROCAS['kana']} lidas pelo kana" if lingua == "ja" else ""))
    return {"arquivos": [nome] + pacotes, "frases": len(saida)}
