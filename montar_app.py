"""Monta os arquivos que o app LANGUAGE MASTER usa a partir de uma Release baixada em saida/.

Uso: python montar_app.py [saida] [destino]   (padrao: saida -> app)
Gera em destino/:
  audio-mapa.json  {"pacotes":[...], "ja":{"猫":[pacote, ini_ms, fim_ms, "n"|"s"], "ねこ":...}, "de":{"Haus":[...]}}
                   (inclui as frases fixas do app, de <lingua>-frases.json, com a chave no texto e no kana)
  dic-ja.json      {"palavras":[[escrita, leitura, nivel, en, de, classe, ex_ja, ex_en]], "kanji":[[k, on, kun, en, pt]]}
  dic-de.json      {"palavras":[[palavra, artigo, plural, nivel, ipa, en, ex_de, ex_en, praeteritum, partizip2, auxiliar]]}
e copia os pacotes MP3 e o LICENCAS.md. O app so precisa destes arquivos (os JSON grandes da Release ficam de fora).
"""
import json
import pathlib
import shutil
import sys


def palavras(saida, lingua):
    out, kanji = [], []
    for f in sorted(saida.glob(f"{lingua}*.json")):
        if "audio" in f.name or "frases" in f.name:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        out += d.get("palavras", [])
        kanji += d.get("kanji", [])
    return out, kanji


def montar(saida, destino):
    destino.mkdir(parents=True, exist_ok=True)
    mapa, pacotes = {"pacotes": []}, {}
    for lingua in ("ja", "de"):
        ps, kanji = palavras(saida, lingua)
        if not ps and not (saida / f"{lingua}-frases.json").exists():
            continue
        m = mapa.setdefault(lingua, {})
        linhas = []
        for p in ps:
            a = p.get("audio")
            if a:
                if a["pacote"] not in pacotes:
                    pacotes[a["pacote"]] = len(mapa["pacotes"])
                    mapa["pacotes"].append(a["pacote"])
                clip = [pacotes[a["pacote"]], a["ini_ms"], a["fim_ms"], "n" if a["tipo"] == "nativo" else "s"]
                chaves = [p["escrita"], p["leitura"]] if lingua == "ja" else [p["palavra"]]
                for k in chaves:              # a primeira (nivel mais facil) vence nos homofonos
                    m.setdefault(k, clip)
            ex = p.get("exemplo") or {}
            if lingua == "ja":
                linhas.append([p["escrita"], p["leitura"], p["nivel"], "; ".join(p["en"]), "; ".join(p.get("de", [])),
                               (p.get("classe") or [""])[0], ex.get("ja") or "", ex.get("en") or ""])
            else:
                linhas.append([p["palavra"], p.get("artigo") or "", p.get("plural") or "", p["nivel"], p.get("ipa") or "",
                               "; ".join(p["en"]), ex.get("de") or "", ex.get("en") or "",
                               p.get("praeteritum") or "", p.get("partizip2") or "", p.get("auxiliar") or ""])
        fr = saida / f"{lingua}-frases.json"           # frases fixas do app (voz sintetica)
        if fr.exists():
            d = json.loads(fr.read_text(encoding="utf-8"))
            for texto, kana, i, ini, fim in d["frases"]:
                nome = d["pacotes"][i]
                if nome not in pacotes:
                    pacotes[nome] = len(mapa["pacotes"])
                    mapa["pacotes"].append(nome)
                for k in (texto, kana):
                    if k:
                        m.setdefault(k, [pacotes[nome], ini, fim, "s"])
        dic = {"palavras": linhas}
        if lingua == "ja":
            dic["kanji"] = [[k["kanji"], "、".join(k["on"]), "、".join(k["kun"]), "; ".join(k["en"]), "; ".join(k["pt"])]
                            for k in kanji]
        (destino / f"dic-{lingua}.json").write_text(json.dumps(dic, ensure_ascii=False, separators=(",", ":")),
                                                    encoding="utf-8")
    (destino / "audio-mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")),
                                             encoding="utf-8")
    for nome in mapa["pacotes"] + ["LICENCAS.md"]:
        if (saida / nome).exists():
            shutil.copy2(saida / nome, destino / nome)
    return mapa


if __name__ == "__main__":
    a = sys.argv[1:]
    mapa = montar(pathlib.Path(a[0] if a else "saida"), pathlib.Path(a[1] if len(a) > 1 else "app"))
    print({k: len(v) for k, v in mapa.items()})
