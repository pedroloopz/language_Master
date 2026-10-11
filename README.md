# LANGUAGE MASTER · dados

Dicionário e áudio para o app LANGUAGE MASTER (japonês N3→N2 e alemão A2→B1).
O workflow **gerar** monta tudo e publica numa **Release** (no dia 3 de cada mês, ou à mão).

## Arquivos da Release

| Arquivo | Conteúdo |
|---|---|
| `ja.json` (ou `ja-n5.json`…`ja-n2.json` se passar de 8 MB) | ~8.000 palavras N5–N2: escrita, leitura em kana, significados em inglês e alemão, classe, exemplo, nível; e os kanji (on/kun, significados com português quando existe) |
| `de.json` (ou `de-a1.json`…) | ~6.000 palavras mais frequentes: artigo, plural, Präteritum, Partizip II, IPA, significado em inglês, exemplo |
| `ja-audio-001.mp3`… / `de-audio-001.mp3`… | Pacotes MP3 de até 10 MB (~300 palavras cada) |
| `ja-audio-indice.json` / `de-audio-indice.json` | Início e fim (ms) de cada palavra dentro do pacote |
| `LICENCAS.md` | Origem e licença de cada base e de cada áudio |

Cada palavra traz `audio: {pacote, ini_ms, fim_ms, tipo}` (`tipo` = `nativo` ou `sintetico`).
Áudio nativo: Wikimedia Commons (Wiktionary e Lingua Libre). Japonês sem gravação: VOICEVOX
(crédito obrigatório: VOICEVOX:四国めたん).

## No app
`python montar_app.py saida app` gera, a partir de uma Release baixada em `saida/`, os arquivos que o app usa
(`audio-mapa.json`, `dic-ja.json`, `dic-de.json`, pacotes MP3 e `LICENCAS.md`); eles são publicados junto do
Artifact, na pasta `dados/`.

## Como rodar
Celular: **Actions → gerar → Run workflow**. Leva de 1 a 3 horas (o áudio sintético é a parte lenta).
Local: `pip install -r requirements.txt && python gerar.py` (precisa de ffmpeg e do VOICEVOX em `localhost:50021`).
Testes: `python -m pytest tests`.
