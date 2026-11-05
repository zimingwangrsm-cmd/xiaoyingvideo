"""Direct service integration tests: real files/workers, no HTTP or browser claim."""
import copy
import json
from pathlib import Path
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.config import Settings
from backend.app import service as service_module
from backend.app.media import probe_media, sha256_file
from backend.app.schemas import ActionRequest, ProposalRequest, RenderRequest
from backend.app.service import AppError, Service
from backend.app.storage import new_id
from backend.app.timeline import parse_srt
from scripts.prepare_test_media import generate, all_frame_colors, frequency_at


@pytest.fixture(scope="module")
def fixture_library(tmp_path_factory):
    root = tmp_path_factory.mktemp("service_samples")
    engineering = root / "engineering"
    generate(engineering)
    for name in ("abc", "six"):
        folder = root / name
        folder.mkdir()
        shutil.copyfile(engineering / "source_abc.mp4", folder / "canonical.mp4")
        if name == "abc":
            shutil.copyfile(engineering / "source_abc.srt", folder / "sample.srt")
        else:
            text = "\n\n".join("%d\n00:00:%02d,100 --> 00:00:%02d,900\n片段%s。" %
                                 (index + 1, index, index, label) for index, label in enumerate("甲乙丙丁戊己")) + "\n"
            (folder / "sample.srt").write_text(text, encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps({"id": name, "title": "工程测试 " + name,
            "videoFile": "canonical.mp4", "subtitleFile": "sample.srt", "origin": "synthetic_sample",
            "durationMs": 6000, "transcriptVerified": False}), encoding="utf-8")
    return root


@pytest.fixture
def app(tmp_path, fixture_library):
    instance = Service(Settings(data_dir=tmp_path / "state", model_mode="rules", test_failures=True))
    instance.fixture_dir = fixture_library
    owner, _ = instance.session(None)
    project = instance.from_sample(owner, "abc")
    assert project["state"] == "ready"
    try:
        yield instance, owner, project
    finally:
        instance.close()


def action(app, project, kind, **fields):
    instance, owner, _ = app
    return instance.action(owner, project["id"], ActionRequest(expectedRevision=project["revision"],
                           action={"type": kind, **fields}))


def render(app, project, **options):
    instance, owner, _ = app
    fail = options.pop("fail", False)
    return instance.render(owner, project["id"], RenderRequest(expectedRevision=project["revision"], **options), fail=fail)


def completed(app, job):
    instance, owner, _ = app
    instance.futures[job["id"]].result(timeout=30)
    return instance.get_job(owner, job["id"])


def expect_error(code, operation, status=None):
    with pytest.raises(AppError) as error:
        operation()
    assert error.value.code == code
    if status is not None:
        assert error.value.status == status


def test_lock_restores_deleted_block_backend_protects_and_five_is_limit(app):
    instance, owner, _ = app
    project = instance.from_sample(owner, "six")
    project = action(app, project, "delete", blockIds=["s02"])
    assert "s02" not in project["edit"]["keptBlockIds"]
    project = action(app, project, "lock", blockIds=["s01", "s02", "s03", "s04", "s05"])
    assert "s02" in project["edit"]["keptBlockIds"]
    assert len(project["edit"]["lockedBlockIds"]) == 5
    before = copy.deepcopy(project)
    expect_error("locked_block", lambda: action(app, project, "delete", blockIds=["s02"]))
    expect_error("lock_limit", lambda: action(app, project, "lock", blockIds=["s06"]))
    assert instance.get_project(owner, project["id"]) == before
    proposal = instance.proposal(owner, project["id"], ProposalRequest(expectedRevision=project["revision"], mode="rules"))
    assert set(project["edit"]["lockedBlockIds"]).issubset(proposal["recommendedKeptBlockIds"])
    project = action(app, project, "set_target", targetMs=4000)
    assert project["metrics"]["targetStatus"] == "locked_conflict"
    assert project["metrics"]["lockedDurationMs"] == 5000


def test_revision_is_monotonic_undo_restores_edit_and_old_request_conflicts(app):
    instance, owner, project = app
    before = copy.deepcopy(project["edit"])
    changed = action(app, project, "delete", blockIds=["s02"])
    assert changed["revision"] == 1
    expect_error("revision_conflict", lambda: action(app, project, "delete", blockIds=["s01"]), 409)
    undone = action(app, changed, "undo")
    assert undone["revision"] == 2
    assert undone["edit"] == before
    assert not undone["canUndo"]
    expect_error("nothing_to_undo", lambda: action(app, undone, "undo"))
    assert instance.get_project(owner, project["id"])["revision"] == 2


def test_concurrent_edits_accept_exactly_one_expected_revision(app):
    instance, owner, project = app
    barrier = threading.Barrier(2)
    def edit(block):
        barrier.wait(timeout=5)
        try:
            return action(app, project, "delete", blockIds=[block])["revision"]
        except AppError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(edit, "s01"), pool.submit(edit, "s03")
        outcomes = [first.result(timeout=5), second.result(timeout=5)]
    assert outcomes.count(1) == 1 and outcomes.count("revision_conflict") == 1
    assert instance.get_project(owner, project["id"])["metrics"]["keptCount"] == 2


def test_proposal_requires_confirmation_and_stale_proposal_cannot_apply(app):
    instance, owner, project = app
    before = instance.get_project(owner, project["id"])
    proposal = instance.proposal(owner, project["id"], ProposalRequest(expectedRevision=0, mode="rules"))
    assert instance.get_project(owner, project["id"]) == before
    changed = action(app, project, "set_target", targetMs=4000)
    expect_error("proposal_stale", lambda: action(app, changed, "apply_proposal", proposalId=proposal["id"]), 409)
    assert instance.get_project(owner, project["id"]) == changed


def test_malformed_proposal_cannot_remove_a_lock_or_empty_selection(app):
    instance, owner, project = app
    project = action(app, project, "lock", blockIds=["s01"])
    proposal = instance.proposal(owner, project["id"], ProposalRequest(expectedRevision=project["revision"], mode="rules"))
    path = instance.store.project_dir(project["id"]) / "proposals" / (proposal["id"] + ".json")
    for malicious in (["s02", "s03"], [], ["s01", "s99"]):
        proposal["recommendedKeptBlockIds"] = malicious
        path.write_text(json.dumps(proposal), encoding="utf-8")
        expect_error("proposal_invalid", lambda: action(app, project, "apply_proposal", proposalId=proposal["id"]))
        assert instance.get_project(owner, project["id"]) == project


def test_empty_selection_persists_with_metrics_but_cannot_render(app):
    instance, owner, project = app
    project = action(app, project, "delete", blockIds=["s01", "s02", "s03"])
    assert project["metrics"]["targetStatus"] == "empty_selection"
    assert project["metrics"]["plannedDurationMs"] == 0
    assert instance.get_project(owner, project["id"])["edit"]["keptBlockIds"] == []
    expect_error("empty_selection", lambda: render(app, project))
    restored = action(app, project, "restore_all")
    assert restored["metrics"]["plannedDurationMs"] == 6000


def test_over_target_requires_explicit_export_acknowledgement(app):
    project = action(app, app[2], "set_target", targetMs=3000)
    expect_error("over_target", lambda: render(app, project))
    job = completed(app, render(app, project, allowOverTarget=True))
    assert job["status"] == "succeeded" and not job["targetMet"]
    assert job["overTargetAcknowledged"]
    assert app[0].artifact_path(app[1], job["artifactId"], "video").is_file()


def test_real_mp4_srt_and_record_are_from_same_snapshot_and_render_is_reused(app):
    instance, owner, project = app
    project = action(app, project, "delete", blockIds=["s02"])
    job = completed(app, render(app, project))
    assert job["status"] == "succeeded" and job["isCurrent"]
    reused = render(app, project)
    assert reused["id"] == job["id"] and reused["artifactId"] == job["artifactId"]
    video = instance.artifact_path(owner, job["artifactId"], "video")
    srt = instance.artifact_path(owner, job["artifactId"], "srt")
    record_path = instance.artifact_path(owner, job["artifactId"], "record")
    preview = instance.artifact_path(owner, job["artifactId"], "video", require_current=False)
    assert video == preview
    record = json.loads(record_path.read_text())
    assert record["videoSha256"] == sha256_file(video)
    assert record["subtitleSha256"] == sha256_file(srt)
    assert record["artifactId"] == job["artifactId"]
    assert record["snapshotRevision"] == project["revision"]
    assert record["spans"] == job["spans"]
    assert record["deletedBlockIds"] == ["s02"]
    assert probe_media(video)["totalFrames"] == 120
    assert all_frame_colors(video) == [0] * 60 + [2] * 60
    assert abs(frequency_at(video, 0.5) - 440) <= 5
    assert abs(frequency_at(video, 2.5) - 880) <= 5
    captions = parse_srt(srt.read_text(), 4000)
    assert len(captions) == 2 and "C：" in captions[1]["text"]
    assert captions[1]["startMs"] == 2100
    assert [cue["text"] for cue in captions] == [cue["text"] for cue in record["captions"]]


def test_edit_during_render_marks_result_old_and_blocks_all_current_downloads(app, monkeypatch):
    instance, owner, project = app
    entered, release = threading.Event(), threading.Event()
    real_render = service_module.render_spans
    def blocked_render(*arguments, **options):
        entered.set()
        assert release.wait(timeout=10)
        return real_render(*arguments, **options)
    monkeypatch.setattr(service_module, "render_spans", blocked_render)
    job = render(app, project)
    try:
        assert entered.wait(timeout=5)
        duplicate = render(app, project)
        assert duplicate["id"] == job["id"]
        project = action(app, project, "delete", blockIds=["s02"])
        assert not instance.get_job(owner, job["id"])["isCurrent"]
    finally:
        release.set()
    job = completed(app, job)
    assert job["status"] == "succeeded" and not job["isCurrent"]
    for kind in ("video", "srt", "vtt", "record"):
        expect_error("artifact_stale", lambda kind=kind: instance.artifact_path(owner, job["artifactId"], kind), 409)
    old_preview = instance.artifact_path(owner, job["artifactId"], "video", require_current=False)
    assert probe_media(old_preview)["totalFrames"] == 180
    fresh = completed(app, render(app, project))
    assert fresh["isCurrent"] and fresh["artifactId"] != job["artifactId"]
    assert probe_media(instance.artifact_path(owner, fresh["artifactId"], "video"))["totalFrames"] == 120


def test_actual_encoder_overshoot_blocks_download_until_same_job_is_acknowledged(app):
    instance, owner, project = app
    project = action(app, project, "delete", blockIds=["s02"])
    project = action(app, project, "set_target", targetMs=4000)
    job = completed(app, render(app, project))
    assert job["status"] == "succeeded" and job["actualDurationMs"] > 4000
    expect_error("actual_over_target", lambda: instance.artifact_path(owner, job["artifactId"], "video"), 409)
    acknowledged = render(app, project, allowOverTarget=True)
    assert acknowledged["id"] == job["id"]
    assert instance.artifact_path(owner, job["artifactId"], "video").is_file()


def test_acknowledgement_made_while_render_is_running_survives_progress_updates(app, monkeypatch):
    instance, owner, project = app
    project = action(app, project, "set_target", targetMs=6000)
    entered, release = threading.Event(), threading.Event()
    real_render = service_module.render_spans
    def blocked_render(*arguments, **options):
        entered.set()
        assert release.wait(timeout=10)
        return real_render(*arguments, **options)
    monkeypatch.setattr(service_module, "render_spans", blocked_render)
    job = render(app, project)
    try:
        assert entered.wait(timeout=5)
        acknowledged = render(app, project, allowOverTarget=True)
        assert acknowledged["id"] == job["id"] and acknowledged["overTargetAcknowledged"]
    finally:
        release.set()
    job = completed(app, job)
    assert job["status"] == "succeeded"
    assert job["overTargetAcknowledged"]
    assert instance.artifact_path(owner, job["artifactId"], "video").is_file()


@pytest.mark.parametrize("paused_status", ["running", "succeeded"])
def test_concurrent_acknowledgement_cannot_be_lost_between_progress_read_and_write(app, monkeypatch, paused_status):
    instance, owner, project = app
    project = action(app, project, "set_target", targetMs=6000)
    entered, release, acknowledged = threading.Event(), threading.Event(), threading.Event()
    original_write = instance.store.write
    def controlled_write(kind, key, data):
        if (kind == "jobs" and data.get("status") == paused_status and
                threading.current_thread().name.startswith("koubo-render") and not entered.is_set()):
            # Pause after progress read the persisted acknowledgement but before
            # its write. A proper project lock serializes the other request.
            entered.set()
            assert release.wait(timeout=10)
        return original_write(kind, key, data)
    monkeypatch.setattr(instance.store, "write", controlled_write)
    job = render(app, project)
    def confirm():
        try:
            return render(app, project, allowOverTarget=True)
        finally:
            acknowledged.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            assert entered.wait(timeout=5)
            confirmation = pool.submit(confirm)
            acknowledged.wait(timeout=0.5)
        finally:
            release.set()
        assert confirmation.result(timeout=5)["id"] == job["id"]
    job = completed(app, job)
    assert job["status"] == "succeeded"
    assert job["overTargetAcknowledged"]
    assert instance.artifact_path(owner, job["artifactId"], "video").is_file()


def test_injected_failures_preserve_edits_and_retry_generates_new_job(app):
    instance, owner, project = app
    project = action(app, project, "delete", blockIds=["s02"])
    before = copy.deepcopy(project["edit"])
    expect_error("injected_proposal_failure", lambda: instance.proposal(owner, project["id"],
        ProposalRequest(expectedRevision=project["revision"], mode="rules"), fail=True), 503)
    retried_proposal = instance.proposal(owner, project["id"],
        ProposalRequest(expectedRevision=project["revision"], mode="rules"))
    assert retried_proposal["baseRevision"] == project["revision"]
    assert instance.get_project(owner, project["id"])["edit"] == before
    failed = completed(app, render(app, project, fail=True))
    assert failed["status"] == "failed" and failed["artifact"] is None
    after = instance.get_project(owner, project["id"])
    assert after["edit"] == before and after["revision"] == project["revision"]
    retried = completed(app, render(app, after))
    assert retried["status"] == "succeeded" and retried["id"] != failed["id"]


def test_restart_interrupts_unfinished_work_and_keeps_completed_artifact(app):
    instance, owner, project = app
    succeeded = completed(app, render(app, project))
    original = instance.store.read("jobs", succeeded["id"])
    unfinished_ids = []
    for status in ("queued", "running"):
        interrupted = dict(original, id=new_id(), status=status, artifactId=None)
        instance.store.write("jobs", interrupted["id"], interrupted)
        unfinished_ids.append(interrupted["id"])
    preparing = instance._new_project(owner, "interrupted import", "user_upload")
    instance.close()
    reopened = Service(instance.settings)
    try:
        for jid in unfinished_ids:
            job = reopened.get_job(owner, jid)
            assert job["status"] == "interrupted" and job["errorCode"] == "interrupted"
        assert reopened.get_project(owner, preparing["id"])["state"] == "failed"
        assert reopened.get_job(owner, succeeded["id"])["status"] == "succeeded"
        video = reopened.artifact_path(owner, succeeded["artifactId"], "video")
        assert probe_media(video)["totalFrames"] == 180
    finally:
        reopened.close()


def test_two_owners_cannot_read_or_mutate_each_others_projects_jobs_or_artifacts(app):
    instance, owner, project = app
    other, created = instance.session(None)
    assert created and other != owner
    assert instance.session(owner) == (owner, False)
    other_project = instance.from_sample(other, "abc")
    assert other_project["id"] != project["id"]
    job = completed(app, render(app, project))
    expect_error("not_found", lambda: instance.get_project(other, project["id"]), 404)
    expect_error("not_found", lambda: instance.source_path(other, project["id"], "video"), 404)
    expect_error("not_found", lambda: instance.get_job(other, job["id"]), 404)
    expect_error("not_found", lambda: instance.artifact_path(other, job["artifactId"], "video", require_current=False), 404)
    expect_error("not_found", lambda: instance.action(other, project["id"], ActionRequest(expectedRevision=0,
        action={"type": "delete", "blockIds": ["s02"]})), 404)
    assert instance.get_project(owner, project["id"])["revision"] == 0
    assert instance.get_project(other, other_project["id"])["revision"] == 0


def test_failure_injection_is_ignored_when_developer_flag_is_disabled(app):
    instance, owner, project = app
    instance.settings.test_failures = False
    proposal = instance.proposal(owner, project["id"], ProposalRequest(expectedRevision=0, mode="rules"), fail=True)
    assert proposal["source"] == "rules"
    assert completed(app, render(app, project, fail=True))["status"] == "succeeded"


def test_second_service_cannot_interrupt_work_in_the_same_data_directory(app, monkeypatch):
    instance, owner, project = app
    entered, release = threading.Event(), threading.Event()
    real_render = service_module.render_spans
    def wait_for_release(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=10)
        return real_render(*args, **kwargs)
    monkeypatch.setattr(service_module, 'render_spans', wait_for_release)
    job = render(app, project)
    try:
        assert entered.wait(timeout=5)
        with pytest.raises(RuntimeError, match='数据目录正在由另一个服务使用'):
            Service(instance.settings)
        assert instance.get_job(owner, job['id'])['status'] == 'running'
    finally:
        release.set()
    assert completed(app, job)['status'] == 'succeeded'


def test_repeating_current_selection_keeps_revision_history_and_artifact(app):
    instance, owner, project = app
    project = action(app, project, 'lock', blockIds=['s01'])
    project = action(app, project, 'delete', blockIds=['s02'])
    job = completed(app, render(app, project))
    before = copy.deepcopy(project)
    for kind, fields in [
        ('set_target', {'targetMs': project['edit']['targetMs']}),
        ('lock', {'blockIds': ['s01']}),
        ('delete', {'blockIds': ['s02']}),
        ('restore', {'blockIds': ['s03']}),
        ('unlock', {'blockIds': ['s03']}),
    ]:
        project = action(app, project, kind, **fields)
        assert project['revision'] == before['revision']
        assert project['edit'] == before['edit']
        assert instance.get_job(owner, job['id'])['isCurrent']
    undone = action(app, project, 'undo')
    assert 's02' in undone['edit']['keptBlockIds']
