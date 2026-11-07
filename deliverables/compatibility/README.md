# FFmpeg / Python compatibility repair

Base: [1c2ed70](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/commit/1c2ed70a949db7de3c1b156539810bcc1fd4e067), including the latest 60-second sentence recording and last-frame extension. This is a separate repair branch, not a deployment or a claim that the final Demo is complete.

## Changes

- Explicit 30 fps constant-frame-rate encoding shared by source preparation, ordinary cuts, reordered/word edits and replacement-audio exports. On FFmpeg 7.1.5, concat otherwise produced 120 frames with average FPS `120000000/3966667`; strict canonical validation correctly refused the result. We correct encoding rather than relaxing frame-count or FPS checks.
- Upgrade Pydantic from 1.10.12 to 1.10.26 while retaining the v1 API and FastAPI 0.100.0. The old pin failed application import on Python 3.12.14 (`ForwardRef._evaluate` / `recursive_guard`). Development pytest is pinned to the exercised 8.3.5.
- Add exact-CFR media and pinned-stack HTTP import/edit/render/download regressions.
- Make rotation-fixture construction work with FFmpeg's current `-display_rotation` input option (legacy tag fallback for older versions).
- Make the over-target download gate test deterministic: actual FFmpeg rendering still runs, then the test explicitly injects a 22ms duration overrun. The test no longer assumes every AAC encoder version happens to add padding. This simulated overrun is not a claimed measurement of the output file.

## Reproduce in an isolated virtual environment

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python -m compileall -q backend tests
(cd frontend && npm run check && npm run build)
```

Use an installed FFmpeg/ffprobe with libx264 and AAC. This repair was exercised on FFmpeg 7.1.5, Python 3.12.14 and Node 24.22.1 on Linux. `-fps_mode` requires FFmpeg 5.1 or newer; older versions are not supported by this repair. Other OS/runtime combinations have not been verified here. Models and source media are not downloaded by the test suite.

## Verification and scope

See `validation.json` for final numbers. The HTTP test uses FastAPI TestClient with the pinned dependencies, real background workers and real FFmpeg files. It uploads controlled six-second color/tone media plus SRT, deletes the middle segment, renders exactly 120 frames at 30fps, then verifies the HTTP response bytes match the MP4 artifact. This is an ASGI/HTTP integration test, not a browser test or human speech evaluation.

The suite retains the latest 3-second and 60-second replacement-audio checks, frame-held extension, tail audio, shifted subtitles, word cuts and restoration. Speech inference in those tests is an explicit test double. Existing public-upload, task identity, duration-limit, isolation and version-protection tests remain enabled.

No models, production data, microphone, server process or public deployment were changed. Browser interaction, physical mobile/microphone behavior, ASR/Demucs/LLM quality and human listening were not independently repeated in this environment. This narrow repair is not a full security or dependency audit. Final Demo acceptance and delivery remain separate work.
