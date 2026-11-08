// Furigana do japonês com kuroshiro + kuromoji (dicionário vem no pacote npm; roda offline).
// Uso: node furigana.js frases.json [tatoeba-ja.json ...] > ja-furigana.json
// Entradas: {"ja":[[texto, kana]]} (frases.js) ou [[texto, kana]]; kana pode ser "".
// Saída: {texto: "{新|あたら}しい{習慣|しゅうかん}"}. Só frases com kanji. Se a frase já tem a leitura
// conferida à mão (kana) e o kuroshiro lê diferente, ela fica fora: o app mostra a linha de kana como antes.
const fs = require("fs");
const Kuroshiro = require("kuroshiro").default, Analisador = require("kuroshiro-analyzer-kuromoji");
const KANJI = /[㐀-鿿々]/;
const soKana = s => [...String(s)].map(c => (c >= "ァ" && c <= "ヶ") ? String.fromCharCode(c.charCodeAt(0) - 0x60) : c)
  .filter(c => c >= "ぁ" && c <= "ゖ" || c === "ー").join("");
const compacta = html => html.replace(/<ruby>(.*?)<rp>\(<\/rp><rt>(.*?)<\/rt><rp>\)<\/rp><\/ruby>/g, "{$1|$2}");

(async () => {
  const k = new Kuroshiro(); await k.init(new Analisador());
  const pares = [];
  for (const arq of process.argv.slice(2)) {
    const d = JSON.parse(fs.readFileSync(arq, "utf8"));
    pares.push(...(Array.isArray(d) ? d : d.ja || []));
  }
  const out = {}; let fora = 0;
  for (const [texto0, kana] of pares) {
    const texto = String(texto0 || "").replace(/\|/g, "").trim();
    if (!texto || out[texto] || !KANJI.test(texto) || /[{}]/.test(texto)) continue;
    if (kana && soKana(await k.convert(texto, { to: "hiragana" })) !== soKana(kana)) { fora++; continue; }
    out[texto] = compacta(await k.convert(texto, { mode: "furigana", to: "hiragana" }));
  }
  process.stderr.write(`furigana: ${Object.keys(out).length} frases; ${fora} ficaram fora (leitura diferente da conferida)\n`);
  process.stdout.write(JSON.stringify(out));
})();
