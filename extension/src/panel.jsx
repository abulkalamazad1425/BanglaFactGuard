import { resultLine } from './shared.js';
import { h, render, Fragment } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import { DEFAULTS, EMPTY_DRAFT, ownerOf, terminal, cropRect, validateDraft } from './shared.js';
import { imageStore } from './db.js';
import './style.css';

async function call(type, payload = {}) {
  if (type === 'capture' || type === 'selection') {
    // Bind capture to the panel's window, even if another Chrome window gains focus.
    const currentWindow = await chrome.windows.getCurrent();
    payload = { ...payload, windowId: currentWindow.id };
  }
  const response = await chrome.runtime.sendMessage({ type, ...payload });
  if (!response) throw Error('Extension worker unavailable. Reload the extension.');
  if (response.error) throw Error(response.error);
  return response.data;
}
function CropPreview({ image, setImage, owner, disabled }) {
  const [url, setUrl] = useState(''), [rect, setRect] = useState(null), [working, setWorking] = useState(false);
  const surface = useRef(), start = useRef();
  useEffect(() => {
    if (!image) return;
    const next = URL.createObjectURL(image.current); setUrl(next); setRect(null);
    return () => URL.revokeObjectURL(next);
  }, [image]);
  if (!image) return null;
  const point = e => { const b = surface.current.getBoundingClientRect(); return { x: Math.max(0,Math.min(b.width,e.clientX-b.left)), y: Math.max(0,Math.min(b.height,e.clientY-b.top)) }; };
  const save = async next => { await imageStore(owner, next); setImage(next); setRect(null); };
  const crop = async () => {
    setWorking(true);
    try {
      const bitmap = await createImageBitmap(image.current), b = surface.current.getBoundingClientRect();
      const r = cropRect(rect, b, bitmap), canvas = document.createElement('canvas');
      canvas.width = r.width; canvas.height = r.height;
      canvas.getContext('2d').drawImage(bitmap,r.x,r.y,r.width,r.height,0,0,r.width,r.height); bitmap.close();
      const blob = await new Promise(resolve => canvas.toBlob(resolve,'image/png'));
      await save({ ...image, current: blob, name: 'cropped.png' });
    } finally { setWorking(false); }
  };
  return <div class="preview"><div class="crop-surface" ref={surface}
    onPointerDown={e => { if (disabled || working) return; e.preventDefault(); start.current=point(e); e.currentTarget.setPointerCapture(e.pointerId); setRect(null); }}
    onPointerMove={e => { if (!start.current) return; const p=point(e), s=start.current; setRect({x:Math.min(p.x,s.x),y:Math.min(p.y,s.y),width:Math.abs(p.x-s.x),height:Math.abs(p.y-s.y)}); }}
    onPointerUp={() => { start.current=null; }} onPointerCancel={() => { start.current=null; setRect(null); }}>
    <img src={url} alt="Selected claim image preview" draggable={false}/>
    {rect && <span class="crop-box" style={{left:rect.x,top:rect.y,width:rect.width,height:rect.height}}/>}
    </div><p class="hint">Drag on the preview to crop further. Only the preview image will be submitted.</p>
    <div class="row"><button type="button" disabled={disabled || working || !rect || rect.width<4 || rect.height<4} onClick={crop}>Apply crop</button>
    <button type="button" disabled={disabled || working} onClick={() => save({...image,current:image.original,name:image.originalName || image.name})}>Reset crop</button>
    <button type="button" disabled={disabled || working} onClick={() => save(null)}>Remove</button></div></div>;
}
function App() {
  const [state,setState]=useState({settings:DEFAULTS,items:[]}), [tab,setTab]=useState(location.hash === '#activity' ? 'activity':'verify');
  const [draft,setDraft]=useState(EMPTY_DRAFT), [image,setImage]=useState(null), [loaded,setLoaded]=useState(false);
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('');
  const [selection,setSelection]=useState(null), [sources,setSources]=useState([]);
  const [addresses,setAddresses]=useState(DEFAULTS), [credentials,setCredentials]=useState({email:'',password:''});
  const owner=ownerOf({user:state.user}), enabled=state.settings.enabled, locked=busy || state.busy || !enabled;
  const ownerRef=useRef(owner), draftRef=useRef(draft);
  ownerRef.current=owner; draftRef.current=draft;
  const refresh=async () => { const next=await call('state'); setState(next); return next; };
  const run=async fn => { setBusy(true);setError('');setNotice('');try { return await fn(); } catch(e) {setError(e.message);} finally {setBusy(false);} };
  useEffect(() => {
    refresh().then(next=>setAddresses(next.settings)).catch(e=>setError(e.message));
    const listener=changes => {
      if (Object.keys(changes).some(k=>k.startsWith('claim:') || ['settings','auth'].includes(k))) void refresh().catch(()=>{});
      if (changes.selection?.newValue?.owner === ownerRef.current) {setSelection(changes.selection.newValue);setTab('verify');}
    };
    chrome.storage.onChanged.addListener(listener);
    const timer=setInterval(()=>{ if(document.visibilityState==='visible') void call('poll').catch(()=>{}); },10000);
    return ()=>{chrome.storage.onChanged.removeListener(listener);clearInterval(timer);};
  },[]);
  useEffect(() => {
    let alive=true; setLoaded(false);setImage(null);setSelection(null);
    Promise.all([chrome.storage.local.get([`draft:${owner}`,'selection',`sending:${owner}`]),imageStore(owner)]).then(([saved,img])=>{
      if(!alive)return;
      setDraft(saved[`draft:${owner}`] || {...EMPTY_DRAFT});setImage(img || null);setLoaded(true);
      if(saved.selection?.owner===owner)setSelection(saved.selection);
      if(saved[`sending:${owner}`])setNotice('A previous submission attempt may have reached the server. Check Activity or website history before resubmitting.');
    }).catch(e=>setError(e.message));
    return ()=>{alive=false;};
  },[owner,state.settings.api]);
  useEffect(()=>{if(enabled)call('sources').then(s=>setSources(s.items || [])).catch(()=>{});},[enabled,state.settings.api]);
  const change=(field,value)=>{
    const next={...draftRef.current,[field]:value};draftRef.current=next;setDraft(next);
    void chrome.storage.local.set({[`draft:${ownerRef.current}`]:next}).catch(e=>setError(e.message));
  };
  const importSelection=async field=>run(async()=>{setSelection({field,text:await call('selection')});});
  const applySelection=async append=>{
    const field=selection.field, max=field==='headline'?2000:50000;
    const value=append && draft[field] ? draft[field]+'\n'+selection.text:selection.text;
    if(value.length>max){setError(`Selected text exceeds the ${max.toLocaleString()} character limit. Paste a shorter excerpt.`);return;}
    change(field,value);setSelection(null);await chrome.storage.local.remove('selection');
  };
  const upload=event=>run(async()=>{
    const file=event.target.files[0];event.target.value='';if(!file)return;
    if(!['image/png','image/jpeg','image/gif','image/webp'].includes(file.type)||!file.size||file.size>10*1024*1024)throw Error('Choose a PNG, JPEG, WebP or GIF image up to 10 MB.');
    const bitmap=await createImageBitmap(file);bitmap.close();
    const value={original:file,current:file,name:file.name,originalName:file.name};await imageStore(owner,value);setImage(value);
  });
  const submit=e=>{e.preventDefault();void run(async()=>{
    validateDraft(draft,image?.current);await call('submit',{draft,owner});
    setDraft({...EMPTY_DRAFT,type:draft.type});setImage(null);setTab('activity');
    setNotice('Claim received. Verification may take a few minutes. You can continue browsing; results will appear in Activity.');await refresh();
  });};
  const saveSettings=e=>{e.preventDefault();void run(async()=>{
    if(state.user?.role!=='admin')throw Error('Only an administrator can change connection settings.');
    const url=new URL(addresses.api);
    if(url.protocol==='https:') {
      const granted=await chrome.permissions.request({origins:[url.origin+'/*']});
      if(!granted)throw Error('Host access was not granted. Your settings were not changed.');
    }
    await call('settings',{settings:{api:addresses.api,website:addresses.website}});await refresh();setNotice('Connection settings saved.');
  });};
  const textField=(field,label,required,minLength)=> <label class="field">{label}<span class="row field-tools"><small>{required?'Required':'Optional'} · {draft[field].length.toLocaleString()} characters</small><button type="button" class="link-button" disabled={locked} onClick={()=>importSelection(field)}>Use selected text</button></span><textarea rows={field==='headline'?3:5} value={draft[field]} onInput={e=>change(field,e.currentTarget.value)} required={required} minLength={minLength} maxLength={field==='headline'?2000:50000} placeholder={`Type, paste, or select ${field==='headline'?'a headline':'body text'} on the page`} /></label>;
  return <main><header><div class="brand"><span class="shield">✓</span><div><strong>BanglaFactGuard</strong><small>Quick Verify</small></div></div><label class="toggle"><input type="checkbox" checked={enabled} disabled={busy || state.busy} onChange={e=>{const value=e.currentTarget.checked;void run(async()=>{await call('settings',{settings:{enabled:value}});await refresh();});}}/><span>{enabled?'ON':'OFF'}</span></label></header>
    <div class="identity">{state.user ? <span>{state.user.full_name || state.user.email} <b class="pill">{state.user.role}</b></span>:<span>Browsing as a guest <button class="link-button" onClick={()=>setTab('account')}>Sign in</button></span>}</div>
    <nav aria-label="Extension navigation">{[['verify','Verify'],['activity',`Activity${state.items.some(x=>x.unread)?' •':''}`],['account','Account']].map(([key,label])=><button class={tab===key?'active':''} onClick={()=>setTab(key)}>{label}</button>)}</nav>
    {!enabled && <div class="banner">Extension is off. Capture, submissions and notifications are paused. Accepted server jobs continue; turn on to catch up.</div>}
    {error && <div role="alert" class="banner error">{error}</div>}{notice && <div role="status" class="banner">{notice}</div>}
    {tab==='verify' && <section><h1>Check before you share.</h1><p class="intro">Submit a claim from the page you are reading.</p>
      {selection && <div class="banner"><strong>Selected {selection.field==='headline'?'headline':'body text'}</strong><p class="selection-text">{selection.text}</p><div class="row"><button disabled={locked} onClick={()=>applySelection(false)}>Replace field</button><button disabled={locked} onClick={()=>applySelection(true)}>Append to field</button><button onClick={()=>{setSelection(null);void chrome.storage.local.remove('selection');}}>Dismiss</button></div>{draft.type==='PHOTO_CARD'&&<small>Switch to Text & source or Text & image to use this text.</small>}</div>}
      <form onSubmit={submit}><fieldset disabled={locked || !loaded}><div class="modes">{[['SOURCE_BASED','Text & source'],['PHOTO_CARD','Photo card'],['MULTIMODAL','Text & image']].map(([key,label])=><button type="button" class={draft.type===key?'chosen':''} onClick={()=>change('type',key)}>{label}</button>)}</div>
        <p class="hint">{draft.type==='SOURCE_BASED'?'Check whether a claimed publisher carried this story.':draft.type==='PHOTO_CARD'?'Upload a news card or select a screenshot area to verify its claim.':'Analyze article body text and an image together. AI results are preliminary.'}</p>
        {draft.type!=='PHOTO_CARD' && <>{textField('headline','Headline',true,draft.type==='SOURCE_BASED'?5:1)}{textField('body_text','Body text',draft.type==='MULTIMODAL',draft.type==='MULTIMODAL'?10:undefined)}</>}
        {draft.type!=='SOURCE_BASED' && <div class="field">Claim image<div class="upload-actions"><label class="upload-button">Upload image<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={upload}/></label><button type="button" onClick={()=>run(async()=>{setNotice('Drag a rectangle on the page. Press Esc to cancel.');const result=await call('capture');if(result.captured){setImage(await imageStore(owner));setNotice('Selected area captured. Review or crop below.');}else setNotice('Screenshot cancelled.');})}>Select screenshot area</button></div><small>PNG, JPEG, WebP or GIF · maximum 10 MB</small><small>On a new website, click the pinned BanglaFactGuard toolbar icon once before capturing.</small><CropPreview image={image} setImage={setImage} owner={owner} disabled={locked}/></div>}
        {draft.type!=='MULTIMODAL' && <><label class="field">Claimed news source<input value={draft.claimed_source_text} onInput={e=>change('claimed_source_text',e.currentTarget.value)} list="sources" required maxLength={255} placeholder="Publisher name or domain"/><datalist id="sources">{sources.map(s=><option value={s.canonical_name}>{s.display_name}</option>)}</datalist><small>The publisher named in the claim, not necessarily this website.</small></label><label class="field">Claimed publication date <small>Optional</small><input type="date" value={draft.published_date} onInput={e=>change('published_date',e.currentTarget.value)}/></label></>}
        <button class="primary submit" type="submit">{busy||state.busy?'Please wait…':'Submit for verification'}</button><p class="hint">After submission, you can continue browsing. Find your results in Activity.</p>
      </fieldset></form></section>}
    {tab==='activity' && <section><div class="row between"><h1>Your activity</h1><button disabled={locked} onClick={()=>run(async()=>{await call('poll',{force:true});await refresh();})}>Refresh</button></div><p class="intro">Submissions made with this extension, for this account.</p>
      {!state.items.length && <div class="empty"><span>◎</span><h2>No claims yet</h2><p>Your pending checks and results will appear here.</p><button onClick={()=>setTab('verify')}>Verify a claim</button></div>}
      {state.items.map(item=><article class={`result ${item.unread?'unread':''}`} key={item.id}><div class="row between"><span class="eyebrow">{item.type.replaceAll('_',' ')}</span>{item.unread&&<span class="pill">New</span>}</div><h2>{item.headline}</h2><p class="status">{{PENDING:'Queued',PROCESSING:'Checking your claim',EXPERT_REVIEW:'Preliminary result ready',FINALIZED:'Final result ready',ESCALATED:'Additional review required',FAILED:'Verification could not finish'}[item.status]}</p>
        {item.summary?.lines?.map(line=><p class={"result-line " + (/verdict|prediction/i.test(line) ? "verdict-emphasis" : "finding-emphasis")}>{resultLine(line)}</p>)}{item.summary?.stage&&item.status!=='FAILED'&&<p class="review">{item.summary.review}</p>}
        {item.summary?.warnings?.map(w=><p class="warning">{w}</p>)}{item.summary?.error&&<p class="warning">{item.summary.error}</p>}{item.error&&<p class="warning">{item.error}</p>}{item.notificationError&&<p class="warning">{item.notificationError}</p>}
        {!terminal(item.status)&&!item.summary?.stage&&<p class="hint">{item.summary?.phase || 'Waiting for the server'}{Date.now()-item.created>120000?' · Taking a little longer than usual.':''}</p>}
        <small>{new Date(item.created).toLocaleString()}</small><div class="row actions"><button onClick={()=>run(()=>call('details',{id:item.id}))}>View details ↗</button>{item.unread&&<button onClick={()=>run(async()=>{await call('read',{id:item.id});await refresh();})}>Mark read</button>}</div></article>)}
      {!state.user&&<p class="hint">Guest history stays in this Chrome profile. Uninstalling or clearing extension data removes it.</p>}</section>}
    {tab==='account' && <section><h1>{state.user?'Your account':'Welcome back'}</h1><p class="intro">{state.user?'Your role is managed by BanglaFactGuard.':'Sign in as a registered user, expert or admin, or continue as a guest.'}</p>
      {state.user?<div class="card"><strong>{state.user.email}</strong><p>{state.user.role}</p><div class="row"><button disabled={busy||state.busy} onClick={()=>run(async()=>{await call('logout');await refresh();})}>Sign out</button>{['admin','expert'].includes(state.user.role)&&<a href={state.settings.website+'/'+state.user.role} target="_blank" rel="noreferrer">Open workspace ↗</a>}</div></div>:<form onSubmit={e=>{e.preventDefault();void run(async()=>{await call('login',{credentials});setCredentials({email:'',password:''});await refresh();setNotice('Signed in successfully.');});}}><fieldset disabled={locked}><label class="field">Email<input type="email" autoComplete="username" required value={credentials.email} onInput={e=>setCredentials({...credentials,email:e.currentTarget.value})}/></label><label class="field">Password<input type="password" autoComplete="current-password" required value={credentials.password} onInput={e=>setCredentials({...credentials,password:e.currentTarget.value})}/></label><button class="primary" type="submit">Sign in</button></fieldset></form>}
      <div class="card"><h2>Notifications</h2><label class="check"><input type="checkbox" checked={state.settings.notifications} disabled={busy||state.busy} onChange={e=>{const value=e.currentTarget.checked;void run(async()=>{await call('settings',{settings:{notifications:value}});await refresh();});}}/>Notify when my results are ready</label><p class="hint">Chrome permission: {state.notificationPermission || 'checking'}. Your operating system may also silence notifications. Activity and the badge retain unread results.</p></div>
      {state.user?.role==='admin' && <details><summary>Connection settings</summary><p class="hint">Changing the API signs you out and clears extension tracking. Server records remain available on the original website.</p><form onSubmit={saveSettings}><label class="field">API base URL<input type="url" value={addresses.api} required onInput={e=>setAddresses({...addresses,api:e.currentTarget.value})}/></label><label class="field">Website URL<input type="url" value={addresses.website} required onInput={e=>setAddresses({...addresses,website:e.currentTarget.value})}/></label><button disabled={busy||state.busy} type="submit">Save connection</button></form></details>}
      <p class="hint">Passwords are never stored. Sign-in tokens are kept locally in this extension until you sign out. Website and extension sessions are separate.</p></section>}
    <footer>Evidence first. Share responsibly.</footer>
  </main>;
}
render(<App/>,document.getElementById('app'));
