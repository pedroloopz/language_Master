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

import audio
import comum
import de
import ja


def licencas(resumo, creditos):
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
         f"| [Piper](https://github.com/OHF-Voice/piper1-gpl) + [Thorsten-Voice](https://github.com/thorstenMueller/Thorsten-Voice) | audio sintetico das frases em alemao do app | dados CC0; credito: {audio.CREDITO_PIPER} |",
         "", "## Resumo desta versao", ""]
    for lingua, r in resumo.items():
        L.append(f"- {lingua}: {r['palavras']} palavras | audio nativo {r['nativos']} | sintetico {r['sinteticos']} "
                 f"| {len(r['pacotes'])} pacotes MP3 | frases do app com audio: {r.get('frases', 0)}")
    L += ["", "## Audios nativos (autor e licenca de cada arquivo)", "",
          "| Palavra (id) | Arquivo no Commons | Autor | Licenca |", "|---|---|---|---|"]
    for pid, info in creditos:
        L.append(f"| {pid} | [{info['arquivo']}]({info['pagina']}) | {info['autor'].replace('|', '/')} | {info['licenca']} |")
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
        parte = {"resumo": {"palavras": len(dados["palavras"]), "nativos": pac["nativos"],
                            "sinteticos": pac["sinteticos"], "pacotes": pac["pacotes"], "frases": fr["frases"]},
                 "arquivos": arquivos, "creditos": pac["creditos"]}
        (comum.SAIDA / f"_parte-{lingua}.json").write_text(json.dumps(parte, ensure_ascii=False), encoding="utf-8")
    juntar()


def juntar():
    """LICENCAS.md e _resumo.json a partir de saida/_parte-*.json (uma por lingua)."""
    resumo, creditos, arquivos = {}, [], []
    for f in sorted(comum.SAIDA.glob("_parte-*.json")):
        parte = json.loads(f.read_text(encoding="utf-8"))
        lingua = f.stem.split("-", 1)[1]
        resumo[lingua] = parte["resumo"]
        creditos += [tuple(c) for c in parte["creditos"]]
        arquivos += parte["arquivos"]
    licencas(resumo, creditos)
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
