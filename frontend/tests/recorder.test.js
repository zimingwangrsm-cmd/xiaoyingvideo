import test from 'node:test';import assert from 'node:assert/strict';
import {encodeWav} from '../src/recorder.js';
test('recording WAV preserves speech samples, averages channels and ends at the sentence limit',async()=>{
 const left=new Float32Array([1,-1,.5,-.5]),right=new Float32Array([1,-1,-.5,.5]);
 const buffer={length:4,sampleRate:4,numberOfChannels:2,getChannelData:i=>i?right:left};
 const data=new DataView(await encodeWav(buffer,.75).arrayBuffer());
 assert.equal(data.byteLength,50);assert.equal(data.getUint32(24,true),4);assert.equal(data.getUint16(22,true),1);
 assert.equal(data.getUint32(40,true),6);assert.equal(data.getInt16(44,true),32767);assert.equal(data.getInt16(46,true),-32768);assert.equal(data.getInt16(48,true),0);
});
test('cancelled permission request stops a late microphone stream without recording',async()=>{
 const {SentenceRecorder}=await import('../src/recorder.js');
 const originals=Object.fromEntries(['navigator','isSecureContext','MediaRecorder'].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)]));
 let resolve,stopped=0,created=0,ready=0;
 try{
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:()=>new Promise(r=>resolve=r)}}});
  Object.defineProperty(globalThis,'isSecureContext',{configurable:true,value:true});
  Object.defineProperty(globalThis,'MediaRecorder',{configurable:true,value:class {constructor(){created++}static isTypeSupported(){return true}}});
  const recorder=new SentenceRecorder(()=>{},()=>ready++);
  const started=recorder.start({projectId:'old',blockId:'s01'},5);assert(recorder.active);recorder.cancel();
  resolve({getTracks:()=>[{stop:()=>stopped++}]});await started;
  assert.equal(stopped,1);assert.equal(created,0);assert.equal(ready,0);assert(!recorder.active);
 }finally{for(const [key,descriptor]of Object.entries(originals)){if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key]}}
});
