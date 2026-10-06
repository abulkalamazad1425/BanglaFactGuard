import test from 'node:test';
import assert from 'node:assert/strict';
import { summarize, cropRect, validateDraft, EMPTY_DRAFT, resultLine, headlinePreview, MODES, HttpError, isDeletedOnServer, recheckDelay } from '../src/shared.js';

test('source absent and incomplete never imply FAKE or a final verdict',()=>{
  for(const source_status of ['NOT_FOUND','INCOMPLETE']) {
    const s=summarize('SOURCE_BASED',{status:'EXPERT_REVIEW',result:{source_status}});
    assert.equal(s.final,false);assert.equal(s.stage,'preliminary');
    assert.ok(!s.lines.join().includes('FAKE'));
  }
});
test('expert finalization is a separate stage from the multimodal AI prediction',()=>{
  const s=summarize('MULTIMODAL',{prediction:'FAKE',expert_overall_verdict:'REAL'},{status:'FINALIZED'});
  assert.equal(s.stage,'final:REAL');assert.equal(s.lines[0],'Final decision: Real');
  assert.ok(s.lines.includes('AI decision: Likely Fake')); // shown apart, never merged into the final decision
});
test('preliminary predictions and historical Activity use readable consistent labels',()=>{
  for (const [prediction,label] of [['FAKE','Likely Fake'],['NON_FAKE','Likely Real']]) {
    const result=summarize('MULTIMODAL',{prediction});
    assert.deepEqual(result.lines,[`AI decision: ${label}`]);
    assert.equal(resultLine(`AI prediction: ${prediction} (preliminary)`),`AI decision: ${label}`);
  }
  assert.equal(resultLine('Expert verdict: MISLEADING'),'Final decision: Misleading');
  assert.equal(resultLine('Source: Confirmed'),null); // a found source is never shown in the extension
  assert.equal(resultLine('Source: Not found'),'Not found in claimed source');
  assert.equal(resultLine('Date: Date mismatch'),'Date: Mismatched');
});
test('queued multimodal claims have no prediction and failures preserve the explanation',()=>{
  assert.deepEqual(summarize('MULTIMODAL',{status:'PENDING'}).lines,[]);
  const s=summarize('PHOTO_CARD',{status:'FAILED',failure_reason:'Unreadable card'});
  assert.equal(s.stage,'failed');assert.equal(s.error,'Unreadable card');
});
test('photocard extracted headline and card date drive the summary',()=>{
  const s=summarize('PHOTO_CARD',{status:'EXPERT_REVIEW',headline:'Extracted claim',published_date:'2026-01-02',claimed_source_text:'prothomalo.com',verification:{source_status:'CONFIRMED',date_status:'MISMATCHED'}});
  assert.equal(s.headline,'Extracted claim');assert.deepEqual(s.warnings,[]);assert.equal(s.final,false);
  assert.ok(s.lines.includes('Date: Mismatched')); // Actual source verification is unaffected.
  const noDate=summarize('PHOTO_CARD',{status:'EXPERT_REVIEW',verification:{source_status:'CONFIRMED',date_status:'MISMATCHED',headline_status:'EXACT_MATCHED'}});
  assert.deepEqual(noDate.lines,['Headline: Exact Matched']); // no claimed date -> no date comparison
});
test('capture coordinates handle display scaling and clip to viewport',()=>{
  assert.deepEqual(cropRect({x:10,y:20,width:50,height:40},{width:100,height:100},{width:200,height:200}),{x:20,y:40,width:100,height:80});
  assert.deepEqual(cropRect({x:90,y:90,width:30,height:30},{width:100,height:100},{width:150,height:150}),{x:135,y:135,width:15,height:15});
});
test('multimodal body and a real bounded image are required; whitespace is rejected',()=>{
  const d={...EMPTY_DRAFT,type:'MULTIMODAL',headline:'Title',body_text:'          '};
  assert.throws(()=>validateDraft(d,new Blob(['image'],{type:'image/png'})),/article text/);
  d.body_text='Article body text';
  assert.throws(()=>validateDraft(d,null),/image/);
  assert.doesNotThrow(()=>validateDraft(d,new Blob(['image'],{type:'image/png'})));
});
test('headline status is Exact Matched / Meaning Preserved / Altered; a missing article hides everything else',()=>{
  const lines=s=>summarize('SOURCE_BASED',{status:'EXPERT_REVIEW',result:s}).lines;
  assert.deepEqual(lines({source_status:'CONFIRMED',content_status:'ALTERED',headline_status:'ALTERED'}),['Headline: Altered']);
  assert.deepEqual(lines({source_status:'CONFIRMED',content_status:'MATCHED',headline_status:'EXACT_MATCHED'}),['Headline: Exact Matched']);
  assert.deepEqual(lines({source_status:'CONFIRMED',content_status:'MATCHED'}),['Headline: Meaning Preserved']); // no exactness evidence
  assert.deepEqual(lines({source_status:'CONFIRMED',content_status:null}),['Headline: No verdict']);
  assert.deepEqual(lines({source_status:'NOT_FOUND',content_status:null,date_status:'MATCHED',claimed_published_date:'2026-01-01'}),['Not found in claimed source']);
  assert.ok(!lines({source_status:'CONFIRMED',headline_status:'EXACT_MATCHED'}).some(l=>/found|confirmed/i.test(l)));
});
test('required fields per submission type, with the failing field named',()=>{
  const img=new Blob(['image'],{type:'image/png'});
  const fieldOf=(d,i)=>{try{validateDraft({...EMPTY_DRAFT,...d},i);return null;}catch(e){return e.field;}};
  assert.equal(fieldOf({type:'SOURCE_BASED',headline:'Short',claimed_source_text:''}),'claimed_source_text');
  assert.equal(fieldOf({type:'SOURCE_BASED',headline:'abc',claimed_source_text:'x'}),'headline');
  assert.equal(fieldOf({type:'SOURCE_BASED',headline:'Valid headline',claimed_source_text:'Prothom Alo'}),null); // body optional
  assert.equal(fieldOf({type:'PHOTO_CARD'},null),'image');
  assert.equal(fieldOf({type:'PHOTO_CARD',claimed_source_text:''},img),null); // image only: outlet/date come from the card
  assert.equal(fieldOf({type:'MULTIMODAL',headline:'',body_text:'long enough text'},img),'headline');
  assert.equal(fieldOf({type:'MULTIMODAL',headline:'H',body_text:'long enough text'},null),'image');
});
test('headline preview keeps five words and adds ... only when longer',()=>{
  assert.equal(headlinePreview('  এক  দুই\u00a0তিন চার পাঁচ ছয় '),'এক দুই তিন চার পাঁচ...');
  assert.equal(headlinePreview('one two three four five'),'one two three four five');
  assert.equal(headlinePreview(''),'');
});

test('input modes are always Text & source, Photo card, Text & image',()=>{
  assert.deepEqual(MODES.map(([,label])=>label),['Text & source','Photo card','Text & image']);
});
test('only the server naming this submission as not found counts as a deletion',()=>{
  assert.equal(isDeletedOnServer(new HttpError('x',404,{error:'not_found',submission_id:'abc'}),'abc'),true);
  assert.equal(isDeletedOnServer(new HttpError('x',404,'Not Found'),'abc'),false);
  assert.equal(isDeletedOnServer(new HttpError('x',404,{error:'not_found',submission_id:'zzz'}),'abc'),false);
  assert.equal(isDeletedOnServer(new HttpError('x',500,{error:'not_found',submission_id:'abc'}),'abc'),false);
  assert.equal(isDeletedOnServer(Error('offline'),'abc'),false);
  assert.ok(recheckDelay('FINALIZED')>recheckDelay('EXPERT_REVIEW') && recheckDelay('EXPERT_REVIEW')>recheckDelay('PENDING'));
  assert.ok(Number.isFinite(recheckDelay('FAILED')));
});
