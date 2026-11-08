"""Tatoeba (sem rede): licencas, escolha das frases, pacotes e montagem no app; furigana."""
import bz2
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import audio  # noqa: E402
import comum  # noqa: E402
import montar_app  # noqa: E402
import tatoeba  # noqa: E402
from test_gerar import tom  # noqa: E402


def test_licenca_aberta():
    for ok in ["CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0", "Public domain"]:
        assert tatoeba.licenca_aberta(ok), ok
    for nao in ["", "\\N", "CC BY-NC 4.0", "CC BY-NC-ND 3.0", "CC BY-ND 4.0", "For use on Tatoeba only"]:
        assert not tatoeba.licenca_aberta(nao), nao


def bz(path, linhas):
    path.write_bytes(bz2.compress("\n".join("\t".join(l) for l in linhas).encode() + b"\n"))


def tarbz(path, nome, linhas):
    dados = ("\n".join("\t".join(l) for l in linhas) + "\n").encode()
    with tarfile.open(path, "w:bz2") as t:
        info = tarfile.TarInfo(nome)
        info.size = len(dados)
        t.addfile(info, io.BytesIO(dados))


def test_gerar_alemao_ponta_a_ponta(tmp_path, monkeypatch):
    cache, saida = tmp_path / "cache", tmp_path / "saida"
    cache.mkdir()
    monkeypatch.setattr(comum, "CACHE", cache)
    monkeypatch.setattr(comum, "SAIDA", saida)
    longa = "Ich habe gestern meinen alten Freund im Park getroffen."
    bz(cache / "per_language_deu_deu_sentences_detailed.tsv.bz2", [
        ["1", "deu", longa, "anna", "x", "x"],
        ["2", "deu", "Kurz.", "anna", "x", "x"],                                   # curta demais
        ["3", "deu", "Wir fahren morgen mit dem Zug nach Berlin.", "ben", "x", "x"],   # audio NC
        ["4", "deu", "Das Wetter ist heute wirklich sehr schön gewesen.", "ben", "x", "x"]])
    bz(cache / "per_language_por_por_sentences_detailed.tsv.bz2", [["10", "por", "Ontem encontrei meu velho amigo no parque.", "c", "x", "x"],
                                                                   ["11", "por", "O tempo hoje estava muito bom.", "c", "x", "x"],
                                                                   ["12", "por", "Amanhã vamos de trem para Berlim.", "c", "x", "x"]])
    bz(cache / "per_language_deu_deu-por_links.tsv.bz2", [["1", "10"], ["4", "11"], ["3", "12"], ["4", "99"]])
    tarbz(cache / "sentences_with_audio.tar.bz2", "sentences_with_audio.csv", [
        ["1", "101", "gravador", "CC BY 4.0", "\\N"], ["2", "102", "g", "CC BY 4.0", "\\N"],
        ["3", "103", "g", "CC BY-NC 4.0", "\\N"], ["4", "104", "outro", "CC BY-SA 4.0", "\\N"]])
    monkeypatch.setattr(tatoeba, "baixar_audio", lambda id_audio, iso, sid: tom(0.5))
    monkeypatch.setattr(tatoeba.time, "sleep", lambda s: None)
    r = tatoeba.gerar("de")
    d = json.loads((saida / "de-tatoeba.json").read_text())
    assert r["frases"] == 2 and r["arquivos"] == ["de-tatoeba.json", "de-tatoeba-001.mp3"]
    assert sorted(f[0] for f in d["frases"]) == ["Das Wetter ist heute wirklich sehr schön gewesen.", longa]   # sem a curta e a NC
    fr = {f[0]: f for f in d["frases"]}
    assert fr[longa][1:3] == ["Ontem encontrei meu velho amigo no parque.", "pt"]
    assert [1, "anna", "gravador", "CC BY 4.0"] in d["creditos"]
    assert d["frases"][0][4:6] == [0, 500]

    destino = tmp_path / "app"
    mapa = montar_app.montar(saida, destino)
    assert mapa["de"][longa][3] == "n" and "de-tatoeba-001.mp3" in mapa["pacotes"]
    assert [longa, "Ontem encontrei meu velho amigo no parque.", "pt"] in json.loads((destino / "tatoeba-de.json").read_text())
    assert (destino / "de-tatoeba-001.mp3").exists()


@pytest.mark.skipif(not shutil.which("node") or not (RAIZ / "node_modules" / "kuroshiro").exists(),
                    reason="sem node ou sem kuroshiro (npm install)")
def test_furigana(tmp_path):
    entrada = tmp_path / "e.json"
    entrada.write_text(json.dumps({"ja": [["日本語を|勉強しています。", "にほんごを べんきょう しています。"],
                                          ["今日は雨です。", "あした は あめ です。"],        # leitura conferida diferente: fica fora
                                          ["ありがとう", ""]]}, ensure_ascii=False))
    r = subprocess.run(["node", "furigana.js", str(entrada)], cwd=RAIZ, capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == {"日本語を勉強しています。": "{日本語|にほんご}を{勉強|べんきょう}しています。"}
