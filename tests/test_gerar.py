"""Testes sem rede: empacotamento de audio, divisao do JSON, Lingua Libre, campos do alemao/japones."""
import json
import math
import subprocess
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import audio  # noqa: E402
import comum  # noqa: E402
import de  # noqa: E402
import ja  # noqa: E402


def tom(seg, freq=440):
    n = int(audio.TAXA * seg)
    return b"".join(int(8000 * math.sin(2 * math.pi * freq * i / audio.TAXA)).to_bytes(2, "little", signed=True)
                    for i in range(n))


def test_lingua_libre_nome():
    assert audio.palavra_lingua_libre("LL-Q5287 (jpn)-Fulano-Beltrano-猫.wav") == "猫"
    assert audio.palavra_lingua_libre("LL-Q188 (deu)-Ich-Haus.wav") == "Haus"
    assert audio.palavra_lingua_libre("De-Haus.ogg") is None


def test_empacotar_tempos_e_tamanho(tmp_path, monkeypatch):
    monkeypatch.setattr(comum, "SAIDA", tmp_path)
    monkeypatch.setattr(audio, "POR_PACOTE", 2)
    dados = {"palavras": [{"id": f"x{i}"} for i in range(5)]}
    sons = {f"x{i}": (tom(0.5 + 0.1 * i), {"tipo": "nativo" if i % 2 == 0 else "sintetico",
                                             "autor": "A", "licenca": "CC BY-SA 4.0", "arquivo": "f", "pagina": "p"})
            for i in range(4)}                                   # x4 sem audio
    r = audio.empacotar(dados, "ja", sons)
    assert r["pacotes"] == ["ja-audio-001.mp3", "ja-audio-002.mp3"] and r["nativos"] == 2 and r["sinteticos"] == 2
    idx = json.loads((tmp_path / "ja-audio-indice.json").read_text())
    p1 = idx["pacotes"][0]["palavras"]
    assert p1["x0"] == [0, 500]
    assert p1["x1"][0] == round((0.5 + audio.PAUSA) * 1000) and p1["x1"][1] - p1["x1"][0] == 600
    assert "audio" not in dados["palavras"][4]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(tmp_path / "ja-audio-001.mp3")], capture_output=True, text=True).stdout)
    assert abs(dur - (0.5 + 0.6 + 2 * audio.PAUSA)) < 0.1


def test_json_divide_por_nivel_acima_de_8mb(tmp_path, monkeypatch):
    monkeypatch.setattr(comum, "SAIDA", tmp_path)
    monkeypatch.setattr(comum, "LIMITE_JSON", 2000)
    dados = {"lingua": "ja", "kanji": [{"kanji": "猫"}],
             "palavras": [{"id": i, "nivel": nv, "t": "x" * 40} for i, nv in enumerate(["N5", "N4"] * 15)]}
    arqs = comum.gravar_json("ja", dados, dividir_por="nivel")
    assert arqs == ["ja-n5.json", "ja-n4.json"]
    assert "kanji" in json.loads((tmp_path / "ja-n5.json").read_text())
    assert "kanji" not in json.loads((tmp_path / "ja-n4.json").read_text())


def test_alemao_substantivo_e_verbo():
    haus = {"word": "Haus", "pos": "noun", "head_templates": [{"args": {"1": "n"}}],
            "forms": [{"form": "Häuser", "tags": ["nominative", "plural"]}],
            "sounds": [{"ipa": "/haʊ̯s/"}, {"audio": "De-Haus.ogg"}],
            "senses": [{"glosses": ["house"], "examples": [{"text": "Das Haus ist groß.", "english": "The house is big."}]}]}
    r = de.resumir(haus)
    assert r["artigo"] == "das" and r["plural"] == "Häuser" and r["ipa"] == "/haʊ̯s/"
    assert r["en"] == ["house"] and r["exemplo"]["de"] == "Das Haus ist groß." and r["audios_wiktionary"] == ["De-Haus.ogg"]
    gehen = {"word": "gehen", "pos": "verb",
             "forms": [{"form": "ging", "tags": ["first-person", "singular", "past"]},
                       {"form": "gegangen", "tags": ["participle", "past"]}, {"form": "sein", "tags": ["auxiliary"]}],
             "senses": [{"glosses": ["to go"]}]}
    r = de.resumir(gehen)
    assert (r["praeteritum"], r["partizip2"], r["auxiliar"]) == ("ging", "gegangen", "sein")


def test_japones_glosas_e_exemplo():
    w = {"sense": [{"gloss": [{"lang": "eng", "text": "cat"}, {"lang": "ger", "text": "Katze"}],
                    "examples": [{"sentences": [{"land": "jpn", "text": "猫がいる。"}, {"lang": "eng", "text": "There is a cat."}]}]}]}
    assert ja.glosas(w, "eng") == ["cat"] and ja.glosas(w, "ger") == ["Katze"]
    assert ja.exemplo(w)["ja"] == "猫がいる。" and ja.exemplo(w)["en"] == "There is a cat."


def test_montar_app(tmp_path, monkeypatch):
    import montar_app
    monkeypatch.setattr(comum, "SAIDA", tmp_path)
    ja_d = {"palavras": [{"id": "ja-1", "escrita": "猫", "leitura": "ねこ", "nivel": "N5", "en": ["cat"], "de": ["Katze"],
                          "classe": ["noun"], "exemplo": {"ja": "猫がいる。", "en": "There is a cat."}},
                         {"id": "ja-2", "escrita": "根子", "leitura": "ねこ", "nivel": "N2", "en": ["root"], "de": []}],
            "kanji": [{"kanji": "猫", "on": ["ビョウ"], "kun": ["ねこ"], "en": ["cat"], "pt": []}]}
    de_d = {"palavras": [{"id": "de-1", "palavra": "Haus", "artigo": "das", "plural": "Häuser", "nivel": "A1",
                          "ipa": "/haʊ̯s/", "en": ["house"], "exemplo": None}]}
    sons = {"ja-1": (tom(0.3), {"tipo": "nativo", "autor": "A", "licenca": "CC0", "arquivo": "f", "pagina": "p"}),
            "ja-2": (tom(0.3), {"tipo": "sintetico", "autor": "V", "licenca": "x"})}
    audio.empacotar(ja_d, "ja", sons)
    audio.empacotar(de_d, "de", {"de-1": (tom(0.4), {"tipo": "nativo", "autor": "B", "licenca": "CC BY", "arquivo": "g", "pagina": "q"})})
    comum.gravar_json("ja", ja_d)
    comum.gravar_json("de", de_d)
    mapa = montar_app.montar(tmp_path, tmp_path / "app")
    assert mapa["pacotes"] == ["ja-audio-001.mp3", "de-audio-001.mp3"]
    assert mapa["ja"]["ねこ"][3] == "n" and mapa["ja"]["根子"][3] == "s" and mapa["de"]["Haus"][0] == 1
    dic = json.loads((tmp_path / "app" / "dic-ja.json").read_text())
    assert dic["palavras"][0][:4] == ["猫", "ねこ", "N5", "cat"] and dic["kanji"][0][0] == "猫"
    assert (tmp_path / "app" / "de-audio-001.mp3").exists()


def test_leitura_comparavel():
    assert audio.so_kana("ガッコー") == audio.so_kana("がっこう")
    assert audio.so_kana("ワタシワ") == audio.so_kana("わたしは")
    assert audio.so_kana("マイニチヤサイオタベル") == audio.so_kana("まいにち やさいを たべる。")
    assert audio.so_kana("セーブツ") != audio.so_kana("なまもの")


def test_frases_e_montar_app(tmp_path, monkeypatch):
    import montar_app
    monkeypatch.setattr(comum, "SAIDA", tmp_path)
    wav = lambda t: subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(audio.TAXA), "-ac", "1", "-i", "pipe:0",
                                    "-f", "wav", "pipe:1"], input=tom(0.2 * len(t.split())), capture_output=True).stdout
    r = audio.frases("de", [["Ich habe Zeit.", ""], ["Wir gehen jetzt nach Hause.", ""]], falar=wav)
    assert r == {"arquivos": ["de-frases.json", "de-frases-001.mp3"], "frases": 2}
    d = json.loads((tmp_path / "de-frases.json").read_text())
    assert d["frases"][0][2:] == [0, 0, 600] and d["frases"][1][3] == round((0.6 + audio.PAUSA) * 1000)
    mapa = montar_app.montar(tmp_path, tmp_path / "app")
    assert mapa["pacotes"] == ["de-frases-001.mp3"] and mapa["de"]["Ich habe Zeit."] == [0, 0, 600, "s"]
    assert (tmp_path / "app" / "de-frases-001.mp3").exists()
