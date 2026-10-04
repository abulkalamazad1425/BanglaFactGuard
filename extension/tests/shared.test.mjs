import test from 'node:test';
import assert from 'node:assert/strict';
import { summarize, cropRect, validateDraft, EMPTY_DRAFT } from '../src/shared.js';

test('source absent and incomplete never imply FAKE or a final verdict',()=>{
  for(const source_status of ['NOT_FOUND','INCOMPLETE']) {
    const s=summarize('SOURCE_BASED',{status:'EXPERT_REVIEW',result:{source_status}});
    assert.equal(s.final,false);assert.equal(s.stage,'preliminary');
    assert.ok(!s.lines.join().includes('FAKE'));
  }
});
test('expert finalization is a separate stage from the multimodal AI prediction',()=>{
  const s=summarize('MULTIMODAL',{prediction:'FAKE',expert_overall_verdict:'REAL'},{status:'FINALIZED'});
  assert.equal(s.stage,'final:REAL');assert.equal(s.lines[0],'Expert verdict: REAL');
});
test('queued multimodal claims have no prediction and failures preserve the explanation',()=>{
  assert.deepEqual(summarize('MULTIMODAL',{status:'PENDING'}).lines,[]);
  const s=summarize('PHOTO_CARD',{status:'FAILED',failure_reason:'Unreadable card'});
  assert.equal(s.stage,'failed');assert.equal(s.error,'Unreadable card');
});
test('photocard warnings and extracted headline survive summary mapping',()=>{
  const s=summarize('PHOTO_CARD',{status:'EXPERT_REVIEW',headline:'Extracted claim',extraction_warnings:['Date conflict','Headline OCR is uncertain'],verification:{source_status:'CONFIRMED',date_status:'MISMATCHED'}});
  assert.equal(s.headline,'Extracted claim');assert.deepEqual(s.warnings,['Headline OCR is uncertain']);assert.equal(s.final,false);
  assert.ok(s.lines.includes('Date: Date mismatch')); // Actual source verification is unaffected.
});
test('capture coordinates handle display scaling and clip to viewport',()=>{
  assert.deepEqual(cropRect({x:10,y:20,width:50,height:40},{width:100,height:100},{width:200,height:200}),{x:20,y:40,width:100,height:80});
  assert.deepEqual(cropRect({x:90,y:90,width:30,height:30},{width:100,height:100},{width:150,height:150}),{x:135,y:135,width:15,height:15});
});
test('multimodal body and a real bounded image are required; whitespace is rejected',()=>{
  const d={...EMPTY_DRAFT,type:'MULTIMODAL',headline:'Title',body_text:'          '};
  assert.throws(()=>validateDraft(d,new Blob(['image'],{type:'image/png'})),/body text/);
  d.body_text='Article body text';
  assert.throws(()=>validateDraft(d,null),/image/);
  assert.doesNotThrow(()=>validateDraft(d,new Blob(['image'],{type:'image/png'})));
});
