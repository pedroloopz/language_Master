// Lista as frases fixas que o app fala (gramática, exemplos de vocabulário, textos e poemas).
// Uso: node frases.js app/index.html > frases.json   ->  {"ja":[[texto, kana]], "de":[[texto, ""]]}
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync(process.argv[2] || "app/index.html", "utf8");
const dados = html.match(/<script>([\s\S]*?)<\/script>/)[1];      // 1º script: só o conteúdo (window.LM_*)
const ctx = { window: {} }; vm.createContext(ctx); vm.runInContext(dados, ctx);
const W = ctx.window, BLANK = /＿＿＿|___/, out = { ja: new Map(), de: new Map() };
const add = (l, t, k) => { t = String(t || "").replace(/\|/g, "").trim(); if (t && !out[l].has(t)) out[l].set(t, k || ""); };
for (const [l, nomes] of [["ja", ["LM_JA1", "LM_JA2", "LM_JA3", "LM_JA4", "LM_JA5"]], ["de", ["LM_DE", "LM_DE2"]]])
  for (const n of nomes) for (const p of (W[n] || {}).points || []) {
    (p.x || []).forEach(x => add(l, x[0].split("|").map(s => s.trim()).join(l === "de" ? " " : ""), x[1]));
    (p.q || []).forEach(q => add(l, q[0].replace(BLANK, q[1][0]), l === "ja" ? q[2] : ""));
  }
for (const [l, nomes] of [["ja", ["LM_VJA", "LM_VJA2", "LM_VJA3"]], ["de", ["LM_VDE", "LM_VDE2", "LM_VDE3"]]])
  nomes.map(n => W[n] || "").join("\n").split("\n").forEach(linha => {
    const f = linha.trim().split("|"); if (f.length < 6) return;
    l === "ja" ? add(l, f[3], f[4]) : add(l, f[4], "");
  });
for (const r of W.LM_READ || []) r.frases.forEach(f => add(r.lang, f[0], f[1]));
for (const p of W.LM_POEM || []) p.versos.forEach(v => add(p.lang, v[0], v[1]));
const res = {}; for (const l in out) res[l] = [...out[l]];
process.stdout.write(JSON.stringify(res));
