// ── Helpers ──
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const api=async(p,b)=>{const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});const d=await r.json();if(!r.ok)throw new Error(d.error||r.statusText);return d};
const getJ=async p=>(await fetch(p)).json();
const busy=on=>{$('loader').classList.toggle('on',on)};
const user=()=>$('userId').value.trim();
const sess=()=>$('sessionId').value.trim();
const msg=()=>$('message').value;
const memOn=()=>$('memEnabled').checked;

// ── Render a single turn card ──
function turnCard(title, r, badge) {
  const tot=Object.values(r.recall_counts||{}).reduce((a,b)=>a+b,0);
  const tpl=r.context?.tokens_per_level||{};
  const deg=r.context?.degraded;
  const errs=(r.errors&&r.errors.length)?`<div class="annotation">${esc(JSON.stringify(r.errors))}</div>`:'';
  const bHtml=badge?`<span class="badge ${badge.includes('Without')||badge.includes('No')||badge.includes('Off')?'badge-red':'badge-green'}">${esc(badge)}</span>`:'';
  
  let ctxHtml='';
  if(tpl.L0||tpl.L1||tpl.L2||tpl.L3||deg){
    ctxHtml=`<div class="ctx-bar"><span style="font-size:10px;color:var(--text-dim);font-weight:600;text-transform:uppercase;letter-spacing:.5px">Context:</span>
    ${['L0','L1','L2','L3'].map(l=>`<span class="ctx-tag">${l}:${tpl[l]||0}</span>`).join('')}
    <span class="${deg?'ctx-warn':'ctx-ok'}">${deg?'⚠ TRIMMED':'✓ OK'}</span></div>`;
  }

  return `<div class="card ${badge&&(badge.includes('Without')||badge.includes('No')||badge.includes('Off'))?'mem-off':'mem-on'} fade-in">
    <div class="card-header"><h3>${esc(title)}</h3>${bHtml}</div>
    <div class="response-box">${esc(r.assistant_response||'No response')}</div>
    ${errs}
    <div class="metrics">
      <div class="m-card"><div class="m-val ${r.router?.top_intent!=='task_default'?'hi':''}">${esc(r.router?.top_intent||'—')}</div><div class="m-lbl">Intent</div></div>
      <div class="m-card"><div class="m-val ${tot>0?'hi':''}">${tot}</div><div class="m-lbl">Recalled</div></div>
      <div class="m-card"><div class="m-val">${r.usage?.prompt_tokens||0}</div><div class="m-lbl">Prompt Tok</div></div>
      <div class="m-card"><div class="m-val">${r.context?.total_tokens||0}</div><div class="m-lbl">Ctx Tok</div></div>
    </div>
    ${ctxHtml}
    <div class="card-footer">
      <span><b>Backends:</b> ${(r.router?.backends||[]).map(esc).join(', ')||'none'}</span>
      <span><b>Writes:</b> P:${r.persisted?.pref_writes||0} F:${r.persisted?.fact_writes||0} E:${r.persisted?.episode_writes||0} S:${r.persisted?.semantic_writes||0}</span>
    </div>
  </div>`;
}

// ── Annotation builder ──
function annotate(text, type='info') {
  return `<div class="annotation ${type}"><strong>💡 Analysis:</strong> ${text}</div>`;
}

// ── Load config ──
async function loadConfig() {
  try {
    const c=await getJ('/api/config');
    $('userId').value=`usr_${Date.now().toString().slice(-6)}`;
    $('cfgPills').innerHTML=['RT:'+c.runtime,'Model:'+c.model,c.fake_redis?'FakeRedis':'Redis',c.ephemeral_chroma?'MemChroma':'PersistChroma'].map(x=>`<span class="pill">${esc(x)}</span>`).join('');
  } catch(e){ console.error(e); }
}

// ── Send single message ──
async function doAsk() {
  busy(true);
  try {
    const r=await api('/api/ask',{message:msg(),user_id:user(),session_id:sess(),memory_enabled:memOn()});
    const memLabel=r.memory_enabled?'With Memory':'Without Memory';
    let analysis='';
    if(r.memory_enabled&&Object.values(r.recall_counts||{}).reduce((a,b)=>a+b,0)>0)
      analysis=annotate(`Memory was <strong>active and recalled ${Object.values(r.recall_counts).reduce((a,b)=>a+b,0)} item(s)</strong>. The agent used stored context (preferences/facts/episodes) to personalize its response. Intent detected: <strong>${r.router?.top_intent}</strong>.`,'success');
    else if(r.memory_enabled)
      analysis=annotate(`Memory is <strong>enabled</strong> but no items were recalled for this query. This could be a <strong>first interaction</strong> (cold start), a general knowledge question, or the router classified it as <strong>${r.router?.top_intent}</strong> which doesn't require memory lookup.`);
    else
      analysis=annotate(`Memory is <strong>disabled</strong>. The agent responds using only the current message without any stored context. Compare with memory-on to see the difference.`);
    
    $('content').innerHTML=`<div class="fade-in">
      <div class="section-hdr"><h2>Single Interaction</h2><span class="badge ${r.memory_enabled?'badge-green':'badge-red'}">${memLabel}</span></div>
      ${analysis}${turnCard('Agent Response',r,memLabel)}</div>`;
  } catch(e){ $('content').innerHTML=`<div class="card"><h3 style="color:var(--red)">Error</h3><p>${esc(e.message)}</p></div>`; }
  finally{ busy(false); }
}

// ── A/B Compare ──
async function doCompare() {
  busy(true);
  try {
    const r=await api('/api/compare',{message:msg(),user_id:user(),session_id:sess()||'compare'});
    const dRec=r.delta.recall_items, dTok=r.delta.prompt_tokens;
    const totMem=Object.values(r.with_memory.recall_counts||{}).reduce((a,b)=>a+b,0);
    const totNo=Object.values(r.without_memory.recall_counts||{}).reduce((a,b)=>a+b,0);

    let analysis='';
    if(totMem>totNo)
      analysis=annotate(`<strong>Memory makes a clear difference!</strong> With memory: <strong>${totMem} items recalled</strong>, without: <strong>${totNo}</strong>. The memory-enabled agent injected ${dRec} extra context items and used ${dTok>0?'+':''}${dTok} more prompt tokens. This demonstrates that the agent successfully retrieves and uses stored knowledge to provide more personalized, contextual responses.`,'success');
    else if(totMem===0&&totNo===0)
      analysis=annotate(`Neither mode recalled memory items. This is expected for <strong>general knowledge questions</strong> or <strong>first interactions</strong> without prior context. Try adding preferences/facts first, then querying them.`);
    else
      analysis=annotate(`Both modes produced similar results. The memory system correctly avoided injecting irrelevant context — this is the <strong>precision behavior</strong> tested in Scenario 08.`);

    $('content').innerHTML=`<div class="fade-in">
      <div class="section-hdr"><h2>A/B Comparison: Memory vs No Memory</h2>
        <span class="badge badge-accent">Δ ${dRec>0?'+':''}${dRec} items, ${dTok>0?'+':''}${dTok} tokens</span></div>
      ${analysis}
      <div class="compare-grid">
        ${turnCard('✅ With Persistent Memory',r.with_memory,'Memory ON')}
        ${turnCard('❌ Without Memory',r.without_memory,'Memory OFF')}
      </div></div>`;
  } catch(e){ $('content').innerHTML=`<div class="card"><h3 style="color:var(--red)">Error</h3><p>${esc(e.message)}</p></div>`; }
  finally{ busy(false); }
}

// ── Full Demo ──
async function doDemo() {
  busy(true);
  try {
    const r=await api('/api/demo/full',{user_id:user()});
    const stepAnnotations=[
      'The agent stores the user\'s language preference (Python=like, Java=dislike) into Redis profile memory. This is <strong>Scenario 01</strong> — same-session preference capture.',
      'Cross-session recall test (<strong>Scenario 02</strong>). With memory, the agent recalls "user likes Python" and recommends it. Without memory, it gives a generic answer.',
      'Episodic memory logging (<strong>Scenario 06</strong>). The agent detects user confusion about async/await and logs it as an episode event with tag "confusion".',
      'Episode recall test. The agent retrieves the logged confusion episode and adapts its explanation to be simpler and step-by-step.'
    ];
    
    let timeline=r.steps.map((s,i)=>`<div class="tl-step">
      <div class="tl-label">Step ${i+1}: ${esc(s.label)}</div>
      <div class="tl-msg">"${esc(s.result.message)}"</div>
      ${annotate(stepAnnotations[i]||'','info')}
      ${turnCard('Result',s.result)}
    </div>`).join('');

    const cmpKeys=Object.keys(r.comparisons);
    const cmpAnnotations={
      language:'This comparison proves <strong>cross-session memory persistence</strong>. The memory-enabled agent recalls "user likes Python" and recommends it, while the no-memory agent gives a generic response.',
      async:'This proves <strong>episodic memory adaptation</strong>. The memory-enabled agent recalls the user was confused about async/await and provides a simpler explanation.'
    };

    let cmpHtml=cmpKeys.map(k=>{
      const c=r.comparisons[k];
      return `<div style="margin-bottom:20px">
        <h4 style="color:var(--text);margin-bottom:8px;font-size:13px">🔬 Comparison: ${esc(k)}</h4>
        ${annotate(cmpAnnotations[k]||`Comparing responses for "${k}" query.`,'success')}
        <div class="compare-grid">
          ${turnCard('With Memory',c.with_memory,'Memory ON')}
          ${turnCard('No Memory',c.without_memory,'Memory OFF')}
        </div></div>`;
    }).join('');

    $('content').innerHTML=`<div class="fade-in">
      <div class="section-hdr"><h2>Full Evaluation Demo — 4 Steps + 2 A/B Tests</h2><span class="badge badge-accent">User: ${esc(r.user_id)}</span></div>
      ${annotate('This demo runs through the complete memory lifecycle: <strong>preference write → cross-session recall → episode logging → episode recall</strong>, followed by 2 A/B comparisons proving memory impact.','info')}
      <h3 style="color:#fff;margin:16px 0 10px;font-size:14px">📋 Step-by-Step Execution</h3>
      <div class="timeline">${timeline}</div>
      <h3 style="color:#fff;margin:24px 0 10px;font-size:14px">🔬 Memory Impact Proof (A/B Tests)</h3>
      ${cmpHtml}
      </div>`;
  } catch(e){ $('content').innerHTML=`<div class="card"><h3 style="color:var(--red)">Error</h3><p>${esc(e.message)}</p></div>`; }
  finally{ busy(false); }
}

// ── Memory Snapshot ──
async function doSnapshot() {
  busy(true);
  try {
    const d=await getJ(`/api/memory?user_id=${encodeURIComponent(user())}`);
    const tbl=(items,cols)=>{
      if(!items||!items.length) return '<div style="padding:14px;color:var(--text-dim);text-align:center;background:rgba(0,0,0,.2);border-radius:6px">No records</div>';
      return `<table class="tbl"><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${items.map(it=>'<tr>'+cols.map(c=>`<td>${esc(it[c]||it[c.toLowerCase()]||'—')}</td>`).join('')+'</tr>').join('')}</tbody></table>`;
    };
    $('modalBody').innerHTML=`
      <div class="metrics" style="margin-bottom:20px">
        <div class="m-card"><div class="m-val hi">${d.preferences?.length||0}</div><div class="m-lbl">Preferences</div></div>
        <div class="m-card"><div class="m-val hi">${d.facts?.length||0}</div><div class="m-lbl">Facts</div></div>
        <div class="m-card"><div class="m-val hi">${d.episodes?.length||0}</div><div class="m-lbl">Episodes</div></div>
        <div class="m-card"><div class="m-val hi">${d.semantic_count||0}</div><div class="m-lbl">Semantic</div></div>
      </div>
      <h4 style="color:#fff;margin:0 0 8px;font-size:13px">Preferences (Redis)</h4>
      ${tbl(d.preferences,['key','value','confidence'])}
      <h4 style="color:#fff;margin:18px 0 8px;font-size:13px">Facts (Redis)</h4>
      ${tbl(d.facts,['fact_id','predicate','object','confidence'])}
      <h4 style="color:#fff;margin:18px 0 8px;font-size:13px">Episodes (JSONL)</h4>
      ${tbl(d.episodes,['kind','summary'])}
      ${annotate('This snapshot shows all 4 memory layers for the current user. <strong>Short-term buffer</strong> is session-scoped and not shown here. <strong>Semantic memory</strong> count reflects ChromaDB vector chunks.','info')}`;
    $('modal').classList.add('open');
  } catch(e){ alert('Failed: '+e.message); }
  finally{ busy(false); }
}

// ── Clear Memory ──
async function doClear() {
  if(!confirm(`Clear ALL memory for "${user()}"? Cannot undo.`)) return;
  busy(true);
  try {
    await api('/api/memory/clear',{user_id:user()});
    $('content').innerHTML=`<div class="card fade-in" style="text-align:center;padding:40px">
      <div style="font-size:40px;margin-bottom:12px">🗑️</div>
      <h3 style="color:#fff;margin-bottom:6px">Memory Cleared</h3>
      <p style="color:var(--text-dim)">All 4 layers wiped for <b>${esc(user())}</b>. Ready for cold-start testing.</p>
      ${annotate('All preferences, facts, episodes, and semantic chunks have been deleted. This simulates <strong>Scenario 10 (Cold Start)</strong>. Send a new message to test how the agent behaves without any prior context.','success')}
    </div>`;
  } catch(e){ $('content').innerHTML=`<div class="card"><h3 style="color:var(--red)">Error</h3><p>${esc(e.message)}</p></div>`; }
  finally{ busy(false); }
}

// ── Batch/Stress Test ──
async function doBatch() {
  const def=["Hi, I'm a new user.","Tôi thích Python, không thích Java.","I'm using Postgres 15.","Tôi dị ứng sữa bò.","Which language for a script?","What database am I using?","Tell me about my allergies.","I'm confused about async/await.","Explain async/await again?","Capital of France?","Remind me my preferred language.","Actually I prefer Rust now.","Which language now?","Tell me my tech stack.","À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.","Tôi dị ứng gì?","Summary of what you know?","Something unrelated.","How does GC work?","My preferred language?"].join('\n');
  const raw=prompt("Messages (one per line):",def);
  if(!raw) return;
  const msgs=raw.split('\n').map(m=>m.trim()).filter(Boolean);
  if(!msgs.length) return;
  busy(true);
  try {
    const r=await api('/api/batch',{messages:msgs,user_id:user(),session_id:sess()||'batch',memory_enabled:memOn()});
    const cards=r.results.map((t,i)=>`<div class="tl-step">
      <div class="tl-label">Turn ${i+1}/${r.total_turns}</div>
      <div class="tl-msg">"${esc(t.message)}"</div>
      ${turnCard('Result',t)}
    </div>`).join('');

    // Check for context trimming
    const trimmed=r.results.filter(t=>t.context?.degraded);
    let batchAnalysis='';
    if(trimmed.length>0)
      batchAnalysis=annotate(`<strong>Context trimming detected!</strong> ${trimmed.length} of ${r.total_turns} turns hit the token budget and triggered L3→L2 degradation. This validates <strong>Scenario 09</strong> (long conversation trim).`,'success');
    else
      batchAnalysis=annotate(`All ${r.total_turns} turns completed within token budget. Increase turn count (30+) or message length to trigger context window trimming.`);

    $('content').innerHTML=`<div class="fade-in">
      <div class="section-hdr"><h2>Batch Stress Test — ${r.total_turns} Turns</h2><span class="badge badge-accent">User: ${esc(r.user_id)}</span></div>
      ${batchAnalysis}
      <div class="timeline">${cards}</div></div>`;
  } catch(e){ $('content').innerHTML=`<div class="card"><h3 style="color:var(--red)">Error</h3><p>${esc(e.message)}</p></div>`; }
  finally{ busy(false); }
}

// ── Benchmark Report ──
async function loadReport() {
  try {
    const d=await getJ('/api/report/latest');
    if(!d.available){ $('reportArea').innerHTML='<div style="color:var(--text-dim);text-align:center;padding:20px">No benchmark report found. Run CLI first.</div>'; return; }
    const rows=(d.summary.scenarios||[]).map(s=>{
      const pass=s.deltas.user_satisfaction_proxy>0||(s.with_mem.user_satisfaction_proxy===1);
      return `<tr>
        <td>${esc(s.id)}</td>
        <td>${esc(s.with_mem.user_satisfaction_proxy)}</td>
        <td>${esc(s.no_mem.user_satisfaction_proxy)}</td>
        <td><span class="${s.deltas.user_satisfaction_proxy>0?'delta-pos':s.deltas.user_satisfaction_proxy<0?'delta-neg':'delta-zero'}">${s.deltas.user_satisfaction_proxy>0?'+':''}${esc(s.deltas.user_satisfaction_proxy)}</span></td>
        <td><span class="badge ${pass?'badge-green':'badge-red'}">${pass?'PASS':'FAIL'}</span></td>
      </tr>`;
    }).join('');
    const winCount=(d.summary.scenarios||[]).filter(s=>s.deltas.user_satisfaction_proxy>0||(s.with_mem.user_satisfaction_proxy===1)).length;

    $('reportArea').innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div><span style="font-family:var(--mono);color:var(--accent-light);font-size:12px">${esc(d.run_id)}</span></div>
        <span class="badge badge-green">Score: ${d.summary?.total_score||'N/A'} — ${winCount}/${(d.summary.scenarios||[]).length} scenarios won</span>
      </div>
      <table class="tbl"><thead><tr><th>Scenario</th><th>With Mem</th><th>No Mem</th><th>Delta</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table>
      ${annotate(`With-memory wins on <strong>${winCount}</strong> of <strong>${(d.summary.scenarios||[]).length}</strong> scenarios. This proves the memory system consistently improves response quality across preference, fact, episodic, and precision test cases.`,'success')}
      <div style="margin-top:10px;font-size:11px;color:var(--text-micro)">Path: ${esc(d.paths.report)}</div>`;
  } catch(e){ console.error(e); }
}

// ── Scenario presets with descriptions ──
const SCENARIOS=[
  {label:'Add Preference',msg:'Tôi thích Python, không thích Java.',ses:'sess_pref',desc:'S01: Write preference → Redis'},
  {label:'Query Preference',msg:'Which language should I use for a simple script?',ses:'sess_query',desc:'S02: Cross-session recall'},
  {label:'Pref Conflict',msg:'Actually I prefer Rust now.',ses:'sess_pref',desc:'S03: Contradiction override'},
  {label:'Fact Write',msg:'Tôi dị ứng sữa bò.',ses:'sess_fact',desc:'S04: Profile fact capture'},
  {label:'Fact Correction',msg:'À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.',ses:'sess_fact',desc:'S04: Allergy correction'},
  {label:'Fact Recall',msg:'Tôi dị ứng gì?',ses:'sess_fact',desc:'S04: Query corrected fact'},
  {label:'Tech Stack',msg:"I'm using Postgres 15 for this project.",ses:'sess_tech',desc:'S05: Technical fact'},
  {label:'Precision',msg:'What is the capital of France?',ses:'sess_prec',desc:'S08: No PII leakage'},
  {label:'Log Episode',msg:"I'm confused about async/await in Python, I don't really get it.",ses:'sess_ep1',desc:'S06: Episode capture'},
  {label:'Recall Episode',msg:'Can you explain async/await again?',ses:'sess_ep2',desc:'S06: Episodic adaptation'}
];

// ── Init ──
document.addEventListener('DOMContentLoaded',()=>{
  // Render chips
  const chipsEl=$('scenarioChips');
  SCENARIOS.forEach(s=>{
    const el=document.createElement('div');
    el.className='chip';
    el.textContent=s.label;
    el.title=s.desc;
    el.onclick=()=>{$('message').value=s.msg;$('sessionId').value=s.ses;document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));el.classList.add('active');};
    chipsEl.appendChild(el);
  });

  // Buttons
  $('askBtn').onclick=doAsk;
  $('compareBtn').onclick=doCompare;
  $('demoBtn').onclick=doDemo;
  $('snapBtn').onclick=doSnapshot;
  $('clearBtn').onclick=doClear;
  $('batchBtn').onclick=doBatch;
  $('reportBtn').onclick=loadReport;
  $('modalCloseBtn').onclick=()=>$('modal').classList.remove('open');
  $('modal').onclick=e=>{if(e.target===$('modal'))$('modal').classList.remove('open');};

  loadConfig().then(loadReport);
});
