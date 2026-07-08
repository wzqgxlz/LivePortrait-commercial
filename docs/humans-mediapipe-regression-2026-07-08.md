# Humans MediaPipe Regression Report - 2026-07-08

## Scope

This report covers the first Humans mode regression pass after replacing the
commercial-risk InsightFace detection path with MediaPipe. Animals mode is not
covered.

## Environment

- Branch: `codex/commercial-mediapipe-cropper`
- Runtime: local virtual environment `LivePortrait_env`
- Device path: CPU only, `--flag-force-cpu --no-flag-use-half-precision`
- Human weights: `pretrained_weights/liveportrait`
- MediaPipe detector model: `pretrained_weights/mediapipe/blaze_face_short_range.tflite`
- Forbidden legacy detector weights: absent from `pretrained_weights`

## Validation Commands

```powershell
.\LivePortrait_env\Scripts\python scripts\commercial_safety_scan.py
python -m pytest tests/test_commercial_mediapipe_cropper.py tests/test_commercial_safety_guardrails.py -q
python -m py_compile src\utils\mediapipe_face_analysis.py src\utils\cropper.py
```

All three checks passed in this regression pass.

## Fast Detection Sweep

MediaPipe detected at least one face in every `.jpg` file under
`assets/examples/source`. Several samples returned multiple detections, so the
current `large-small` selection rule remains important:

| Source Pattern | Result |
| --- | --- |
| Single clear face | Detected successfully |
| Small face | Detected successfully |
| Close-up face | Detected successfully |
| Multi-face or false-positive-prone image | Detected successfully, largest face selected |

## Full Regression Samples

All commands used `--flag-force-cpu --no-flag-use-half-precision`.

| Case | Type | Output | Result | Notes |
| --- | --- | --- | --- | --- |
| `s9.jpg + d12.jpg` | Image-driven image | `animations/regression_humans/s9--d12.jpg` | Pass | Baseline static generation completed. |
| `s9.jpg + d1.pkl` | Template-driven video, 16 frames | `animations/regression_humans_template/s9--d1.mp4` | Pass | Multi-frame output completed on CPU. |
| `s10.jpg + d12.jpg` | Image-driven image | `animations/regression_humans_batch/s10--d12.jpg` | Pass | Single-face source completed. |
| `s3.jpg + d19.jpg` | Image-driven image | `animations/regression_humans_batch/s3--d19.jpg` | Pass | Small source face completed. |
| `s23.jpg + d30.jpg` | Image-driven image | `animations/regression_humans_batch/s23--d30.jpg` | Pass | Close-up/multi-detection-prone source completed. |
| `s42.jpg + d38.jpg` | Image-driven image | `animations/regression_humans_batch/s42--d38.jpg` | Pass | Strong facial expression completed. |
| `s0.jpg + d8.jpg` | Image-driven image | `animations/regression_humans_batch/s0--d8.jpg` | Pass | Multi-detection source completed. |

Local visual contact sheet:

```text
animations/regression_humans_batch/contact_sheet.jpg
```

## Known Gaps

- Direct driving-video regression with `d18.mp4` was stopped after a long CPU
  run produced no visible output directory. This should be retried on a GPU
  machine or with a shorter clipped video.
- CPU mode is suitable for smoke tests, but not for realistic throughput or
  commercial latency assessment.
- Some example driving images are stylized or extreme; they are useful for
  robustness checks but not sufficient for final user-facing quality review.
- MediaPipe runtime emitted telemetry upload warnings from its native layer.
  They did not block generation, but production builds should review whether
  telemetry can be disabled through deployment policy or environment controls.

## Next Regression Step

Run a GPU-backed video regression set:

1. One short frontal driving video.
2. One side-turn driving video.
3. One low-light or mobile-selfie driving video.
4. One multi-face source image with explicit expected target selection.
5. One failure-case sample retained for detector-threshold tuning.

Record per-sample detection count, selected bounding box, crop stability, output
jitter, and generation time.
