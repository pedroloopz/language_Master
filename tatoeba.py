"""Frases reais do Tatoeba com gravacao nativa de licenca aberta, para a Escuta do app.

Baixa os exports semanais do Tatoeba (frases, traducoes e lista de audios), escolhe frases
com audio de licenca que permite reuso (sem NC/ND), com traducao em portugues,
baixa as gravacoes e junta em pacotes <lingua>-tatoeba-NNN.mp3 (~3 min cada, 32 kbps).
Grava saida/<lingua>-tatoeba.json:
  {"pacotes": [...], "frases": [[texto, traducao, "pt", pacote, ini_ms, fim_ms, id_frase]],
   "creditos": [[id_frase, autor_frase, autor_audio, licenca_audio]]}
Texto das frases: CC BY 2.0 FR (autor = quem escreveu a frase). Audio: licenca escolhida por quem gravou.
"""
import bz2
import csv
import json
import os
import random
import subprocess
import sys
import tarfile
import time

import requests

import audio
import comum

EXPORTS = "https://downloads.tatoeba.org/exports"
ISO = {"ja": "jpn", "de": "deu"}
MAXIMO = int(os.environ.get("TATOEBA_MAX", "1500"))
MINUTOS = float(os.environ.get("MINUTOS_TATOEBA", "90"))
TAMANHO = {"ja": (12, 60), "de": (6, 25)}       # ja: caracteres; de: palavras
csv.field_size_limit(sys.maxsize)


def licenca_aberta(lic):
    """Reuso permitido: CC BY, CC BY-SA, CC0, dominio publico. Sem licenca, NC ou ND: fora."""
    lic = (lic or "").strip()
    if not lic or lic == "\\N":
        return False
    up = lic.upper()
    return "NC" not in up and "ND" not in up and (up.startswith("CC") or "PUBLIC" in up)


def tamanho(lingua, texto):
    return len(texto) if lingua == "ja" else len(texto.split())


def tsv(caminho):
    """Linhas de um .tsv.bz2 (ou .csv dentro de .tar.bz2) do Tatoeba."""
    if str(caminho).endswith(".tar.bz2"):
        with tarfile.open(caminho, "r:bz2") as t:
            for m in t:
                if m.isfile():
                    for linha in t.extractfile(m).read().decode("utf-8").splitlines():
                        yield linha.split("\t")
        return
    with bz2.open(caminho, "rt", encoding="utf-8") as f:
        for linha in f:
            yield linha.rstrip("\n").split("\t")


def baixar_export(rel):
    return comum.baixar(f"{EXPORTS}/{rel}", rel.replace("/", "_"))


def frases_da_lingua(iso):
    """{id: (texto, autor)}"""
    out = {}
    for c in tsv(baixar_export(f"per_language/{iso}/{iso}_sentences_detailed.tsv.bz2")):
        if len(c) >= 4:
            out[c[0]] = (c[2], c[3] if c[3] != "\\N" else "")
    return out


def links(iso, alvo):
    """{id_origem: [id_traducao]} entre iso e alvo (se o arquivo do par nao existir, usa o links.tar.bz2 completo;
    a lingua da traducao e conferida depois, pela lista de frases do alvo)."""
    out = {}
    try:
        arq = baixar_export(f"per_language/{iso}/{iso}-{alvo}_links.tsv.bz2")
    except RuntimeError:
        arq = baixar_export("links.tar.bz2")
    for c in tsv(arq):
        if len(c) >= 2:
            out.setdefault(c[0], []).append(c[1])
    return out


def audios(ids):
    """{id_frase: (id_audio, autor, licenca)} so com licenca aberta (o primeiro audio aberto de cada frase)."""
    out = {}
    for c in tsv(baixar_export("sentences_with_audio.tar.bz2")):
        if len(c) >= 4 and c[0] in ids and c[0] not in out and licenca_aberta(c[3]):
            out[c[0]] = (c[1], c[2], c[3])
    return out


def escolher(lingua, frases, aud, trad):
    """Frases com audio aberto e traducao, no tamanho certo; sorteio fixo."""
    lo, hi = TAMANHO[lingua]
    cand = [(sid, t) for sid, (t, _) in frases.items()
            if sid in aud and sid in trad and lo <= tamanho(lingua, t) <= hi]
    random.Random(42).shuffle(cand)
    return cand[:MAXIMO]


def baixar_audio(id_audio, iso, sid):
    for url in (f"https://tatoeba.org/audio/download/{id_audio}", f"https://audio.tatoeba.org/sentences/{iso}/{sid}.mp3"):
        for n in range(3):
            try:
                r = requests.get(url, headers=comum.UA, timeout=(10, 30))
                if r.status_code == 429:
                    time.sleep(10 * (n + 1))
                    continue
                if r.status_code == 404:
                    break
                r.raise_for_status()
                return audio.para_pcm(r.content, max_seg=20)
            except Exception as e:
                comum.log(f"tatoeba: audio {sid} falhou ({e!r})")
                time.sleep(3 * (n + 1))
    return None


def gerar(lingua):
    iso = ISO[lingua]
    frases = frases_da_lingua(iso)
    comum.log(f"tatoeba {lingua}: {len(frases)} frases")
    aud = audios(set(frases))
    comum.log(f"tatoeba {lingua}: {len(aud)} com audio de licenca aberta")
    trad, por = {}, frases_da_lingua("por")               # {id: (traducao, "pt")}: o app e todo em portugues
    for sid, ts in links(iso, "por").items():
        t = next((por[x][0] for x in ts if x in por), None) if sid in aud else None
        if t:
            trad[sid] = (t, "pt")
    escolhidas = escolher(lingua, frases, aud, trad)
    comum.log(f"tatoeba {lingua}: {len(trad)} com audio aberto e traducao em portugues; {len(escolhidas)} escolhidas")

    comum.SAIDA.mkdir(parents=True, exist_ok=True)
    pausa = b"\x00\x00" * int(audio.TAXA * audio.PAUSA)
    pacotes, saida, creditos, buf, pos = [], [], [], bytearray(), 0

    def fechar():
        nonlocal buf, pos
        if not buf:
            return
        nome = f"{lingua}-tatoeba-{len(pacotes) + 1:03d}.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(audio.TAXA), "-ac", "1", "-i", "pipe:0",
                        "-c:a", "libmp3lame", "-b:a", "32k", str(comum.SAIDA / nome)], input=bytes(buf), check=True)
        pacotes.append(nome)
        buf, pos = bytearray(), 0

    prazo = time.time() + MINUTOS * 60
    for n, (sid, texto) in enumerate(escolhidas, 1):
        if time.time() > prazo:
            comum.log(f"tatoeba {lingua}: tempo esgotado em {n - 1} frases")
            break
        id_audio, autor_audio, lic = aud[sid]
        pcm = baixar_audio(id_audio, iso, sid)
        time.sleep(0.3)
        if not pcm:
            continue
        ini = pos / 2 / audio.TAXA * 1000
        buf += pcm + pausa
        pos += len(pcm) + len(pausa)
        saida.append([texto, trad[sid][0], trad[sid][1], len(pacotes), round(ini),
                      round(ini + len(pcm) / 2 / audio.TAXA * 1000), int(sid)])
        creditos.append([int(sid), frases[sid][1], autor_audio, lic])
        if pos > audio.TAXA * 2 * 180:
            fechar()
        if n % 200 == 0:
            comum.log(f"tatoeba {lingua}: {n}/{len(escolhidas)} audios, {len(saida)} ok")
    fechar()
    nome = f"{lingua}-tatoeba.json"
    (comum.SAIDA / nome).write_text(json.dumps({"pacotes": pacotes, "frases": saida, "creditos": creditos},
                                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    comum.log(f"tatoeba {lingua}: {len(saida)} frases com audio nativo em {len(pacotes)} pacotes")
    return {"arquivos": [nome] + pacotes, "frases": len(saida), "creditos": creditos}
