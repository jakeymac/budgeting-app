import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowUpRight, ArrowDownLeft, Plus, Wallet, SlidersHorizontal, ChevronRight, X, Pencil, Trash2, FlaskConical, Check, Search, Leaf, CalendarDays, LogOut} from 'lucide-react';
import './style.css';
import Planner from './Planner';

const cents = value => Math.round(Number(value || 0) * 100);
const currency = value => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(Number(value));
const dateLabel = value => new Date(value+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
const today = () => {const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const emptyEvent = () => ({description:'',amount:'',category:'Groceries',date:today(),note:''});
const categoryColors = ['#bc638b','#d78eaa','#9d6b91','#b485aa','#c597a5','#ad5479','#dfabc1','#9e8394'];

const csrfToken = () => document.cookie.split('; ').find(row=>row.startsWith('csrftoken='))?.split('=')[1] || '';
const toLogin = () => {location.href = `/login/?next=${encodeURIComponent(location.pathname)}`};
async function signOut(){
  await fetch('/logout/',{method:'POST',headers:{'X-CSRFToken':csrfToken()}}).catch(()=>{});
  location.href = '/login/';
}
async function request(path, method='GET', data) {
  const response = await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},...(data?{body:JSON.stringify(data)}:{})});
  // An expired session gets bounced to the login page, which is HTML, not JSON.
  if(response.redirected && new URL(response.url).pathname.startsWith('/login')){toLogin();throw new Error('Your session has expired. Taking you back to sign in…')}
  const result = await response.json().catch(()=>({error:'The server could not complete this request. Please try again.'}));
  if(!response.ok) throw new Error(result.error || 'Could not save. Please refresh and try again.');
  return result;
}
function Field({label,children,wide=false}) {return <label className={wide?'field wide':'field'}><span>{label}</span>{children}</label>}
function AmountInput(props) {return <div className="money-input"><span>$</span><input type="number" min="0" max="9999999999.99" step="0.01" required {...props}/></div>}
function App(){
 const [data,setData]=useState(null),[loadError,setLoadError]=useState(''),[page,setPage]=useState(location.pathname.startsWith('/workspace')?'workspace':'overview');
 const [modal,setModal]=useState(null),[notice,setNotice]=useState(''),[query,setQuery]=useState(''),[category,setCategory]=useState('All'),[periodOnly,setPeriodOnly]=useState(false);
 const [plannerDirty,setPlannerDirty]=useState(false);
 const load=()=>{setLoadError('');request('/api/budget/').then(d=>{setData(d);}).catch(e=>setLoadError(e.message));};
 useEffect(load,[]);
 useEffect(()=>{const fn=()=>setPage(location.pathname.startsWith('/workspace')?'workspace':'overview');window.addEventListener('popstate',fn);return()=>window.removeEventListener('popstate',fn)},[]);
 useEffect(()=>{if(!notice)return;const id=setTimeout(()=>setNotice(''),5000);return()=>clearTimeout(id)},[notice]);
 const navigate=p=>{if(p===page)return;if(plannerDirty&&!window.confirm('Leave this page and discard unsaved budget edits?'))return;history.pushState({},'',p==='overview'?'/':'/workspace/');setPage(p);window.scrollTo(0,0)};
 const accept=(result,message)=>{setData(result);setNotice(message)};
 if(!data)return <main className="loading"><Leaf size={34}/><h1>Teresa’s budget</h1><p>{loadError||'Getting your budget ready…'}</p>{loadError&&<button className="primary" onClick={load}>Try again</button>}</main>;
 const {budget,events,categories}=data;
 const inPeriod=e=>e.date>=budget.start&&e.date<=budget.end;
 const currentEvents=events.filter(inPeriod);
 const spent=cents(data.spent),amount=cents(budget.amount),reserve=cents(budget.reserve),available=cents(data.available);
 const percent=amount>0?Math.min(100,Math.round(spent/amount*100)):0;
 const filtered=events.filter(e=>(!periodOnly||inPeriod(e))&&(category==='All'||e.category===category)&&`${e.description} ${e.note}`.toLowerCase().includes(query.toLowerCase()));
 const breakdown=categories.map((name,i)=>({name,color:categoryColors[i],total:currentEvents.filter(e=>e.category===name).reduce((s,e)=>s+cents(e.amount),0)})).filter(c=>c.total>0).sort((a,b)=>b.total-a.total);
 return <div className={page==='overview'?'overview-theme':undefined}><header className="topbar"><a href="/" className="brand" onClick={e=>{e.preventDefault();navigate('overview')}}><span className="brand-icon"><Leaf size={23}/></span><span>little by little<span className="brand-sub">TERESA’S BUDGET</span></span></a><nav aria-label="Main navigation"><a href="/" className={page==='overview'?'active':''} onClick={e=>{e.preventDefault();navigate('overview')}}><Wallet size={17}/>Overview</a><a href="/workspace/" className={page==='workspace'?'active':''} onClick={e=>{e.preventDefault();navigate('workspace')}}><SlidersHorizontal size={17}/>Budget workspace</a></nav><div className="account"><div className="avatar" aria-label={budget.owner}>{budget.owner.slice(0,1).toUpperCase()}</div><button type="button" className="signout" onClick={signOut}><LogOut size={15}/>Sign out</button></div></header>
 <main><div className="page-heading"><div><div className="eyebrow">A LITTLE CLARITY, EVERY DAY</div><h1>{page==='overview'?`Your money, ${budget.owner}.`:'Make room for your plans.'}</h1><p>{page==='overview'?'A clear view of what’s yours to spend.':'Your budget, every purchase, and a little space to experiment.'}</p></div><span className="period"><CalendarDays size={16}/>{dateLabel(budget.start)} — {dateLabel(budget.end)}</span></div>
 {notice&&<div className="toast" role="status"><Check size={18}/>{notice}</div>}
 {page==='overview'?<>
 <section className="overview-grid"><div className="balance-card"><div className="balance-top"><span className="eyebrow">AVAILABLE TO SPEND</span><span className="pill"><span/> {available<0?'Over budget':'Your current budget'}</span></div><div className="balance-number">{currency(available/100)}</div><p>{available<0?'Spending has gone beyond your available budget.':amount===0?'A fresh start. Add your income and monthly payments in the workspace.':'After required monthly payments, other purchases, and money set aside.'}</p><div className="balance-bottom"><div><span>After required payments</span><strong>{currency(amount/100)}</strong></div><div><span>Set aside</span><strong>{currency(reserve/100)}</strong></div><button onClick={()=>navigate('workspace')}>Manage budget <ArrowUpRight size={18}/></button></div></div>
 <div className="spend-card"><div className="section-icon"><ArrowUpRight size={22}/></div><span className="eyebrow">SPENT THIS PERIOD</span><strong>{currency(spent/100)}</strong><div className="progress"><span style={{width:percent+'%'}}/></div><p>{amount?`${Math.round(spent/amount*100)}% of your budget`:'No budget set yet'} <span>· {currentEvents.length} purchases</span></p><div className="quiet-note">Small moments. All accounted for.</div></div></section>
 <section className="content-grid"><div className="panel activity"><div className="panel-heading"><div><h2>The latest little things</h2><p>Your recent spending this period</p></div><button className="text-button" onClick={()=>navigate('workspace')}>View all <ChevronRight size={16}/></button></div><EventList events={currentEvents.slice(0,5)} onEdit={setModal}/></div><div className="panel quick-add"><div className="panel-heading"><div><h2>Add a little spending</h2><p>Other purchases, beyond your planned monthly bills.</p></div><Plus size={21}/></div><EventForm categories={categories} onSave={result=>accept(result,'Purchase added to your budget.')} compact/></div></section>
 <section className="panel categories"><div><div className="eyebrow">THE BIGGER PICTURE</div><h2>Where it’s going</h2><p>Spending by category for this budget period.</p></div><div className="category-bars">{breakdown.length?breakdown.map(c=><div key={c.name} className="category-row"><span><i style={{background:c.color}}/>{c.name}</span><div className="category-track"><div style={{width:c.total/spent*100+'%',background:c.color}}/></div><strong>{currency(c.total/100)}</strong></div>):<div className="empty-small">Your categories will come to life with your first purchase.</div>}</div></section>
 </>:<>
 <Planner data={data} request={request} onSave={accept} onDirty={setPlannerDirty}/>
 <section className="panel ledger"><div className="panel-heading"><div><h2>Every little thing</h2><p>Other purchases, across all dates. Don’t log the required monthly bills above again.</p></div><button className="primary" onClick={()=>setModal({})}><Plus size={17}/>Add spending</button></div><div className="filters"><div className="search"><Search size={17}/><input aria-label="Search spending" placeholder="Search purchases or notes" value={query} onChange={e=>setQuery(e.target.value)}/></div><select aria-label="Filter by category" value={category} onChange={e=>setCategory(e.target.value)}><option>All</option>{categories.map(c=><option key={c}>{c}</option>)}</select><label className="check-label"><input type="checkbox" checked={periodOnly} onChange={e=>setPeriodOnly(e.target.checked)}/>This period only</label></div><div className="ledger-meta">{filtered.length} events <span>{currency(filtered.reduce((s,e)=>s+cents(e.amount),0)/100)} total shown</span></div><EventList events={filtered} onEdit={setModal} full/></section>
 </>}
 <footer><span><Leaf size={15}/> A little intention goes a long way.</span><span>{budget.title} · USD</span></footer></main>
 {modal&&<EventModal event={modal} categories={categories} onClose={()=>setModal(null)} onSave={(result,message)=>{accept(result,message);setModal(null)}}/>}</div>;
}
function EventList({events,onEdit,full=false}){return events.length?<div className="event-list">{events.map(event=><div className="event" key={event.id}><span className="event-icon"><ArrowDownLeft size={19}/></span><div className="event-name"><strong>{event.description}</strong><span>{event.category} <b>·</b> {dateLabel(event.date)}</span>{full&&event.note&&<p>{event.note}</p>}</div><strong className="event-amount">−{currency(event.amount)}</strong><button className="icon-button" aria-label={`Edit ${event.description}`} onClick={()=>onEdit(event)}><Pencil size={16}/></button></div>)}</div>:<div className="empty"><span className="empty-icon"><Wallet size={25}/></span><h3>No purchases here yet</h3><p>Add your first spending event, or adjust your filters.</p></div>}
function EventForm({event,categories,onSave,compact=false}){
 const [form,setForm]=useState(event?.id?{...event}:emptyEvent()),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const update=(name,value)=>setForm({...form,[name]:value});
 const submit=async e=>{e.preventDefault();setBusy(true);setError('');try{const result=await request(event?.id?`/api/events/${event.id}/`:'/api/events/',event?.id?'PATCH':'POST',form);onSave(result,event?.id?'Spending event updated.':'Spending event added.');if(!event?.id)setForm(emptyEvent())}catch(e){setError(e.message)}finally{setBusy(false)}};
 const remove=async()=>{if(!window.confirm('Delete this spending event? This will restore its amount to your available budget if it is in the current period.'))return;setBusy(true);setError('');try{onSave(await request(`/api/events/${event.id}/`,'DELETE'),'Spending event deleted.')}catch(e){setError(e.message);setBusy(false)}};
 return <form onSubmit={submit} className="form-grid"><Field label="What was it for?" wide><input autoFocus={!!event} required maxLength="120" placeholder="e.g. The weekly grocery shop" value={form.description} onChange={e=>update('description',e.target.value)}/></Field><Field label="Amount"><AmountInput min="0.01" placeholder="0.00" value={form.amount} onChange={e=>update('amount',e.target.value)}/></Field><Field label="Category"><select value={form.category} onChange={e=>update('category',e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field><Field label="Date" wide={compact}><input required type="date" value={form.date} onChange={e=>update('date',e.target.value)}/></Field>{!compact&&<Field label="Note (optional)" wide><textarea rows="2" maxLength="1000" value={form.note} onChange={e=>update('note',e.target.value)} placeholder="Anything you'd like to remember"/></Field>}{error&&<p className="error wide" role="alert">{error}</p>}<button className="primary wide" disabled={busy}>{busy?'Saving…':event?.id?'Save changes':'Add spending'}<Plus size={17}/></button>{event?.id&&<button type="button" className="delete-button wide" disabled={busy} onClick={remove}><Trash2 size={15}/>Delete spending event</button>}</form>
}
function EventModal({event,categories,onClose,onSave}){
 useEffect(()=>{const prev=document.activeElement;const close=e=>{if(e.key==='Escape')onClose()};document.addEventListener('keydown',close);document.body.style.overflow='hidden';return()=>{document.removeEventListener('keydown',close);document.body.style.overflow='';prev?.focus()}},[]);
 const trap=e=>{if(e.key!=='Tab')return;const elements=e.currentTarget.querySelectorAll('button:not(:disabled),input,select,textarea');const first=elements[0],last=elements[elements.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}};
 return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)onClose()}}><section className="modal panel" role="dialog" aria-modal="true" aria-labelledby="modal-title" onKeyDown={trap}><div className="panel-heading"><h2 id="modal-title">{event.id?'Edit spending':'Add spending'}</h2><button className="icon-button" aria-label="Close" onClick={onClose}><X size={21}/></button></div><EventForm event={event} categories={categories} onSave={onSave}/></section></div>
}
createRoot(document.getElementById('root')).render(<App/>);
