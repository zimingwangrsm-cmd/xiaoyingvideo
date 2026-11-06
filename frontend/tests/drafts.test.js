import test from 'node:test';
import assert from 'node:assert/strict';
import {draftFor,setDraft,clearSavedDraft,projectHasDrafts} from '../src/drafts.js';

test('same block ids in different projects do not share drafts',()=>{
 const d={};setDraft(d,'A','s01','note','A的备注');setDraft(d,'B','s01','note','B的备注');
 assert.equal(draftFor(d,'A','s01').note,'A的备注');assert.equal(draftFor(d,'B','s01').note,'B的备注');
});
test('successful field save keeps other fields and later typing',()=>{
 const d={};setDraft(d,'A','s01','caption','旧稿');setDraft(d,'A','s01','note','备注');
 setDraft(d,'A','s01','caption','发送后又修改');clearSavedDraft(d,'A','s01','caption','旧稿');
 assert.equal(draftFor(d,'A','s01').caption,'发送后又修改');
 clearSavedDraft(d,'A','s01','caption','发送后又修改');assert.equal(draftFor(d,'A','s01').note,'备注');
 assert(projectHasDrafts(d,'A'));
});
test('late save cannot clear a new project or another block',()=>{
 const d={};setDraft(d,'A','s01','note','相同内容');setDraft(d,'B','s01','note','相同内容');
 setDraft(d,'A','s02','note','相同内容');clearSavedDraft(d,'A','s01','note','相同内容');
 assert.equal(draftFor(d,'B','s01').note,'相同内容');assert.equal(draftFor(d,'A','s02').note,'相同内容');
});
