// Compara o FSRS-6 do app com o ts-fsrs (referência), em sequências de revisões em dias inteiros.
const fs=require("fs"), vm=require("vm"), T=require("ts-fsrs");   // npm i ts-fsrs
const html=fs.readFileSync(process.argv[2],"utf8");
const ini=html.indexOf("const W=[0.212"), fim=html.indexOf("/* =====", html.indexOf("function schedule("));
const ctx={settings:{retencao:0.9},TODAY:"",Math};
ctx.diffDays=(a,b)=>Math.round((new Date(b+"T12:00")-new Date(a+"T12:00"))/864e5);
ctx.addDays=(a,n)=>{const d=new Date(a+"T12:00");d.setDate(d.getDate()+n);return d.toISOString().slice(0,10);};
vm.createContext(ctx); vm.runInContext(html.slice(ini,fim)+";this.schedule=schedule;",ctx);
const f=T.fsrs(T.generatorParameters({enable_short_term:false,enable_fuzz:false,request_retention:0.9,maximum_interval:730}));
let pior={S:0,D:0,I:0}, n=0, rnd=1;
const R=()=>(rnd=(rnd*48271)%2147483647)/2147483647;
for(let caso=0;caso<2000;caso++){
  let it={estado:2}, card=T.createEmptyCard(new Date("2026-01-01T12:00Z")), dia="2026-01-01";
  for(let k=0;k<8;k++){
    const r=1+Math.floor(R()*4);
    ctx.TODAY=dia; ctx.schedule(it,r);
    card=f.next(card,new Date(dia+"T12:00Z"),r).card;
    const dS0=Math.abs(it.S-card.stability)/card.stability, dD=Math.abs(it.D-card.difficulty), dI=Math.abs(it.intervalo-card.scheduled_days);
    const dS=dS0; pior={S:Math.max(pior.S,dS),D:Math.max(pior.D,dD),I:Math.max(pior.I,dI)}; n++;
    dia=ctx.addDays(dia, Math.max(1, Math.round(it.intervalo*(0.5+R()))));   // revisa antes ou depois do dia certo
  }
}
console.log(JSON.stringify({revisoes:n, maior_dif_estabilidade_rel:+pior.S.toFixed(4), maior_dif_dificuldade:+pior.D.toFixed(3), maior_dif_intervalo_dias:pior.I}));
// intervalo pode diferir: o ts-fsrs força Difícil < Bom < Fácil (botões); o app dá a nota sozinho
process.exit(pior.S<0.01 && pior.D<0.01 ? 0 : 1);
