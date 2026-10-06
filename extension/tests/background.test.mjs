import test from 'node:test';
import assert from 'node:assert/strict';
import 'fake-indexeddb/auto';

function event(){return {addListener(fn){this.listener=fn;}};}
const data={}, notifications=[], opened=[], cleared=[], sentForms=[];
const local={
  async get(keys){ if(keys===null)return structuredClone(data);const result={};for(const k of typeof keys==='string'?[keys]:keys)if(k in data)result[k]=structuredClone(data[k]);return result; },
  async set(values){Object.assign(data,structuredClone(values));},
  async remove(keys){for(const k of Array.isArray(keys)?keys:[keys])delete data[k];},
  async clear(){for(const k of Object.keys(data))delete data[k];},
  async setAccessLevel(){}
};
globalThis.chrome={storage:{local},runtime:{id:'test',getURL:path=>'chrome-extension://test/'+path,onMessage:event(),onInstalled:event(),onStartup:event()},
  alarms:{async get(){return true;},async create(){},onAlarm:event()},sidePanel:{async setPanelBehavior(){},async open(){}},
  action:{async setBadgeBackgroundColor(){},async setBadgeText(){},onClicked:event()},contextMenus:{async removeAll(){},create(){},onClicked:event()},
  notifications:{async getPermissionLevel(){return 'granted';},async create(id,body){notifications.push({id,body});},async getAll(){return {};},async clear(id){cleared.push(id);},onClicked:event()},
  permissions:{async contains(){return true;}},tabs:{async create(options){opened.push(options);}}
};
let currentResponse, requests=0;
// `{httpStatus, body}` simulates an error response; anything else is a 200 body.
globalThis.fetch=async(url,options={})=>{requests++;if(options.body instanceof FormData)sentForms.push(options.body);if(currentResponse instanceof Error)throw currentResponse;
  if(currentResponse?.httpStatus)return {ok:false,status:currentResponse.httpStatus,async json(){return structuredClone(currentResponse.body);}};
  return {ok:true,status:200,async json(){return structuredClone(currentResponse);}};};
await import('../src/background.js');
const send=(type,extra={})=>new Promise((resolve,reject)=>chrome.runtime.onMessage.listener({type,...extra},{id:'test',url:'chrome-extension://test/index.html'},reply=>reply.error?reject(Error(reply.error)):resolve(reply.data)));
function reset(){for(const k of Object.keys(data))delete data[k];notifications.length=0;cleared.length=0;sentForms.length=0;requests=0;data.settings={enabled:true,notifications:true};}
function claim(extra={}){return {id:'one',owner:'guest',type:'SOURCE_BASED',headline:'A claim',created:1,status:'PENDING',next:0,...extra};}

test('notifications deduplicate across polling, then notify expert finalization',async()=>{
  reset();data['claim:one']=claim();currentResponse={status:'EXPERT_REVIEW',result:{source_status:'CONFIRMED'}};
  await send('poll',{force:true});await send('poll',{force:true});
  assert.equal(notifications.length,1);assert.equal(data['claim:one'].unread,true);
  await send('read',{id:'one'});assert.equal(data['claim:one'].unread,false);
  currentResponse={status:'FINALIZED',result:{source_status:'CONFIRMED',overall_verdict:'REAL'}};
  await send('poll',{force:true});await send('poll',{force:true});assert.equal(notifications.length,2);
  assert.equal(data['claim:one'].notified,'final:REAL');
});
test('OFF blocks polling and submissions; re-enable recovers persisted claims',async()=>{
  reset();data.settings.enabled=false;data['claim:one']=claim();currentResponse={status:'EXPERT_REVIEW',result:{source_status:'NOT_FOUND'}};
  await send('poll',{force:true});assert.equal(requests,0);
  await assert.rejects(send('submit',{draft:{},owner:'guest'}),/Turn on/);
  data.settings.enabled=true;await send('poll',{force:true});assert.equal(notifications.length,1);
});
test('account isolation, failed network backoff, and unauthorized detail access',async()=>{
  reset();data.auth={user:{id:'alice'},access_token:'token'};data['claim:one']=claim({owner:'bob'});currentResponse={status:'FINALIZED'};
  await send('poll',{force:true});assert.equal(requests,0);assert.equal((await send('state')).items.length,0);
  await assert.rejects(send('details',{id:'one'}),/account/);
  data['claim:one'].owner='alice';currentResponse=Error('offline');await send('poll',{force:true});
  assert.equal(data['claim:one'].status,'PENDING');assert.equal(data['claim:one'].failures,1);assert.equal(notifications.length,0);
});
test('terminal result saved before a restart is notified without a network request',async()=>{
  reset();data['claim:one']=claim({status:'FINALIZED',summary:{stage:'final:REAL',final:true},next:Date.now()+600000});
  await send('poll');assert.equal(requests,0);assert.equal(notifications.length,1);
});

test('a submission deleted on the server disappears from Activity, with its alert and badge',async()=>{
  for(const status of ['PENDING','EXPERT_REVIEW','FINALIZED','FAILED']){
    reset();data['claim:one']=claim({status,unread:true,summary:{stage:'preliminary',lines:['Headline: Exact Matched']},notified:'preliminary'});
    currentResponse={httpStatus:404,body:{detail:{error:'not_found',submission_id:'one'}}};
    await send('poll',{force:true});
    assert.equal(requests,1,status);assert.equal(data['claim:one'],undefined,status);
    assert.deepEqual(cleared,['bfg:one']);assert.equal((await send('state')).items.length,0);
  }
});

test('finished results are re-checked later, so a later deletion is noticed',async()=>{
  reset();data['claim:one']=claim({status:'FINALIZED',summary:{stage:'final:REAL',final:true},notified:'final:REAL',next:0});
  currentResponse={status:'FINALIZED',result:{source_status:'CONFIRMED',overall_verdict:'REAL'}};
  await send('poll');assert.equal(requests,1);
  assert.ok(data['claim:one'].next>Date.now()+5*60000);  // finished: re-checked rarely, not never
  await send('poll');assert.equal(requests,1);
  currentResponse={httpStatus:404,body:{detail:{error:'not_found',submission_id:'one'}}};
  await send('poll',{force:true});assert.equal(data['claim:one'],undefined);
});

test('a generic 404 (wrong API address) or an outage never deletes saved results',async()=>{
  for(const response of [{httpStatus:404,body:{detail:'Not Found'}},{httpStatus:404,body:{detail:{error:'not_found',submission_id:'other'}}},{httpStatus:503,body:{}},Error('offline')]){
    reset();data['claim:one']=claim({status:'EXPERT_REVIEW',summary:{stage:'preliminary',lines:['Headline: Altered']}});
    currentResponse=response;await send('poll',{force:true});
    assert.ok(data['claim:one']);assert.deepEqual(data['claim:one'].summary.lines,['Headline: Altered']);assert.equal(data['claim:one'].failures,1);
  }
});

test('a photo card is submitted as the image only, whatever an old draft holds',async()=>{
  reset();
  const {imageStore}=await import('../src/db.js');
  await imageStore('guest',{current:new Blob(['png-bytes'],{type:'image/png'}),name:'card.png'});
  currentResponse={submission_id:'new-card',status:'PENDING'};
  await send('submit',{owner:'guest',draft:{type:'PHOTO_CARD',headline:'',body_text:'',claimed_source_text:'Prothom Alo',published_date:'2026-01-01'}});
  assert.equal(sentForms.length,1);assert.deepEqual([...sentForms[0].keys()],['image']);
  assert.equal(data['claim:new-card'].type,'PHOTO_CARD');
  await send('poll'); // let the poll started by submit finish before the next test
});
test('content scripts cannot invoke privileged extension messages',()=>{
  let called=false;
  const result=chrome.runtime.onMessage.listener({type:'state'},{id:'test',url:'https://example.com'},()=>{called=true;});
  assert.equal(result,undefined);assert.equal(called,false);
});

test('failed desktop notification retains an unread saved result and retries later',async()=>{
  reset();data['claim:one']=claim();currentResponse={status:'FINALIZED',result:{source_status:'CONFIRMED',overall_verdict:'REAL'}};
  const create=chrome.notifications.create;
  chrome.notifications.create=async()=>{throw Error('Notification service unavailable');};
  try {await send('poll',{force:true});}finally{chrome.notifications.create=create;}
  assert.equal(data['claim:one'].status,'FINALIZED');assert.equal(data['claim:one'].unread,true);assert.ok(data['claim:one'].notificationError);
  await send('poll',{force:true});assert.equal(notifications.length,1);assert.equal(data['claim:one'].notificationError,null);
});

test('a Facebook tab with hidden URL metadata is not rejected as restricted',async()=>{
  reset();let target, query;
  chrome.tabs.query=async options=>{query=options;return [{id:42,windowId:7}];};
  chrome.scripting={async executeScript(options){target=options.target;return [{result:null}];}};
  assert.deepEqual(await send('capture',{windowId:7}),{cancelled:true});
  assert.deepEqual(target,{tabId:42});assert.deepEqual(query,{active:true,windowId:7});
});

test('missing page permission explains the toolbar gesture rather than blaming Facebook',async()=>{
  reset();chrome.tabs.query=async()=>[{id:42,windowId:7}];
  chrome.scripting={async executeScript(){throw Error('Cannot access contents of the page. Extension manifest must request permission.');}};
  await assert.rejects(send('capture',{windowId:7}),/click the pinned BanglaFactGuard icon/);
});

test('real Chrome internal pages still cannot start selection',async()=>{
  reset();chrome.tabs.query=async()=>[{id:42,windowId:7,url:'chrome://extensions/'}];
  let injected=false;chrome.scripting={async executeScript(){injected=true;}};
  await assert.rejects(send('capture',{windowId:7}),/Chrome or extension page/);
  assert.equal(injected,false);
});

test('toolbar action immediately opens the panel in the clicked window',()=>{
  let openedWindow;
  chrome.sidePanel.open=options=>{openedWindow=options;return Promise.resolve();};
  chrome.action.onClicked.listener({id:42,windowId:7,url:'https://www.facebook.com/'});
  assert.deepEqual(openedWindow,{windowId:7});
});

test('headline/body selection also works when Chrome omits tab URL',async()=>{
  reset();chrome.tabs.query=async()=>[{id:42,windowId:7}];
  chrome.scripting={async executeScript(){return [{result:'Selected Facebook text'}];}};
  assert.equal(await send('selection',{windowId:7}),'Selected Facebook text');
});

test('old finalized photocard Activity hides cached extracted-date warnings',async()=>{
  reset();data['claim:one']=claim({type:'PHOTO_CARD',status:'FINALIZED',summary:{warnings:['The card\'s own text suggests a date that does not clearly match the published date provided.','Headline OCR is uncertain']}});
  const state=await send('state');
  assert.deepEqual(state.items[0].summary.warnings,['Headline OCR is uncertain']);
  assert.equal(requests,0);
});

test('guests, registered users and experts cannot change either connection URL',async()=>{
  for(const role of [null,'user','expert'])for(const key of ['api','website']){
    reset();if(role)data.auth={user:{id:'person',role},access_token:'token'};
    await assert.rejects(send('settings',{settings:{[key]:'https://other.example'}}),/Only an administrator/);
    assert.equal(requests,0);assert.equal(data.settings[key],undefined);
  }
});

test('only a server-confirmed admin can save connection settings',async()=>{
  reset();data.auth={user:{id:'admin-1',role:'admin'},access_token:'token'};
  currentResponse={id:'admin-1',role:'expert'};
  await assert.rejects(send('settings',{settings:{website:'https://site.example'}}),/Only an administrator/);
  currentResponse={id:'admin-1',role:'admin'};
  await send('settings',{settings:{website:'https://site.example'}});
  assert.equal(data.settings.website,'https://site.example');
});

test('non-admins can still use ON/OFF and notification preferences',async()=>{
  reset();await send('settings',{settings:{enabled:false,notifications:false}});
  assert.equal(data.settings.enabled,false);assert.equal(data.settings.notifications,false);assert.equal(requests,0);
});

test('expired access refreshes; temporary refresh failure keeps credentials',async()=>{
  const savedFetch=globalThis.fetch;
  try {
    reset();data.auth={user:{id:'alice'},access_token:'old',refresh_token:'refresh'};
    data['claim:one']=claim({owner:'alice'});
    let failRefresh=true;
    globalThis.fetch=async(url,options)=> {
      if(url.endsWith('/auth/refresh')) return {ok:!failRefresh,status:failRefresh?503:200,json:async()=>({access_token:'new',refresh_token:'rotated'})};
      if(options.headers.Authorization==='Bearer old')return {ok:false,status:401,json:async()=>({})};
      return {ok:true,status:200,json:async()=>({status:'EXPERT_REVIEW',result:{source_status:'CONFIRMED'}})};
    };
    await send('poll',{force:true});
    assert.equal(data.auth.refresh_token,'refresh');assert.equal(notifications.length,0);
    failRefresh=false;await send('poll',{force:true});
    assert.equal(data.auth.refresh_token,'rotated');assert.equal(notifications.length,1);
  } finally {globalThis.fetch=savedFetch;}
});
