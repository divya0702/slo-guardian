import { useMemo, useState } from 'react'
import type { Analysis, Candidate, Metrics, Simulation } from './types'

const scenarios = [
  ['healthy','Healthy baseline'],['slow_dependency','Slow recommendations'],['retry_storm','Retry storm'],
  ['recommendation_timeout','Recommendation timeout'],['recommendation_saturation','Recommendation saturation'],
  ['inventory_timeout','Inventory timeout'],['pricing_errors','Pricing errors'],['gateway_saturation','Gateway saturation'],
  ['checkout_pool_exhaustion','Pool exhaustion'],['correlated_latency','Correlated latency'],
  ['unsafe_policy','Unsafe policy'],['hallucinated_evidence','Hallucinated evidence']
]

async function json<T>(url:string, init?:RequestInit):Promise<T>{
  const response=await fetch(url,{...init,headers:{'Content-Type':'application/json',...(init?.headers||{})}})
  if(!response.ok) throw new Error((await response.json()).detail||`Request failed (${response.status})`)
  return response.json()
}

function Graph({analysis}:{analysis:Analysis}){
  const positions:Record<string,[number,number]>={gateway:[80,130],checkout:[300,130],inventory:[540,35],pricing:[540,130],recommendations:[540,225]}
  return <svg className="graph" viewBox="0 0 700 280" role="img" aria-label="Service graph">
    {analysis.packet.service_graph.edges.map(edge=>{const [x1,y1]=positions[edge.source], [x2,y2]=positions[edge.target];return <g key={`${edge.source}-${edge.target}`}><line x1={x1+62} y1={y1} x2={x2-62} y2={y2} className={edge.traffic_class}/><text x={(x1+x2)/2} y={(y1+y2)/2-8}>{edge.traffic_class}{edge.retry_amplification>1?` · ${edge.retry_amplification}×`:''}</text></g>})}
    {analysis.packet.service_graph.nodes.map(node=>{const [x,y]=positions[node.id];return <g key={node.id} transform={`translate(${x-62} ${y-31})`}><rect width="124" height="62" rx="14" className={`node ${node.status}`}/><text x="62" y="26" textAnchor="middle" className="node-label">{node.label}</text><text x="62" y="46" textAnchor="middle" className="node-stat">p99 {node.p99_ms} ms</text></g>})}
  </svg>
}

function MetricTable({baseline,comparison,label}:{baseline:Metrics;comparison:Metrics;label:string}){
  const rows:[string,string,string][]=[
    ['Checkout p99',`${baseline.checkout_p99_ms} ms`,`${comparison.checkout_p99_ms} ms`],
    ['Critical success',`${(baseline.critical_success_rate*100).toFixed(1)}%`,`${(comparison.critical_success_rate*100).toFixed(1)}%`],
    ['Critical rejected',String(baseline.critical_rejected),String(comparison.critical_rejected)],
    ['Optional degraded',`${baseline.optional_degradation_percent}%`,`${comparison.optional_degradation_percent}%`],
    ['Retry amplification',`${baseline.retry_amplification}×`,`${comparison.retry_amplification}×`]
  ]
  return <table><thead><tr><th>Metric</th><th>Current</th><th>{label}</th></tr></thead><tbody>{rows.map(r=><tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>)}</tbody></table>
}

export default function App(){
  const [scenario,setScenario]=useState('slow_dependency'), [analysis,setAnalysis]=useState<Analysis|null>(null)
  const [selected,setSelected]=useState<string|null>(null), [simulation,setSimulation]=useState<Simulation|null>(null)
  const [busy,setBusy]=useState(''), [error,setError]=useState(''), [active,setActive]=useState<string|null>(null)
  const candidate:Candidate|undefined=analysis?.candidates.find(c=>c.policy_id===selected)
  const evidenceMap=useMemo(()=>new Map(analysis?.packet.evidence.map(e=>[e.id,e])||[]),[analysis])
  async function runAnalysis(){setBusy('Analyzing traces');setError('');setSimulation(null);setActive(null);try{const data=await json<Analysis>('/api/v1/analyses',{method:'POST',body:JSON.stringify({scenario_id:scenario,source:'fixture',use_live_model:false})});setAnalysis(data);setSelected(data.candidates.find(c=>c.state==='validated')?.policy_id||data.candidates[0]?.policy_id||null)}catch(e){setError(String(e))}finally{setBusy('')}}
  async function simulate(mode:'counterfactual'|'live'){if(!selected)return;setBusy(mode==='live'?'Running bounded live replay':'Running counterfactual replay');setError('');try{const data=await json<Simulation>('/api/v1/simulations',{method:'POST',body:JSON.stringify({policy_id:selected,scenario_id:scenario,mode,request_count:40,concurrency:5})});setSimulation(data);if(analysis)setAnalysis({...analysis,candidates:analysis.candidates.map(c=>c.policy_id===selected?{...c,state:'simulated'}:c)})}catch(e){setError(String(e))}finally{setBusy('')}}
  async function approve(){if(!selected)return;setBusy('Activating canonical policy');setError('');try{await json(`/api/v1/policies/${selected}/approve`,{method:'POST'});setActive(selected)}catch(e){setError(String(e))}finally{setBusy('')}}
  async function deactivate(){if(!active)return;setBusy('Rolling back policy');try{await json(`/api/v1/policies/${active}/deactivate`,{method:'POST'});setActive(null)}catch(e){setError(String(e))}finally{setBusy('')}}
  return <main><header><div><span className="eyebrow">TRACE-AWARE CONTROL PLANE</span><h1>SLO <i>Guardian</i></h1></div><div className="controls"><select value={scenario} onChange={e=>setScenario(e.target.value)}>{scenarios.map(s=><option value={s[0]} key={s[0]}>{s[1]}</option>)}</select><button onClick={runAnalysis} disabled={!!busy}>Analyze incident</button></div></header>
    {busy&&<div className="notice pulse">{busy}…</div>}{error&&<div className="notice error">{error}</div>}
    {!analysis?<section className="hero"><div className="radar">◎</div><h2>Detect pressure before it cascades.</h2><p>Select a deterministic incident scenario to build its trace graph, SLO evidence, and safe intervention set.</p><button onClick={runAnalysis}>Run demo scenario</button></section>:
    <div className="grid">
      <section className="panel graph-panel"><div className="panel-title"><span>01</span><div><h2>Service graph</h2><p>{analysis.packet.scenario_id.replaceAll('_',' ')}</p></div></div><Graph analysis={analysis}/><div className="legend"><span className="dot healthy"/>Healthy <span className="dot warning"/>Warning <span className="dot breached"/>Breached <span className="line optional"/>Optional edge</div></section>
      <section className="panel evidence"><div className="panel-title"><span>02</span><div><h2>Incident evidence</h2><p>{analysis.packet.evidence.length} deterministic signals</p></div></div><div className="evidence-list">{analysis.packet.evidence.map(e=><article key={e.id} id={e.id}><code>{e.id}</code><strong>{e.service}</strong><p>{e.summary}</p></article>)}</div></section>
      <section className="panel recommendation"><div className="panel-title"><span>03</span><div><h2>GPT‑5.6 recommendation</h2><p>Structured, cited, untrusted</p></div><b className="confidence">{Math.round(analysis.recommendation.confidence*100)}%</b></div><h3>{analysis.recommendation.suspected_root_cause}</h3><p>{analysis.recommendation.summary}</p><div className="chips">{analysis.recommendation.evidence_ids.map(id=><a href={`#${id}`} key={id}>{id}</a>)}</div><div className="candidates">{analysis.candidates.map(c=><button key={c.policy_id} className={`${selected===c.policy_id?'selected':''} ${c.state==='rejected'?'rejected':''}`} onClick={()=>{setSelected(c.policy_id);setSimulation(null)}}><span>{c.proposal.action.type.replaceAll('_',' ')}</span><strong>{c.proposal.title}</strong><small>{c.state}{c.rejection_reasons[0]?` · ${c.rejection_reasons[0]}`:''}</small></button>)}</div>{candidate&&<div className="policy-detail"><code>{JSON.stringify(candidate.proposal.action)}</code><p>{candidate.proposal.expected_effect}</p><p>Evidence: {candidate.proposal.evidence_ids.map(id=>evidenceMap.get(id)?.summary||id).join(' · ')}</p></div>}</section>
      <section className="panel simulation"><div className="panel-title"><span>04</span><div><h2>Policy simulation</h2><p>Prediction, replay, approval</p></div></div><div className="actions"><button onClick={()=>simulate('counterfactual')} disabled={!candidate||candidate.state==='rejected'||!!busy}>Counterfactual</button><button className="secondary" onClick={()=>simulate('live')} disabled={!candidate||candidate.state==='rejected'||!!busy}>Live replay</button></div>{simulation?<><div className={`safety ${simulation.safe?'safe':'unsafe'}`}>{simulation.safe?'✓ Critical checkout protected':'✕ Safety invariant failed'}</div><MetricTable baseline={simulation.baseline} comparison={simulation.observed||simulation.projected} label={simulation.observed?'Observed':'Predicted'}/><div className="actions"><button onClick={approve} disabled={!!active||!!busy}>Approve & activate</button>{active&&<button className="danger" onClick={deactivate}>Deactivate</button>}</div>{active&&<p className="active">Policy {active} is active with automatic TTL rollback.</p>}</>:<div className="empty">Select a valid candidate and run simulation.</div>}</section>
    </div>}</main>
}

