import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { build } from 'esbuild';
import { Window } from 'happy-dom';
import 'fake-indexeddb/auto';
import { render } from 'preact';

test('English side panel supports independent headline/body selection, persistence, submit and account roles',async()=>{
  const window=new Window({url:'https://extension.test/index.html'});
  Object.assign(globalThis,{window,document:window.document,location:window.location});
  document.body.innerHTML='<div id="app"></div>';
  const store={},listeners=new Set(),messages=[];
  let user, selected='Selected headline', submitted;
  const settings={enabled:true,notifications:true,api:'http://localhost:8000/api/v1',website:'http://localhost:4200'};
  const local={
    async get(keys){const result={};for(const key of typeof keys==='string'?[keys]:keys)if(key in store)result[key]=store[key];return result;},
    async set(values){Object.assign(store,values);},async remove(keys){for(const key of Array.isArray(keys)?keys:[keys])delete store[key];}
  };
  globalThis.chrome={windows:{async getCurrent(){return {id:7};}},storage:{local,onChanged:{addListener(fn){listeners.add(fn);},removeListener(fn){listeners.delete(fn);}}},runtime:{async sendMessage(message){
    messages.push(message);
    switch(message.type){
      case 'state': return {data:{settings,user,items:[],notificationPermission:'granted'}};
      case 'sources': return {data:{items:[{canonical_name:'prothomalo.com',display_name:'Prothom Alo'}]}};
      case 'selection': return {data:selected};
      case 'submit': submitted=message.draft;return {data:{id:'accepted'}};
      case 'login': user={id:'expert-1',email:'expert@example.com',role:'expert'};return {data:true};
      default:return {data:true};
    }
  }}};
  await mkdir('test-results',{recursive:true});
  await build({entryPoints:['src/panel.jsx'],outfile:'test-results/panel-under-test.mjs',bundle:true,format:'esm',jsxFactory:'h',jsxFragment:'Fragment',loader:{'.css':'empty'},external:['preact','preact/hooks']});
  const tick=()=>new Promise(r=>setTimeout(r,60));
  const button=text=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()===text);
  const input=(el,value)=>{el.value=value;el.dispatchEvent(new window.Event('input',{bubbles:true}));};
  try {
    await import(pathToFileURL(resolve('test-results/panel-under-test.mjs')).href);
    await tick();await tick();
    assert.match(document.body.textContent,/Check before you share/);
    assert.equal(document.querySelectorAll('textarea').length,2);
    const selectionButtons=Array.from(document.querySelectorAll('button')).filter(b=>b.textContent==='Use selected text');
    assert.equal(selectionButtons.length,2);
    selectionButtons[0].click();await tick();button('Replace field').click();await tick();
    assert.equal(document.querySelectorAll('textarea')[0].value,'Selected headline');
    selected='বাংলা body selected from page';selectionButtons[1].click();await tick();button('Append to field').click();await tick();
    assert.equal(document.querySelectorAll('textarea')[1].value,selected);
    assert.equal(store['draft:guest'].body_text,selected);
    input(document.querySelector('input[list="sources"]'),'prothomalo.com');await tick();
    document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await tick();
    assert.equal(submitted.headline,'Selected headline');assert.equal(submitted.body_text,selected);
    assert.match(document.body.textContent,/Claim received/);
    button('Verify').click();await tick();button('Photo card').click();await tick();
    assert.ok(button('Select screenshot area'));assert.equal(document.querySelectorAll('textarea').length,0);
    button('Text & image').click();await tick();assert.equal(document.querySelectorAll('textarea')[1].required,true);
    button('Account').click();await tick();
    assert.ok(!document.body.textContent.includes('Connection settings'));
    input(document.querySelector('input[type=email]'),'expert@example.com');input(document.querySelector('input[type=password]'),'example-password');await tick();
    document.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));await tick();await tick();
    assert.ok(Array.from(document.querySelectorAll('a')).some(a=>a.href==='http://localhost:4200/expert'));
    assert.match(document.body.textContent,/expert@example.com/);
    assert.ok(!JSON.stringify(store).includes('example-password'));
    assert.ok(!document.body.textContent.includes('Connection settings'));
    for(const role of ['user','admin','expert']){
      user={id:'role-test',email:'person@example.com',role};
      for(const listener of listeners)listener({auth:{newValue:{user}}});
      await tick();await tick();
      assert.equal(document.body.textContent.includes('Connection settings'),role==='admin');
      assert.equal(Boolean(button('Save connection')),role==='admin');
    }
  } finally {render(null,document.getElementById('app'));await tick();await window.happyDOM.close();}
});
