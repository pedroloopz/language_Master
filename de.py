"""Alemao: ~6.000 palavras mais frequentes (wordfreq), dados do Wiktionary via kaikki.org.

Por palavra: artigo (der/die/das), plural, Praeteritum e Partizip II (verbos), IPA, significado
em ingles, 1 exemplo e o audio do Commons citado no proprio Wiktionary.
"""
import json

import comum

ALVO = 6000
KAIKKI = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"
ARTIGO = {"masculine": "der", "feminine": "die", "neuter": "das"}
POS_PREF = ["noun", "verb", "adj", "adv", "prep", "conj", "pron", "det", "article", "num", "intj", "particle"]


def frequentes(n):
    from wordfreq import top_n_list
    out = []
    for w in top_n_list("de", n * 3):
        if w.isalpha() and len(w) > 1 and w not in out:
            out.append(w)
        if len(out) >= n:
            break
    return out


def forma(e, *tags):
    for f in e.get("forms", []):
        t = set(f.get("tags", []))
        if all(x in t for x in tags) and f.get("form") and f["form"] not in ("-", "—"):
            return f["form"]
    return None


def resumir(e):
    pos = e.get("pos")
    tags = {t for s in e.get("senses", []) for t in s.get("tags", [])} | \
        {t for h in e.get("head_templates", []) for t in h.get("args", {}).values() if isinstance(t, str)}
    item = {"palavra": e["word"], "classe": pos}
    if pos == "noun":
        genero = next((g for g in ("masculine", "feminine", "neuter") if g in tags
                       or any(g in f.get("tags", []) for f in e.get("forms", []))), None)
        if not genero:  # cabeca do Wiktionary: {{de-noun|m|...}}
            g1 = next((h.get("args", {}).get("1", "") for h in e.get("head_templates", [])), "")
            genero = {"m": "masculine", "f": "feminine", "n": "neuter"}.get(g1[:1])
        item["artigo"] = ARTIGO.get(genero)
        item["plural"] = forma(e, "nominative", "plural") or forma(e, "plural")
    if pos == "verb":
        item["praeteritum"] = forma(e, "first-person", "singular", "past") or forma(e, "past")
        item["partizip2"] = forma(e, "participle", "past")
        item["auxiliar"] = forma(e, "auxiliary")
    item["ipa"] = next((s["ipa"] for s in e.get("sounds", []) if s.get("ipa")), None)
    item["en"] = []
    for s in e.get("senses", []):
        for g in s.get("glosses", [])[:1]:
            if g not in item["en"] and "form of" not in g and "inflection of" not in g:
                item["en"].append(g)
        if len(item["en"]) >= 3:
            break
    item["exemplo"] = None
    for s in e.get("senses", []):
        for ex in s.get("examples", []):
            if ex.get("text") and len(ex["text"]) < 160:
                item["exemplo"] = {"de": ex["text"], "en": ex.get("english") or ex.get("translation"),
                                   "fonte": "Wiktionary (CC BY-SA 4.0)"}
                break
        if item["exemplo"]:
            break
    item["audios_wiktionary"] = [s["audio"] for s in e.get("sounds", []) if s.get("audio")]
    return item


def gerar():
    alvo = frequentes(ALVO)
    rank = {w: i for i, w in enumerate(alvo)}
    melhores = {}            # palavra minuscula -> [entradas]
    caminho = comum.baixar(KAIKKI)
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            e = json.loads(linha)
            chave = e.get("word", "").lower()
            if chave in rank and e.get("pos") in POS_PREF and e.get("senses"):
                it = resumir(e)
                if it["en"]:
                    melhores.setdefault(chave, []).append(it)
    palavras = []
    for w in alvo:
        ents = melhores.get(w)
        if not ents:
            continue
        # substantivo com maiuscula quando existe (Haus), senao a classe mais comum
        ents.sort(key=lambda x: (POS_PREF.index(x["classe"]), x["palavra"] != x["palavra"].capitalize()))
        principal = ents[0]
        r = rank[w]
        nivel = "A1" if r < 1000 else "A2" if r < 2500 else "B1"
        palavras.append({"id": f"de-{r + 1:05d}", "rank": r + 1, "nivel": nivel,
                         "nivel_fonte": "estimado pela frequencia (wordfreq)", **principal,
                         "outras_classes": [x["classe"] for x in ents[1:3] if x["classe"] != principal["classe"]]})
    comum.log(f"alemao: {len(palavras)} palavras (de {len(alvo)} frequentes)")
    return {"lingua": "de", "versao_fonte": "kaikki.org (Wiktionary em ingles)", "palavras": palavras}
