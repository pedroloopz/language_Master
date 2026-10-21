# Pedidos de textos novos (botão do app)

O botão **Textos novos com áudio** (Praticar > Escuta e Praticar > Leitura) grava um pedido no banco do
Artifact. Uma tarefa agendada do Claude, a cada 6 horas, segue este roteiro.

- Artifact: `https://claude.ai/code/artifact/7ca7f052-2259-4a3a-a0b5-b6bc3afb08d7`
- Pedidos: `ArtifactData`, coleção `data/users/me/app/pedidos`
  - campos: `lang` (`ja`|`de`), `nivel` (N3/N2 ou A2/B1/B2), `qtd`, `tema` (opcional), `estado`, `criado`
  - estados: `pendente` → `escrevendo` → `gravando` (com `run_id`) → `pronto` (ou `erro`, com `nota` curta em português para o Pedro)
  - toda escrita leva `if_version` da última leitura

## 1. Pedido `gravando`: o áudio terminou?
`gh api repos/pedroloopz/language_Master/actions/runs/<run_id> --jq '.status,.conclusion'`
- `in_progress`/`queued`: não faça nada.
- `failure`: leia o log (`gh api .../runs/<id>/jobs`), corrija se for do código, reenvie o `gerar` e atualize `run_id`;
  se não der, `estado: erro` com `nota`.
- `success`: publique (passo 3) e marque `estado: pronto`, `nota: "<n> textos novos em Praticar > Leitura e na Escuta"`.
  Se o job `publicar` falhou mas a Release saiu, publique mesmo assim.

## 2. Pedido `pendente`: escrever os textos
1. Marque `escrevendo`.
2. Base do app: leia a versão publicada (`Artifact` action `read`, `path: "index.html"`). Se ela for diferente de
   `app/index.html`, a publicada vence: copie-a para `app/index.html` (tirando o esqueleto `<!doctype…><body>` e
   `</body></html>` que a publicação acrescenta).
3. Escreva `qtd` textos novos em `window.LM_READ`, no fim da lista, no mesmo formato:
   `{id:"r-<lang>-<próximo número>",lang,lvl,titulo,frases:[[texto, kana (ja; vazio no de), tradução pt]],perguntas:[[pergunta pt, certa, errada, errada, errada]]}`
   - nível do pedido; 6 frases por texto, a maioria longas (japonês ≥ 20 caracteres; alemão ≥ 9 palavras);
   - japonês: kana em hiragana com espaços entre os blocos, como nos textos existentes (o VOICEVOX lê o kana);
     números e siglas escritos como se leem (ex.: `エーアイ`);
   - tema do pedido, se houver; sem repetir temas dos títulos que já existem; vocabulário e gramática do nível;
   - 2 perguntas de compreensão em português por texto, com a certa em segundo lugar.
4. Confira: `node frases.js app/index.html` roda e o número de frases aumentou; `python -m pytest tests` passa.
5. Commit e push direto na `main`; dispare o `gerar`
   (`gh api repos/pedroloopz/language_Master/actions/workflows/gerar.yml/dispatches -X POST -f ref=main -f 'inputs[linguas]=ja,de'`; sempre as duas línguas, porque o `audio-mapa.json` é montado de uma Release só e perderia a outra)
   e marque `gravando` com o `run_id` do run novo.
6. Publique já o `index.html` no Artifact (os textos aparecem; o áudio chega no passo 3).

## 3. Publicar a Release no app
1. `gh release download <tag mais nova> -R pedroloopz/language_Master -D saida`
2. `python montar_app.py saida dados_novos`
3. Confira no `audio-mapa.json` que as frases dos textos novos têm áudio (chave = texto ou kana).
4. Publique no Artifact (`url` acima): `index.html` + `dados/audio-mapa.json` + os MP3 novos ou de tamanho diferente
   (`Artifact` action `list`, `scope: "files"`, mostra os tamanhos publicados). No máximo 64 MB por publicação:
   divida em várias publicações para a mesma `url`. Não declare `capabilities` (o app mantém as que tem).
