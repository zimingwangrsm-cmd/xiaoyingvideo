"""V2 deterministic media/transaction tests; mocked inference is never demo evidence."""
import copy
import json
import threading
from io import BytesIO
import subprocess
import pytest
from starlette.datastructures import UploadFile

from test_service import fixture_library, app, action, render, completed, expect_error
from backend.app import editing, speech, local_suggestions
from backend.app.schemas import ActionRequest, ProcessingRequest, ConfirmProcessingRequest, ProposalDecisionRequest
from backend.app.media import probe_media
from scripts.prepare_test_media import all_frame_colors, frequency_at


def seeded(app):
    service,owner,p=app
    raw=service.store.read('projects',p['id']);service._upgrade(raw)
    raw['words']=editing.attach_words(raw,[{'text':label,'startMs':i*1000+100,'endMs':i*1000+900}
                                           for i,label in enumerate(['甲','乙','丙','丁','戊','己'])])
    service.store.write('projects',p['id'],raw)
    return service.get_project(owner,p['id'])


def refine(app,p,kind,**fields):
    return app[0].action(app[1],p['id'],ActionRequest(expectedRevision=p['revision'],action={'type':kind,**fields}))


def wait_processing(app,job):
    app[0].futures[job['id']].result(timeout=20)
    return app[0].get_processing(app[1],job['id'])


def test_words_use_real_boundaries_and_cut_audio_video_caption_together(app):
    p=seeded(app);wid=p['words'][1]['id']
    p=refine(app,p,'delete_words',wordIds=[wid])
    assert p['metrics']['plannedDurationMs']==5000
    job=completed(app,render(app,p));assert job['status']=='succeeded'
    video=app[0].artifact_path(app[1],job['artifactId'],'video')
    assert all_frame_colors(video)==[0]*30+[1]*60+[2]*60
    record=json.loads(app[0].artifact_path(app[1],job['artifactId'],'record').read_text())
    assert '乙' not in ''.join(c['text'] for c in record['captions'])
    assert abs(frequency_at(video,1.5)-660)<5
    p=refine(app,p,'restore_words',wordIds=[wid]);assert p['metrics']['plannedDurationMs']==6000


def test_sentence_reorder_changes_actual_media_and_subtitle_order(app):
    p=seeded(app);p=refine(app,p,'move_block',blockId='s03',direction=-1)
    p=refine(app,p,'move_block',blockId='s03',direction=-1)
    assert p['edit']['order']==['s03','s01','s02']
    job=completed(app,render(app,p));assert job['status']=='succeeded'
    video=app[0].artifact_path(app[1],job['artifactId'],'video')
    assert all_frame_colors(video)==[2]*60+[0]*60+[1]*60
    assert abs(frequency_at(video,.5)-880)<5
    record=json.loads(app[0].artifact_path(app[1],job['artifactId'],'record').read_text())
    assert record['captions'][0]['text']=='戊己。'
    assert record['captions'][1]['startMs']>record['captions'][0]['endMs']


def test_caption_and_word_corrections_do_not_change_audio_intervals(app):
    p=seeded(app);before=editing.timeline(p)[0]
    p=refine(app,p,'correct_word',wordId=p['words'][0]['id'],text='正确内容')
    assert editing.timeline(p)[0]==before
    assert '正确内容' in editing.timeline(p)[1][0]['text']
    p=refine(app,p,'correct_caption',blockId='s01',text='整段人工校对。')
    assert editing.timeline(p)[0]==before
    with pytest.raises(ValueError,match='整段校对'):
        refine(app,p,'delete_words',wordIds=[p['words'][0]['id']])
    p=refine(app,p,'correct_caption',blockId='s01',text='')
    p=refine(app,p,'delete_words',wordIds=[p['words'][0]['id']]);assert p['metrics']['plannedDurationMs']==5000


def test_lock_restores_words_and_protects_interior(app):
    p=seeded(app);wid=p['words'][0]['id']
    p=refine(app,p,'delete_words',wordIds=[wid]);p=action(app,p,'lock',blockIds=['s01'])
    assert wid not in p['edit']['deletedWordIds']
    with pytest.raises(ValueError,match='必留'):
        refine(app,p,'delete_words',wordIds=[wid])
    p=action(app,p,'unlock',blockIds=['s01']);p=refine(app,p,'delete_words',wordIds=[w['id'] for w in p['words']])
    assert p['metrics']['keptCount']==0
    expect_error('empty_selection',lambda:render(app,p))
    p=action(app,p,'restore_all');assert p['metrics']['plannedDurationMs']==6000


def test_pending_rewrite_requires_recording_or_withdrawal(app):
    p=seeded(app);p=refine(app,p,'set_rewrite',blockId='s01',text='改成新的说法。')
    assert p['metrics']['pendingRewriteCount']==1
    expect_error('pending_recording',lambda:render(app,p))
    p=refine(app,p,'set_rewrite',blockId='s01',text='')
    assert completed(app,render(app,p))['status']=='succeeded'


def test_partial_proposal_decisions_rebase_and_manual_edit_invalidates(app,monkeypatch):
    p=seeded(app)
    monkeypatch.setattr(local_suggestions,'generate',lambda *_:{'strategy':'测试明确操作','items':[
        {'type':'delete_block','blockId':'s01','reason':'测试删减'},
        {'type':'rewrite','blockId':'s02','text':'新的说法。','reason':'需要补录'}]})
    job=wait_processing(app,app[0].start_processing(app[1],p['id'],ProcessingRequest(expectedRevision=p['revision']),'suggestions'))
    proposal=job['result']
    out=app[0].decide_proposal(app[1],p['id'],ProposalDecisionRequest(expectedRevision=p['revision'],proposalId=proposal['id'],itemIds=['i01'],decision='accept'))
    assert out['proposal']['baseRevision']==out['project']['revision']
    assert out['proposal']['items'][1]['status']=='pending'
    p=out['project'];p=refine(app,p,'annotate',blockId='s03',text='人工改动')
    expect_error('proposal_stale',lambda:app[0].decide_proposal(app[1],p['id'],ProposalDecisionRequest(expectedRevision=p['revision'],proposalId=proposal['id'],itemIds=['i02'],decision='accept')),409)


def test_model_cannot_delete_locked_or_unknown_ids(app):
    p=seeded(app);p=action(app,p,'lock',blockIds=['s01'])
    proposal=app[0]._proposal_v2(p,{'strategy':'测试','items':[{'type':'delete_block','blockId':'s01','reason':'错'},
        {'type':'delete_words','blockId':'s02','wordIds':['missing'],'reason':'错'},
        {'type':'delete_block','blockId':'unknown','reason':'错'}]},'local_llm')
    assert proposal['items']==[]


def test_transcription_confirmation_wont_overwrite_concurrent_edit(app,monkeypatch):
    p=seeded(app)
    result={'cues':p['cues'],'words':[{'text':w['text'],'startMs':w['startMs'],'endMs':w['endMs']} for w in p['words']]}
    monkeypatch.setattr(speech,'run_worker',lambda *_,**__:result)
    job=wait_processing(app,app[0].start_processing(app[1],p['id'],ProcessingRequest(expectedRevision=p['revision']),'transcribe'))
    p=action(app,p,'delete',blockIds=['s02'])
    expect_error('transcript_stale',lambda:app[0].confirm_transcript(app[1],p['id'],ConfirmProcessingRequest(expectedRevision=p['revision'],jobId=job['id'])),409)
    assert 's02' not in app[0].get_project(app[1],p['id'])['edit']['keptBlockIds']


def test_recording_too_long_is_rejected_before_transcription(app,tmp_path,monkeypatch):
    p=seeded(app);file=tmp_path/'long.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=500:duration=3','-y',str(file)],check=True)
    def forbidden(*a,**k):raise AssertionError('Should not transcribe oversized recording')
    monkeypatch.setattr(speech,'run_worker',forbidden)
    audio=UploadFile(filename='long.wav',file=BytesIO(file.read_bytes()))
    job=app[0].upload_recording(app[1],p['id'],p['revision'],'s01',audio,False)
    job=wait_processing(app,job)
    assert job['status']=='failed' and '请缩短' in job['error']
    assert app[0].get_project(app[1],p['id'])['revision']==p['revision']


def test_processing_jobs_are_owned_and_v1_upgrade_keeps_backup(app,monkeypatch):
    p=refine(app,app[2],'annotate',blockId='s01',text='口误')
    assert (app[0].store.project_dir(p['id'])/'v1-before-upgrade.json').is_file()
    monkeypatch.setattr(local_suggestions,'generate',lambda *_:{'strategy':'无需修改','items':[]})
    job=wait_processing(app,app[0].start_processing(app[1],p['id'],ProcessingRequest(expectedRevision=p['revision']),'suggestions'))
    other,_=app[0].session(None)
    expect_error('not_found',lambda:app[0].get_processing(other,job['id']),404)


def test_contiguous_measured_words_stay_editable_and_zero_duration_text_is_preserved():
    p={'blocks':[{'id':'s01','clipStartFrame':0,'clipEndFrame':30}]}
    raw=[{'text':'甲','startMs':20,'endMs':300},{'text':'乙','startMs':300,'endMs':600},
         {'text':'丙','startMs':600,'endMs':600},{'text':'丁','startMs':600,'endMs':950}]
    words=editing.attach_words(p,raw)
    assert ''.join(w['text'] for w in words)=='甲乙丙丁'
    assert len(words)==3
    assert words[0]['clipStartFrame']==0 and words[-1]['clipEndFrame']==30
    assert all(a['clipEndFrame']==b['clipStartFrame'] for a,b in zip(words,words[1:]))


def test_accept_all_is_one_atomic_undoable_edit(app,monkeypatch):
    p=seeded(app);before=copy.deepcopy(p['edit'])
    proposal=app[0]._proposal_v2(p,{'strategy':'测试批量确认','items':[
        {'type':'delete_block','blockId':'s01','reason':'删除第一段'},
        {'type':'move_block','blockId':'s03','direction':-1,'reason':'调整次序'}]},'local_llm')
    result=app[0].decide_proposal(app[1],p['id'],ProposalDecisionRequest(expectedRevision=p['revision'],proposalId=proposal['id'],itemIds=['i01','i02'],decision='accept'))
    assert result['project']['revision']==p['revision']+1
    restored=action(app,result['project'],'undo')
    assert restored['edit']==before


def test_model_caption_correction_is_text_only_and_can_be_rejected(app):
    p=seeded(app)
    proposal=app[0]._proposal_v2(p,{'strategy':'校对转写','items':[
        {'type':'caption_correction','blockId':'s01','text':'修正字幕。','reason':'同音错字，请回听'}]},'local_llm')
    result=app[0].decide_proposal(app[1],p['id'],ProposalDecisionRequest(expectedRevision=p['revision'],proposalId=proposal['id'],itemIds=['i01'],decision='reject'))
    assert result['project']['revision']==p['revision']
    assert result['proposal']['items'][0]['status']=='rejected'


def test_restart_marks_processing_interrupted_without_losing_edits(app):
    from backend.app.service import Service
    from backend.app.storage import new_id
    p=seeded(app);p=refine(app,p,'annotate',blockId='s01',text='重启后保留')
    jid=new_id()
    app[0].store.write('processing',jid,{'id':jid,'projectId':p['id'],'kind':'transcribe','status':'running',
        'phase':'transcribing','baseRevision':p['revision'],'createdAt':0,'result':None,'_owner':app[1]})
    app[0].close();reopened=Service(app[0].settings)
    try:
        job=reopened.get_processing(app[1],jid)
        assert job['status']=='interrupted'
        assert reopened.get_project(app[1],p['id'])['edit']==p['edit']
    finally:reopened.close()
