# CLAUDE.md — language_master (dados do LANGUAGE MASTER)

## O que é
Gera os dados de dicionário + áudio do app LANGUAGE MASTER (um Artifact no Claude) e publica numa
Release do GitHub. Não tem bot nem Telegram. Workflow `gerar`: à mão e dia 3 de cada mês (03h41 BRT).

- `gerar.py` orquestra; `ja.py` (JMdict + Kanjidic + listas JLPT de Waller + wordfreq); `de.py` (kaikki.org/Wiktionary + wordfreq); `audio.py` (Commons/Lingua Libre, VOICEVOX, pacotes MP3 ≤ 10 MB + índice); `comum.py` (downloads, Commons, JSON ≤ 8 MB dividido por nível).
- `tatoeba.py`: frases reais do Tatoeba com gravação nativa de licença aberta (sem NC/ND) e tradução em português → `<lingua>-tatoeba.json` + `<lingua>-tatoeba-NNN.mp3`; o app usa na Escuta/Trajeto as que cabem no nível. `furigana.js` (kuroshiro + kuromoji, `npm install`): furigana das frases do app e do Tatoeba → `ja-furigana.json`.
- `montar_app.py` transforma a Release nos arquivos do app (`dados/` do Artifact: mapa de áudio, dicionários compactos, MP3).
- `app/index.html` é o código do app (o Artifact). Ao mudar o app, salve aqui. `frases.js` tira dele as frases fixas; o `gerar` grava cada uma com voz sintética (japonês: VOICEVOX; alemão: Piper/Thorsten, CC0) em `<lingua>-frases-NNN.mp3` (o app do Claude no Android não tem voz do navegador).
- Saída em `saida/`; `LICENCAS.md` é regravado na raiz a cada Release.

## Segredos e variáveis
- Nenhum. Usa só o `GITHUB_TOKEN` automático do Actions (Release e API do GitHub).

## Como testar
- `pip install -r requirements.txt pytest && npm install && python -m pytest tests` (sem rede: pacotes, divisão do JSON, campos, Tatoeba, furigana e o FSRS do app conferido contra o `ts-fsrs`).
- No GitHub: Actions → `gerar` → Run workflow (`linguas: de` é o mais rápido, sem VOICEVOX). Também roda sozinho quando `tatoeba.py` ou `furigana.js` mudam.
- Publicar no Artifact: baixar a Release em `saida/`, `python montar_app.py saida dados_novos` e publicar `index.html` + `dados/` (≤ 64 MB por publicação).

## Regras do Pedro
- Pedro não tem computador: tudo no GitHub Actions e configurável pelo celular.
- Não quebre o que funciona; leia antes de mudar. Teste, depois commit e push direto na `main`.
- Sem chamadas à API paga do Claude. Fontes só com licença aberta, citadas no `LICENCAS.md` (autor e licença de cada áudio).
- JSON ≤ 8 MB por arquivo; pacotes MP3 ≤ 10 MB. Áudio sintético sempre marcado como `sintetico`.
- Dependeu de decisão do Pedro → pare e pergunte em uma frase, com opções.

## Como trabalhar
- **Pense antes de codar:** diga as suposições; se o pedido aceita mais de uma leitura, pergunte.
- **Simplicidade primeiro:** o menor código que resolve; nada que não foi pedido.
- **Mudanças cirúrgicas:** só o necessário; não reformate o vizinho.
- **Objetivo verificável:** defina como provar que funcionou (teste ou execução) e só termine quando passar.
