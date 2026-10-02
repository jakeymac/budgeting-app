import React, {useEffect, useState} from 'react';
import {Plus, Trash2, FlaskConical, Check, CreditCard, HeartPulse, Banknote, ReceiptText, RotateCcw} from 'lucide-react';
import {calculatePlan} from './planning';

const clone = value => JSON.parse(JSON.stringify(value));
const money = cents => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format((cents || 0) / 100);
const labelMonth = value => new Date(value+'-15T12:00:00').toLocaleDateString('en-US',{month:'long',year:'numeric'});
function Money({label, value, onChange}) {
 return <div className="money-input"><span>$</span><input aria-label={label} type="number" required min="0" max="9999999999.99" step="0.01" value={value} onChange={e=>onChange(e.target.value)}/></div>;
}
function MonthField({label, title, value, onChange}) {
 const [year, month] = value.split('-');
 return <div className="field"><span>{title}</span><div className="month-picker"><select aria-label={`${label} month`} value={month || '01'} onChange={e=>onChange(`${year}-${e.target.value}`)}>{Array.from({length:12},(_,i)=><option key={i} value={String(i+1).padStart(2,'0')}>{new Date(2026,i,1).toLocaleDateString('en-US',{month:'long'})}</option>)}</select><input aria-label={`${label} year`} required type="number" min="1" max="9999" step="1" value={year} onChange={e=>onChange(`${e.target.value ? e.target.value.padStart(4,'0') : ''}-${month || '01'}`)}/></div></div>;
}
function EditableTable({title, subtitle, icon:Icon, rows, columns, onChange, singular}) {
 const add = () => onChange([...rows, Object.fromEntries([['name',''], ...columns.map(c=>[c.key,'0.00'])])]);
 const update = (index,key,value) => onChange(rows.map((row,i)=>i===index?{...row,[key]:value}:row));
 return <section className="panel planning-table"><div className="panel-heading"><div><h2><Icon size={20}/>{title}</h2><p>{subtitle}</p></div><button type="button" className="text-button" disabled={rows.length>=100} onClick={add}><Plus size={16}/>Add {singular}</button></div>
 <div className="table-scroll"><table><caption className="sr-only">{title}: editable monthly budget data</caption><thead><tr><th scope="col">Name</th>{columns.map(c=><th key={c.key} scope="col">{c.label}</th>)}<th scope="col"><span className="sr-only">Remove</span></th></tr></thead><tbody>{rows.map((row,i)=><tr key={i}><td><input required maxLength="120" aria-label={`${singular} ${i+1} name`} placeholder={singular==='income'?'e.g. Take-home salary':singular==='card'?'e.g. Visa':'e.g. Car insurance'} value={row.name} onChange={e=>update(i,'name',e.target.value)}/></td>{columns.map(c=><td key={c.key}><Money label={`${singular} ${i+1} ${c.label}`} value={row[c.key]} onChange={value=>update(i,c.key,value)}/></td>)}<td><button type="button" className="icon-button" aria-label={`Remove ${singular} ${i+1}`} onClick={()=>onChange(rows.filter((_,n)=>n!==i))}><Trash2 size={16}/></button></td></tr>)}</tbody></table></div>
 {!rows.length&&<div className="table-empty">No {title.toLowerCase()} yet. Add your own numbers to get started.</div>}
 </section>;
}
export default function Planner({data, request, onSave, onDirty}) {
 const [slot,setSlot]=useState('actual');
 const [drafts,setDrafts]=useState(()=>Object.fromEntries(Object.entries(data.plans).map(([kind,p])=>[kind,clone(p.data)])));
 const [bases,setBases]=useState(()=>clone(data.plans));
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const dirty = kind => JSON.stringify(drafts[kind])!==JSON.stringify(bases[kind].data);
 const anyDirty=dirty('actual')||dirty('theoretical');
 useEffect(()=>{onDirty(anyDirty);return()=>onDirty(false)},[anyDirty]);
 useEffect(()=>{const warn=e=>{if(anyDirty){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[anyDirty]);
 const plan=drafts[slot], theory=slot==='theoretical';
 const change=(key,value)=>setDrafts(prev=>({...prev,[slot]:{...prev[slot],[key]:value}}));
 const insurance=(key,value)=>change('insurance',{...plan.insurance,[key]:value});
 let preview=null, baseline=null, previewError='';
 try {preview=calculatePlan(plan,data.events);baseline=calculatePlan({...data.plans.actual.data,month:plan.month},data.events)}catch(e){previewError=e.message}
 const save=async e=>{e.preventDefault();if(!preview)return;setBusy(true);setError('');try{
   const result=await request(`/api/plans/${slot}/`,'PUT',{revision:bases[slot].revision,data:plan});
   setBases(prev=>({...prev,[slot]:clone(result.plans[slot])}));
   setDrafts(prev=>({...prev,[slot]:clone(result.plans[slot].data)}));
   onSave(result,`${theory?'Theoretical':'Actual'} budget saved.`);
 }catch(e){setError(e.message)}finally{setBusy(false)}};
 const reload=async()=>{if(dirty(slot)&&!window.confirm('Discard your unsaved edits in this budget and reload its saved values?'))return;setBusy(true);setError('');try{const result=await request('/api/budget/');setBases(prev=>({...prev,[slot]:clone(result.plans[slot])}));setDrafts(prev=>({...prev,[slot]:clone(result.plans[slot].data)}));onSave(result,'Saved values reloaded.')}catch(e){setError(e.message)}finally{setBusy(false)}};
 const copyActual=()=>{if(!window.confirm('Replace your theoretical draft with the saved actual numbers? The actual budget will not change.'))return;setDrafts(prev=>({...prev,theoretical:{...clone(data.plans.actual.data),extra_spending:'0.00'}}));setError('')};
 const rows=preview?[
  ['Monthly income',preview.income],['Credit-card minimums',-preview.minimums],['Monthly expenses',-preview.expenses],['Work insurance',-preview.insurance],['Money set aside',-preview.reserve],['Other spending this month',-preview.spending],...(theory?[['Hypothetical extra spending',-preview.extra]]:[])]:[];
 return <section className={`planner ${theory?'is-theoretical':''}`}>
 <div className="plan-toolbar"><div className="plan-tabs" role="group" aria-label="Budget version"><button type="button" disabled={busy} aria-pressed={!theory} className={!theory?'selected':''} onClick={()=>{setSlot('actual');setError('')}}><Banknote size={16}/>Actual {dirty('actual')&&<span className="dirty-dot" aria-label="Unsaved changes"/>}</button><button type="button" disabled={busy} aria-pressed={theory} className={theory?'selected':''} onClick={()=>{setSlot('theoretical');setError('')}}><FlaskConical size={16}/>Theoretical {dirty('theoretical')&&<span className="dirty-dot" aria-label="Unsaved changes"/>}</button></div><span className="plan-status">{dirty(slot)?'Unsaved changes · preview below':'Saved budget'}</span></div>
 <div className="plan-explainer"><strong>{theory?'A safe place to try something different.':'Your actual monthly plan.'}</strong><p>{theory?'Change income, card payments, bills, or insurance. Saving updates only this one theoretical budget.':'Add monthly take-home income and required payments. Saving updates the money available on your overview.'}</p></div>
 <form onSubmit={save}>
 <fieldset disabled={busy} className="plan-fieldset">
 <div className="plan-controls"><MonthField label="Budget" title="Budget month" value={plan.month} onChange={value=>change('month',value)}/><label className="field"><span>Money set aside</span><Money label="Money set aside" value={plan.reserve} onChange={value=>change('reserve',value)}/></label>{theory&&<label className="field"><span>Hypothetical extra spending</span><Money label="Hypothetical extra spending" value={plan.extra_spending} onChange={value=>change('extra_spending',value)}/></label>}</div>
 <div className="plan-layout"><div className="plan-tables">
 <EditableTable title="Income" singular="income" subtitle="Monthly take-home amounts, before the work-insurance deduction below." icon={Banknote} rows={plan.incomes} columns={[{key:'amount',label:'Monthly income'}]} onChange={rows=>change('incomes',rows)}/>
 <section className="panel insurance-panel"><div className="panel-heading"><div><h2><HeartPulse size={20}/>Work insurance</h2><p>Kept separate so you can easily test your future contribution.</p></div></div><div className="form-grid"><label className="field"><span>Full monthly premium</span><Money label="Full monthly insurance premium" value={plan.insurance.premium} onChange={value=>insurance('premium',value)}/></label><label className="field"><span>Your contribution (%)</span><input required type="number" min="0" max="100" step="0.01" value={plan.insurance.percentage} onChange={e=>insurance('percentage',e.target.value)}/></label><MonthField label="Contribution starts" title="Contribution starts" value={plan.insurance.start_month} onChange={value=>insurance('start_month',value)}/><div className="insurance-result"><span>Your monthly share</span><strong>{preview?money(preview.contribution):'—'}</strong><small>{preview?(plan.month>=plan.insurance.start_month?'Included this month':`Starts ${labelMonth(plan.insurance.start_month)}`):'Check the inputs'}</small></div></div><p className="form-help">Full premium × your percentage. Before the start month, the deduction is $0. Don’t also list this deduction under monthly expenses.</p></section>
 <EditableTable title="Credit cards" singular="card" subtitle="Only monthly minimums reduce your budget. Balances are amounts still owed." icon={CreditCard} rows={plan.cards} columns={[{key:'minimum',label:'Monthly minimum'},{key:'balance',label:'Outstanding balance'}]} onChange={rows=>change('cards',rows)}/>
 <EditableTable title="Monthly expenses" singular="expense" subtitle="Car payments, insurance, rent, and other recurring monthly bills." icon={ReceiptText} rows={plan.expenses} columns={[{key:'amount',label:'Monthly amount'}]} onChange={rows=>change('expenses',rows)}/>
 </div><aside className="plan-summary panel" aria-label="Budget calculation"><div className="eyebrow">{theory?'THEORETICAL':'ACTUAL'} · {plan.month||'SELECT MONTH'}</div><h2>What’s left to spend</h2><div className={`summary-available ${preview?.available<0?'negative':''}`} aria-live="polite">{preview?money(preview.available):'—'}</div>{previewError&&<p className="error" role="alert">{previewError}</p>}<dl>{rows.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{money(value)}</dd></div>)}</dl>{preview&&<><div className="summary-total"><span>Required monthly payments</span><strong>{money(preview.required)}</strong></div><div className="summary-debt"><span>Total card balance</span><strong>{money(preview.debt)}</strong></div>{theory&&<div className="comparison"><span>Compared with saved actual<br/>for {labelMonth(plan.month)}</span><strong className={preview.available-baseline.available<0?'negative':''}>{preview.available>=baseline.available?'+':''}{money(preview.available-baseline.available)}</strong><small>Saved actual would leave {money(baseline.available)}. Both include the same recorded spending for this month.</small></div>}</>}<p className="form-help">These are monthly amounts, with no proration. Actual purchases come from your spending log; theoretical edits never change that log.</p></aside></div>
 <div className="plan-savebar"><div><button className="primary" disabled={!dirty(slot)||!preview||busy}><Check size={17}/>{busy?'Saving…':`Save ${theory?'theoretical':'actual'} budget`}</button><button type="button" className="text-button" onClick={reload}><RotateCcw size={15}/>Reload saved</button>{theory&&<button type="button" className="text-button" onClick={copyActual}>Copy saved actual</button>}</div><span>{theory?'Your actual numbers stay unchanged.':'Changes become live when you save.'}</span></div>{error&&<p className="error" role="alert">{error}</p>}
 </fieldset></form></section>;
}
