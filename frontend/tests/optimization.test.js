import test from 'node:test';import assert from 'node:assert/strict';
import {cutPoints,refinementPanel} from '../src/v2views.js';
test('cut audition uses actual rendered discontinuities, including replacement audio',()=>{
 const job={spans:[{sourceStartFrame:0,sourceEndFrame:30,outputStartFrame:0},{sourceStartFrame:60,sourceEndFrame:90,outputStartFrame:30},{sourceStartFrame:90,sourceEndFrame:120,outputStartFrame:60},{sourceStartFrame:120,sourceEndFrame:150,outputStartFrame:90,recordingId:'new'}]};
 assert.deepEqual(cutPoints(job),[1,3]);
});
test('drawer shows only the active project draft and labels its three task groups',()=>{
 const state={project:{id:'B',blocks:[{id:'s01',text:'原文。',clipStartFrame:0,clipEndFrame:60}],edit:{lockedBlockIds:[]},capabilities:{}},health:{allowUploads:false},refineBlock:'s01',refineTab:'text',refineDrafts:{A:{s01:{note:'A机密草稿'}},B:{s01:{note:'B备注'}}}};
 const html=refinementPanel(state);assert(!html.includes('A机密草稿'));assert(html.includes('B备注'));assert(html.includes('文字校对'));assert(html.includes('公开样例模式不可上传补录'));
});
