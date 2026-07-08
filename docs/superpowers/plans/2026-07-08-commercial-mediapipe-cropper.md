# Commercial MediaPipe Cropper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace LivePortrait's commercial-risk InsightFace detection/cropping dependency with a MediaPipe-based detector while keeping the LivePortrait inference path unchanged.

**Architecture:** Add a small MediaPipe adapter that returns the same face-like fields currently consumed by `Cropper`. Keep `Cropper`'s public behavior and landmark refinement flow intact, then remove InsightFace code/configuration so commercial builds cannot load the non-commercial `buffalo_l` model.

**Tech Stack:** Python, NumPy, OpenCV, MediaPipe, pytest.

---

### Task 1: Commercial Safety Tests

**Files:**
- Create: `tests/test_commercial_mediapipe_cropper.py`
- Modify: none

- [ ] **Step 1: Write failing tests**

Create tests that assert `Cropper` imports without InsightFace, `CropConfig` no longer exposes `insightface_root`, and the MediaPipe adapter sorts/limits face results.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_commercial_mediapipe_cropper.py -q`

Expected: failures because the MediaPipe adapter does not exist yet and `Cropper` still imports `FaceAnalysisDIY`.

### Task 2: MediaPipe Adapter

**Files:**
- Create: `src/utils/mediapipe_face_analysis.py`
- Test: `tests/test_commercial_mediapipe_cropper.py`

- [ ] **Step 1: Implement adapter**

Create `MediaPipeFaceAnalysis` with `prepare()`, `warmup()`, and `get()` methods matching the existing call sites. Convert MediaPipe detections into face records containing `bbox`, `det_score`, `kps`, and `landmark_2d_106`.

- [ ] **Step 2: Verify adapter tests pass**

Run: `python -m pytest tests/test_commercial_mediapipe_cropper.py -q`

Expected: adapter tests pass; Cropper import tests may still fail until Task 3.

### Task 3: Cropper Switch

**Files:**
- Modify: `src/utils/cropper.py`
- Modify: `src/config/crop_config.py`
- Modify: `requirements_base.txt`
- Test: `tests/test_commercial_mediapipe_cropper.py`

- [ ] **Step 1: Replace InsightFace import and initialization**

Change `Cropper` to instantiate `MediaPipeFaceAnalysis`, remove InsightFace provider/root handling, and keep the human landmark runner initialization unchanged.

- [ ] **Step 2: Add dependency**

Add `mediapipe` to `requirements_base.txt`.

- [ ] **Step 3: Verify tests pass**

Run: `python -m pytest tests/test_commercial_mediapipe_cropper.py -q`

Expected: all tests pass.

### Task 4: Remove Commercial-Risk InsightFace Source

**Files:**
- Delete: `src/utils/face_analysis_diy.py`
- Delete: `src/utils/dependencies/insightface/`
- Modify: `assets/docs/directory-structure.md`
- Test: source scan

- [ ] **Step 1: Delete InsightFace implementation files**

Remove the local InsightFace wrapper and vendored dependency tree.

- [ ] **Step 2: Run safety scan**

Run: `rg -n "FaceAnalysisDIY|buffalo_l|insightface_root|dependencies/insightface|pretrained_weights/insightface" src tests requirements*.txt assets/docs`

Expected: no commercial runtime references remain. License/readme acknowledgements may still mention InsightFace historically.

### Task 5: Final Verification

**Files:**
- All touched files

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_commercial_mediapipe_cropper.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run import smoke test**

Run: `python -c "from src.utils.cropper import Cropper; from src.config.crop_config import CropConfig; print('ok')"`

Expected: prints `ok`.

- [ ] **Step 3: Review diff**

Run: `git diff --stat` and `git diff --check`

Expected: only planned files changed and no whitespace errors.
