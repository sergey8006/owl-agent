// OWL Agent — Phase 1+2 JavaScript
// ReAct, RAG, Tasks, Scheduler, Webhooks, Secrets

// ===== Feature Toggles =====
const FEATURES = {
  react: true,
  rag: true,
  tasks: true,
  scheduler: true,
  webhooks: true,
  secrets: true,
  teams: true,
  flow: true
};

// Load saved preferences
try {
  const saved = localStorage.getItem('owl_features');
  if (saved) {
    Object.assign(FEATURES, JSON.parse(saved));
    // Update checkboxes
    for (const [key, val] of Object.entries(FEATURES)) {
      const cb = document.getElementById('feat_' + key);
      if (cb) cb.checked = val;
    }
  }
} catch(e) {}

function toggleFeature(name, enabled) {
  FEATURES[name] = enabled;
  localStorage.setItem('owl_features', JSON.stringify(FEATURES));
}

// Get enabled features count
function getEnabledFeatures() {
  return Object.entries(FEATURES).filter(([k,v]) => v).map(([k]) => k);
}

// ===== ReAct =====
function showReActPanel(){document.getElementById('reactModal').classList.add('show')}
async function runReAct(){
  const task=document.getElementById('reactTask').value.trim();
  const maxSteps=parseInt(document.getElementById('reactMaxSteps').value)||10;
  if(!task)return;
  const log=document.getElementById('reactLog');
  const status=document.getElementById('reactStatus');
  log.style.display='block';
  log.textContent='Running...\n';
  status.textContent='Executing ReAct loop...';
  try{
    const resp=await fetch('/api/react/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,max_steps:maxSteps})});
    const data=await resp.json();
    log.textContent=data.log?data.log.join('\n'):JSON.stringify(data,null,2);
    status.textContent='Status: '+data.status;
  }catch(e){status.textContent='Error: '+e.message}
}

// ===== Task Queue =====
function showTaskQueue(){document.getElementById('taskQueueModal').classList.add('show');loadTasks()}
async function loadTasks(){
  try{
    const resp=await fetch('/api/tasks/list');
    const data=await resp.json();
    const list=document.getElementById('taskList');
    if(!data.tasks||data.tasks.length===0){list.innerHTML='<div style="padding:8px;color:#484f58">No tasks</div>';return}
    list.innerHTML=data.tasks.map(t=>{
      const c=t.status==='completed'?'var(--green)':t.status==='failed'?'var(--red)':t.status==='in_progress'?'var(--yellow)':'#8b949e';
      return '<div style="padding:6px 8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center"><div><span style="color:'+c+'">['+t.status+']</span> <span style="color:#8b949e">p'+t.priority+'</span> '+t.description+'</div><div style="display:flex;gap:4px">'+(t.status==='pending'?'<button class="btn-green btn-sm" onclick="completeTask(\''+t.id+'\')">✓</button><button class="btn-red btn-sm" onclick="failTask(\''+t.id+'\')">✗</button>':'')+'</div></div>';
    }).join('');
    document.getElementById('sidebarTasks').textContent=data.tasks.filter(t=>t.status==='pending').length+' pending';
  }catch(e){}
}
async function createTask(){
  const desc=document.getElementById('newTaskDesc').value.trim();
  const priority=parseInt(document.getElementById('newTaskPriority').value)||5;
  if(!desc)return;
  await fetch('/api/tasks/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({description:desc,priority})});
  document.getElementById('newTaskDesc').value='';loadTasks();
}
async function completeTask(id){
  await fetch('/api/tasks/'+id+'/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result:'completed'})});loadTasks();
}
async function failTask(id){
  await fetch('/api/tasks/'+id+'/fail',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({error:'failed'})});loadTasks();
}
async function generateTasks(){
  const obj=document.getElementById('generateObjective').value.trim();
  if(!obj)return;
  await fetch('/api/tasks/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({objective:obj,max_tasks:5})});
  document.getElementById('generateObjective').value='';loadTasks();
}

// ===== RAG =====
function showRAGPanel(){document.getElementById('ragModal').classList.add('show');loadRAGDocs()}
async function ragIndexFile(){
  const path=document.getElementById('ragFilePath').value.trim();
  if(!path)return;
  const resp=await fetch('/api/rag/index-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
  const data=await resp.json();
  document.getElementById('ragStatus').textContent=data.error||'Indexed: '+data.chunks+' chunks';
  document.getElementById('ragFilePath').value='';loadRAGDocs();
}
async function ragIndexDir(){
  const path=document.getElementById('ragDirPath').value.trim();
  if(!path)return;
  const resp=await fetch('/api/rag/index-dir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})});
  const data=await resp.json();
  document.getElementById('ragStatus').textContent='Loaded: '+data.loaded+' files';
  document.getElementById('ragDirPath').value='';loadRAGDocs();
}
async function ragSearch(){
  const query=document.getElementById('ragQuery').value.trim();
  if(!query)return;
  const resp=await fetch('/api/rag/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,top_k:5})});
  const data=await resp.json();
  const r=document.getElementById('ragResults');r.style.display='block';
  r.textContent=data.results&&data.results.length?data.results.map(x=>'['+x.source+'] (score: '+x.score.toFixed(3)+')\n'+x.content.substring(0,300)).join('\n---\n'):'No results found.';
}
async function ragAsk(){
  const q=document.getElementById('ragQuery').value.trim();
  if(!q)return;
  const r=document.getElementById('ragResults');r.style.display='block';r.textContent='Thinking...';
  const resp=await fetch('/api/rag/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
  const data=await resp.json();
  r.textContent=data.answer+'\n\nSources: '+(data.sources||[]).map(s=>s.source).join(', ');
}
async function loadRAGDocs(){
  try{
    const resp=await fetch('/api/rag/documents');
    const data=await resp.json();
    const list=document.getElementById('ragDocList');
    if(!data.documents||data.documents.length===0){list.innerHTML='<div style="padding:4px;color:#484f58">No documents</div>'}
    else{list.innerHTML=data.documents.map(d=>'<div style="padding:4px 8px;display:flex;justify-content:space-between"><span>'+d.title+' ('+d.chunk_count+' chunks)</span><button class="btn-red btn-sm" onclick="ragDeleteDoc(\''+d.id+'\')">✗</button></div>').join('')}
    document.getElementById('sidebarRAG').textContent=data.documents.length+' docs';
  }catch(e){}
}
async function ragDeleteDoc(id){await fetch('/api/rag/document/'+id,{method:'DELETE'});loadRAGDocs()}

// ===== Scheduler =====
function showSchedulerPanel(){document.getElementById('schedulerModal').classList.add('show');loadSchedulerJobs()}
async function loadSchedulerJobs(){
  try{
    const resp=await fetch('/api/scheduler/list');
    const data=await resp.json();
    const list=document.getElementById('schedulerList');
    if(!data.jobs||data.jobs.length===0){list.innerHTML='<div style="padding:8px;color:#484f58">No jobs</div>'}
    else{list.innerHTML=data.jobs.map(j=>'<div style="padding:6px 8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center"><div><span style="color:'+(j.enabled?'var(--green)':'#8b949e')+'">'+(j.enabled?'ON':'OFF')+'</span> '+j.name+' <span style="color:#484f58">('+j.type+')</span></div><div style="display:flex;gap:4px"><button class="btn-secondary btn-sm" onclick="toggleJob(\''+j.id+'\')">'+(j.enabled?'⏸':'▶')+'</button><button class="btn-green btn-sm" onclick="runJobNow(\''+j.id+'\')">Run</button><button class="btn-red btn-sm" onclick="removeJob(\''+j.id+'\')">✗</button></div></div>').join('')}
    document.getElementById('sidebarScheduler').textContent=data.jobs.length+' jobs';
  }catch(e){}
}
async function addSchedulerJob(){
  const name=document.getElementById('schedName').value.trim();
  const type=document.getElementById('schedType').value;
  const cmd=document.getElementById('schedCommand').value.trim();
  if(!name)return;
  const body={name,type,command:cmd};
  if(type==='interval')body.interval_seconds=parseInt(document.getElementById('schedInterval').value)||3600;
  await fetch('/api/scheduler/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  document.getElementById('schedName').value='';document.getElementById('schedCommand').value='';loadSchedulerJobs();
}
async function toggleJob(id){await fetch('/api/scheduler/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});loadSchedulerJobs()}
async function runJobNow(id){await fetch('/api/scheduler/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})}
async function removeJob(id){await fetch('/api/scheduler/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});loadSchedulerJobs()}

// ===== Webhooks =====
function showWebhookPanel(){document.getElementById('webhookModal').classList.add('show');loadWebhooks()}
async function loadWebhooks(){
  try{
    const resp=await fetch('/api/webhook/list');
    const data=await resp.json();
    const list=document.getElementById('webhookList');
    if(!data.webhooks||data.webhooks.length===0){list.innerHTML='<div style="padding:8px;color:#484f58">No webhooks</div>'}
    else{list.innerHTML=data.webhooks.map(w=>'<div style="padding:6px 8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center"><div><span style="color:var(--accent)">'+w.name+'</span> <span style="color:#484f58">('+w.calls+' calls)</span></div><div style="display:flex;gap:4px"><button class="btn-red btn-sm" onclick="deleteWebhook(\''+w.id+'\')">✗</button></div></div>').join('')}
    document.getElementById('sidebarWebhooks').textContent=data.webhooks.length+' hooks';
  }catch(e){}
}
async function registerWebhook(){
  const name=document.getElementById('whName').value.trim();
  const flow_id=document.getElementById('whFlowId').value.trim();
  const cmd=document.getElementById('whCommand').value.trim();
  if(!name)return;
  const resp=await fetch('/api/webhook/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,flow_id,command:cmd})});
  const data=await resp.json();
  if(data.url)alert('URL: '+window.location.origin+data.url+'?token='+data.token);
  document.getElementById('whName').value='';document.getElementById('whFlowId').value='';document.getElementById('whCommand').value='';loadWebhooks();
}
async function deleteWebhook(id){await fetch('/api/webhook/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});loadWebhooks()}

// ===== Secrets =====
function showSecretsPanel(){document.getElementById('secretsModal').classList.add('show');loadSecrets()}
async function loadSecrets(){
  try{
    const resp=await fetch('/api/secrets/list');
    const data=await resp.json();
    const list=document.getElementById('secretsList');
    if(!data.keys||data.keys.length===0){list.innerHTML='<div style="padding:8px;color:#484f58">No secrets</div>'}
    else{list.innerHTML=data.keys.map(k=>'<div style="padding:6px 8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center"><span style="font-family:monospace">'+k+'</span><div style="display:flex;gap:4px"><button class="btn-secondary btn-sm" onclick="getSecret(\''+k+'\')">Show</button><button class="btn-red btn-sm" onclick="deleteSecret(\''+k+'\')">✗</button></div></div>').join('')}
    document.getElementById('sidebarSecrets').textContent=data.keys.length+' keys';
  }catch(e){}
}
async function setSecret(){
  const key=document.getElementById('secretKey').value.trim();
  const val=document.getElementById('secretValue').value;
  if(!key)return;
  await fetch('/api/secrets/set',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,value:val})});
  document.getElementById('secretKey').value='';document.getElementById('secretValue').value='';loadSecrets();
}
async function getSecret(key){const r=await fetch('/api/secrets/get?key='+encodeURIComponent(key));const d=await r.json();alert(key+' = '+(d.value||'(empty)'))}
async function deleteSecret(key){await fetch('/api/secrets/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});loadSecrets()}

// Update sidebar counts on load
document.addEventListener('DOMContentLoaded',function(){setTimeout(function(){loadTasks();loadRAGDocs();loadSchedulerJobs();loadWebhooks();loadSecrets()},1000)});

// ===== Context Optimization =====
// Build minimal system prompt based on enabled features
function buildSystemPrompt() {
  const base = 'Ты — OWL, локальный AI-агент. Отвечай на русском.\n\nПРАВИЛА:\n1. ДЕЙСТВУЙ, а не объясняй. Если просят что-то сделать — делай сразу через инструменты.\n2. Никогда не давай инструкции вместо действий.\n3. Не пиши код для обучения моделей — ты inference-only агент.\n4. Не выдумывай библиотеки, модели, бенчмарки.\n5. Проверяй результат после действий.\n6. Используй инструменты в первую очередь.';
  
  let tools = 'run_command, read_file, write_file, edit_file, list_dir, execute_code, calculator, web_search, learn_fact, get_memory_stats, use_skill, system_info';
  
  if (FEATURES.react) tools += ', react_solve';
  if (FEATURES.rag) tools += ', rag_search, rag_ask, rag_index_file, rag_list_docs';
  if (FEATURES.tasks) tools += ', task_create, task_list';
  if (FEATURES.flow) tools += ', flow_create, flow_run';
  if (FEATURES.teams) tools += ' (Agent Teams через API)';
  
  return base + '\n\nДоступные инструменты: ' + tools + '\n\nВключенные фичи: ' + getEnabledFeatures().join(', ');
}

// Override saveSettings to use minimal prompt
const _origSaveSettings = window.saveSettings;
window.saveSettings = function() {
  // Update system prompt based on features
  const prompt = buildSystemPrompt();
  const cfgSystem = document.getElementById('cfgSystem');
  if (cfgSystem && !cfgSystem.value.includes('Включенные фичи')) {
    cfgSystem.value = prompt;
  }
  if (_origSaveSettings) _origSaveSettings();
};
