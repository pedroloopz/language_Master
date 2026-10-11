"""Japones: ~8.000 palavras uteis para N5-N2 (JMdict) + kanji do nivel (Kanjidic2).

Lista: JLPT N5-N2 de Jonathan Waller (CC BY), ja ligada ao JMdict por stephenmk/yomitan-jlpt-vocab;
completada ate ALVO com as palavras "common" do JMdict mais frequentes (wordfreq), nivel estimado.
"""
import csv
import io
import json
import zipfile

import comum

ALVO = 8000
NIVEIS = ["n5", "n4", "n3", "n2"]
JLPT_CSV = "https://raw.githubusercontent.com/stephenmk/yomitan-jlpt-vocab/main/original_data/{}.csv"


def ler_zip_json(caminho):
    with zipfile.ZipFile(caminho) as z:
        nome = next(n for n in z.namelist() if n.endswith(".json"))
        with z.open(nome) as f:
            return json.load(f)


def lista_jlpt():
    """{jmdict_seq: (nivel, kanji, kana)} - o nivel mais facil vence se repetir."""
    out = {}
    for nv in NIVEIS:
        texto = comum.baixar(JLPT_CSV.format(nv), f"jlpt-{nv}.csv").read_text(encoding="utf-8")
        for linha in csv.DictReader(io.StringIO(texto)):
            seq = linha["jmdict_seq"].strip()
            if seq and seq not in out:
                out[seq] = (nv.upper(), linha["kanji"].strip(), linha["kana"].strip())
    return out


def glosas(entrada, lang, n=3):
    vistos = []
    for s in entrada["sense"]:
        for g in s.get("gloss", []):
            if g.get("lang") == lang and g["text"] not in vistos:
                vistos.append(g["text"])
                break
        if len(vistos) >= n:
            break
    return vistos


def exemplo(entrada):
    for s in entrada["sense"]:
        for ex in s.get("examples", []) or []:
            ja = next((x["text"] for x in ex.get("sentences", []) if x.get("land", x.get("lang")) == "jpn"), None)
            en = next((x["text"] for x in ex.get("sentences", []) if x.get("lang") == "eng"), None)
            if ja:
                return {"ja": ja, "en": en, "fonte": "Tatoeba (CC BY 2.0 FR)"}
    return None


def zipf(texto):
    from wordfreq import zipf_frequency
    try:
        return round(zipf_frequency(texto, "ja"), 2)
    except Exception:
        return 0.0


def gerar():
    url_ex, tag = comum.ultima_release("scriptin/jmdict-simplified",
                                       lambda n: n.startswith("jmdict-examples-eng") and n.endswith(".json.zip"))
    url_all, _ = comum.ultima_release("scriptin/jmdict-simplified",
                                      lambda n: n.startswith("jmdict-all-") and n[11:12].isdigit() and n.endswith(".json.zip"))
    url_kd, _ = comum.ultima_release("scriptin/jmdict-simplified",
                                     lambda n: n.startswith("kanjidic2-all") and n.endswith(".json.zip"))
    comum.log(f"JMdict-simplified {tag}")
    ex = ler_zip_json(comum.baixar(url_ex))
    tags_pos = ex.get("tags", {})
    por_seq = {w["id"]: w for w in ex["words"]}
    alemao = {}
    todos = ler_zip_json(comum.baixar(url_all))
    for w in todos["words"]:
        g = glosas(w, "ger")
        if g:
            alemao[w["id"]] = g
    del todos

    jlpt = lista_jlpt()
    comum.log(f"lista JLPT N5-N2: {len(jlpt)} entradas")
    escolhidos = []          # (seq, nivel, escrita, leitura, fonte_nivel)
    for seq, (nv, kanji, kana) in jlpt.items():
        if seq in por_seq:
            escolhidos.append((seq, nv, kanji or kana, kana, "lista JLPT de Jonathan Waller"))
    ja_tem = {e[0] for e in escolhidos}
    candidatos = []
    for seq, w in por_seq.items():
        if seq in ja_tem:
            continue
        k = next((x["text"] for x in w.get("kanji", []) if x.get("common")), None)
        r = next((x["text"] for x in w.get("kana", []) if x.get("common")), None)
        if not (k or r) or not r:
            continue
        candidatos.append((zipf(k or r), seq, k or r, r))
    candidatos.sort(reverse=True)
    for z, seq, escrita, leitura in candidatos[:max(0, ALVO - len(escolhidos))]:
        escolhidos.append((seq, "N2", escrita, leitura, "estimado pela frequencia (fora da lista JLPT)"))

    palavras = []
    ordem = {nv: i for i, nv in enumerate(["N5", "N4", "N3", "N2"])}
    for seq, nv, escrita, leitura, fonte in escolhidos:
        w = por_seq[seq]
        pos = []
        for s in w["sense"][:2]:
            for p in s.get("partOfSpeech", []):
                if p not in pos:
                    pos.append(p)
        palavras.append({
            "id": f"ja-{seq}", "jmdict": int(seq), "escrita": escrita, "leitura": leitura,
            "en": glosas(w, "eng"), "de": alemao.get(seq, []),
            "classe": [tags_pos.get(p, p) for p in pos],
            "exemplo": exemplo(w), "nivel": nv, "nivel_fonte": fonte, "zipf": zipf(escrita),
        })
    palavras.sort(key=lambda p: (ordem[p["nivel"]], -p["zipf"]))

    # kanji que aparecem nas palavras escolhidas
    kd = ler_zip_json(comum.baixar(url_kd))
    usados = {c for p in palavras for c in p["escrita"] if "一" <= c <= "鿿"}
    kanji = []
    for ch in kd["characters"]:
        if ch["literal"] not in usados:
            continue
        rm = ch.get("readingMeaning") or {}
        on, kun, sig = [], [], {"en": [], "pt": []}
        for g in rm.get("groups", []):
            for r in g.get("readings", []):
                (on if r["type"] == "ja_on" else kun if r["type"] == "ja_kun" else []).append(r["value"])
            for m in g.get("meanings", []):
                if m.get("lang") in sig:
                    sig[m["lang"]].append(m["value"])
        misc = ch.get("misc", {})
        kanji.append({"kanji": ch["literal"], "on": on, "kun": kun, "en": sig["en"][:5], "pt": sig["pt"][:5],
                      "jlpt_antigo": misc.get("jlptLevel"), "serie_escolar": misc.get("grade"),
                      "tracos": (misc.get("strokeCounts") or [None])[0], "freq": misc.get("frequency")})
    kanji.sort(key=lambda k: (k["freq"] or 9999))
    comum.log(f"japones: {len(palavras)} palavras, {len(kanji)} kanji")
    return {"lingua": "ja", "versao_fonte": f"JMdict-simplified {tag}", "palavras": palavras, "kanji": kanji}
