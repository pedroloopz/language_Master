"""Gera os dados do LANGUAGE MASTER em saida/: ja*.json, de*.json, pacotes MP3, indices e LICENCAS.md.

Uso: python gerar.py            (tudo)
     LINGUAS=de python gerar.py (so alemao)
     python gerar.py licencas   (so junta LICENCAS.md e _resumo.json das partes ja geradas)
O workflow `gerar` roda uma lingua por job e publica uma Release com os arquivos.
"""
import json
import os
import pathlib
import sys

import subprocess

import audio
import comum
import de
import ja
import tatoeba


def licencas(resumo, creditos, creditos_tatoeba=()):
    L = ["# Licencas e origem dos dados", "",
         "Gerado automaticamente por `gerar.py`. Cada base mantem a licenca da fonte.", "",
         "| Base | Uso aqui | Licenca |", "|---|---|---|",
         "| [JMdict](https://www.edrdg.org/jmdict/j_jmdict.html) via [jmdict-simplified](https://github.com/scriptin/jmdict-simplified) | palavras, leituras, significados (en/de), classe | [EDRDG](https://www.edrdg.org/edrdg/licence.html) (CC BY-SA 4.0) |",
         "| [Kanjidic2](https://www.edrdg.org/wiki/index.php/KANJIDIC_Project) via jmdict-simplified | leituras on/kun e significados dos kanji | CC BY-SA 4.0 |",
         "| Exemplos do JMdict ([Tatoeba](https://tatoeba.org)) | frase de exemplo em japones | CC BY 2.0 FR |",
         "| Listas JLPT de [Jonathan Waller](https://www.tanos.co.uk/jlpt/) via [yomitan-jlpt-vocab](https://github.com/stephenmk/yomitan-jlpt-vocab) | nivel N5-N2 | CC BY (listas) / CC BY-SA 4.0 (repositorio) |",
         "| [wordfreq](https://github.com/rspeer/wordfreq) | frequencia (ordem e niveis estimados) | dados CC BY-SA 4.0 |",
         "| [Wiktionary](https://en.wiktionary.org) via [kaikki.org](https://kaikki.org) ([wiktextract](https://github.com/tatuylonen/wiktextract)) | alemao: artigo, plural, verbos, IPA, significado, exemplo | CC BY-SA 4.0 (e GFDL) |",
         "| [Wikimedia Commons](https://commons.wikimedia.org) (Wiktionary e [Lingua Libre](https://lingualibre.org)) | audio nativo | licenca de cada arquivo (lista abaixo) |",
         f"| [VOICEVOX](https://voicevox.hiroshiba.jp/) | audio sintetico do japones sem gravacao nativa e das frases do app | termos do VOICEVOX; credito: {audio.CREDITO_VOZ} |",
         "| [Tatoeba](https://tatoeba.org) (frases reais da Escuta) | texto das frases e traducoes | CC BY 2.0 FR (autor de cada frase abaixo) |",
         "| Gravacoes do [Tatoeba](https://tatoeba.org) | audio nativo das frases da Escuta | licenca escolhida por quem gravou (so CC BY, CC BY-SA, CC0; lista abaixo) |",
         "| [kuroshiro](https://github.com/hexenq/kuroshiro) + [kuromoji.js](https://github.com/takuyaa/kuromoji.js) (dicionario IPADIC) | furigana automatica | MIT / Apache 2.0 |",
         f"| [Piper](https://github.com/OHF-Voice/piper1-gpl) + [Thorsten-Voice](https://github.com/thorstenMueller/Thorsten-Voice) | audio sintetico das frases em alemao do app | dados CC0; credito: {audio.CREDITO_PIPER} |",
         "", "## Resumo desta versao", ""]
    for lingua, r in resumo.items():
        L.append(f"- {lingua}: {r['palavras']} palavras | audio nativo {r['nativos']} | sintetico {r['sinteticos']} "
                 f"| {len(r['pacotes'])} pacotes MP3 | frases do app com audio: {r.get('frases', 0)} | frases do Tatoeba: {r.get('tatoeba', 0)}")
    L += ["", "## Audios nativos (autor e licenca de cada arquivo)", "",
          "| Palavra (id) | Arquivo no Commons | Autor | Licenca |", "|---|---|---|---|"]
    for pid, info in creditos:
        L.append(f"| {pid} | [{info['arquivo']}]({info['pagina']}) | {info['autor'].replace('|', '/')} | {info['licenca']} |")
    if creditos_tatoeba:
        L += ["", "## Frases e gravacoes do Tatoeba", "",
              "| Frase | Autor da frase (CC BY 2.0 FR) | Autor da gravacao | Licenca da gravacao |", "|---|---|---|---|"]
        for sid, autor, autor_audio, lic in creditos_tatoeba:
            L.append(f"| [#{sid}](https://tatoeba.org/sentences/show/{sid}) | {autor or '?'} | {autor_audio} | {lic} |")
    (comum.SAIDA / "LICENCAS.md").write_text("\n".join(L) + "\n", encoding="utf-8")


FRASES = pathlib.Path("frases.json")


def main():
    linguas = os.environ.get("LINGUAS", "ja,de").split(",")
    for lingua in linguas:
        dados = ja.gerar() if lingua == "ja" else de.gerar()
        sons = audio.anexar_audio(dados, lingua, sintetico=(lingua == "ja"))
        pac = audio.empacotar(dados, lingua, sons)
        dados["audio"] = {"pacotes": pac["pacotes"], "indice": pac["indice"], "taxa_hz": audio.TAXA}
        arquivos = comum.gravar_json(lingua, dados, dividir_por="nivel") + pac["pacotes"] + [pac["indice"]]
        fr = {"arquivos": [], "frases": 0}
        if FRASES.exists():                   # frases fixas do app (node frases.js app/index.html > frases.json)
            fr = audio.frases(lingua, json.loads(FRASES.read_text(encoding="utf-8"))[lingua])
        arquivos += fr["arquivos"]
        tt = {"arquivos": [], "frases": 0, "creditos": []}
        try:                                  # frases reais do Tatoeba com gravacao nativa (falha nao derruba o resto)
            tt = tatoeba.gerar(lingua)
        except Exception as e:
            comum.log(f"tatoeba {lingua} falhou: {e!r}")
        arquivos += tt["arquivos"]
        if lingua == "ja":
            arquivos += furigana(tt)
        parte = {"resumo": {"palavras": len(dados["palavras"]), "nativos": pac["nativos"],
                            "sinteticos": pac["sinteticos"], "pacotes": pac["pacotes"], "frases": fr["frases"],
                            "tatoeba": tt["frases"]},
                 "arquivos": arquivos, "creditos": pac["creditos"], "creditos_tatoeba": tt["creditos"]}
        (comum.SAIDA / f"_parte-{lingua}.json").write_text(json.dumps(parte, ensure_ascii=False), encoding="utf-8")
    juntar()


def furigana(tt):
    """saida/ja-furigana.json com kuroshiro (node furigana.js): frases do app + frases do Tatoeba."""
    entradas = [str(FRASES)] if FRASES.exists() else []
    if tt["frases"]:
        comum.CACHE.mkdir(parents=True, exist_ok=True)
        pares = comum.CACHE / "tatoeba-ja-pares.json"
        d = json.loads((comum.SAIDA / "ja-tatoeba.json").read_text(encoding="utf-8"))
        pares.write_text(json.dumps([[f[0], ""] for f in d["frases"]], ensure_ascii=False), encoding="utf-8")
        entradas.append(str(pares))
    try:
        r = subprocess.run(["node", "furigana.js", *entradas], capture_output=True, text=True, check=True)
    except Exception as e:
        comum.log(f"furigana falhou: {e!r} {getattr(e, 'stderr', '')}")
        return []
    comum.log(r.stderr.strip())
    (comum.SAIDA / "ja-furigana.json").write_text(r.stdout, encoding="utf-8")
    return ["ja-furigana.json"]


def juntar():
    """LICENCAS.md e _resumo.json a partir de saida/_parte-*.json (uma por lingua)."""
    resumo, creditos, arquivos, cred_tt = {}, [], [], []
    for f in sorted(comum.SAIDA.glob("_parte-*.json")):
        parte = json.loads(f.read_text(encoding="utf-8"))
        lingua = f.stem.split("-", 1)[1]
        resumo[lingua] = parte["resumo"]
        creditos += [tuple(c) for c in parte["creditos"]]
        cred_tt += parte.get("creditos_tatoeba", [])
        arquivos += parte["arquivos"]
    licencas(resumo, creditos, cred_tt)
    arquivos.append("LICENCAS.md")
    tamanhos = {a: (comum.SAIDA / a).stat().st_size for a in arquivos}
    (comum.SAIDA / "_resumo.json").write_text(json.dumps({"resumo": resumo, "tamanhos": tamanhos},
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    for a, t in tamanhos.items():
        comum.log(f"{a}: {t / 1024 / 1024:.2f} MB")
    for lingua, r in resumo.items():
        comum.log(f"RESUMO {lingua}: {r['palavras']} palavras, {r['nativos']} com audio nativo, "
                  f"{r['sinteticos']} sinteticos, {len(r['pacotes'])} pacotes, {r.get('frases', 0)} frases")


if __name__ == "__main__":
    juntar() if sys.argv[1:] == ["licencas"] else main()
