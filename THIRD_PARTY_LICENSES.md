# Third-Party Licenses and Commercial Safety Notes

This document is a preliminary engineering inventory for the commercial-safe
LivePortrait build. It is not legal advice. Before commercial distribution,
review the upstream license files, packaged wheel metadata, model cards, and
deployment terms with counsel.

## Commercial-Safe Build Scope

- First supported scope: Humans mode only.
- Face detection: MediaPipe replaces the original InsightFace detection path.
- LivePortrait inference code path is otherwise kept as close to upstream as
  possible.
- Animals mode is not yet cleared for commercial use in this build because it
  includes additional XPose and animal-model dependencies that need separate
  license review.

## Removed or Forbidden Components

The commercial-safe build must not include or load these legacy detector
components:

- `pretrained_weights/insightface`
- `src/utils/dependencies/insightface`
- `FaceAnalysisDIY`
- `buffalo_l`
- `insightface_root`

The local guardrails are:

- `scripts/commercial_safety_scan.py` scans runtime files for forbidden
  references.
- `src/utils/commercial_safety.py` blocks startup when the legacy detector
  weight directory is present.

## License Inventory

| Component | Version or Source | License | Commercial-Safe Status | Notes |
| --- | --- | --- | --- | --- |
| LivePortrait code | Local repository / upstream KlingAIResearch LivePortrait | MIT | Needs final release review | Upstream states commercial users should remove and replace InsightFace detection models to fully comply with the MIT license. |
| LivePortrait human weights | `pretrained_weights/liveportrait` | To verify against upstream release terms | Pending | Keep only after confirming model-weight terms and redistribution rights. |
| LivePortrait landmark model | `pretrained_weights/liveportrait/landmark.onnx` | To verify against upstream release terms | Pending | This build keeps using it for landmark refinement; confirm it is part of the LivePortrait commercial-safe assets. |
| MediaPipe | `mediapipe==0.10.35` | Apache-2.0 | Allowed after notice review | Replaces the InsightFace detection path. |
| PyTorch | `torch`, `torchvision`, `torchaudio` | BSD-style / BSD-3-Clause | Allowed after notice review | Verify exact wheel notices for the target CUDA/CPU distribution. |
| ONNX Runtime | `onnxruntime-gpu==1.18.0` or platform equivalent | MIT | Allowed after notice review | Verify provider-specific binaries and bundled notices. |
| OpenCV Python | `opencv-python==4.10.0.84` | Apache-2.0 for OpenCV binary package | Allowed after notice review | Verify opencv-python third-party notices for redistributed binaries. |
| Gradio | `gradio==5.1.0` | Apache-2.0 | Allowed after notice review | Used for the demo UI. |
| NumPy | `numpy==1.26.4` | BSD-style | Allowed after notice review | Verify bundled binary notices in packaged artifacts. |
| SciPy | `scipy==1.13.1` | BSD-3-Clause | Allowed after notice review | Verify bundled library notices in packaged artifacts. |
| XPose / animal mode dependencies | `src/utils/dependencies/XPose` and animal weights | To verify | Not cleared | Do not market Animals mode as commercial-ready until this review is complete. |

## Upstream References Checked

- LivePortrait upstream license: https://github.com/KlingAIResearch/LivePortrait/blob/main/LICENSE
- LivePortrait upstream project: https://github.com/KlingAIResearch/LivePortrait
- MediaPipe PyPI package: https://pypi.org/project/mediapipe/
- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0
- PyTorch license: https://github.com/pytorch/pytorch/blob/main/LICENSE
- ONNX Runtime license: https://github.com/microsoft/onnxruntime/blob/main/LICENSE
- OpenCV license: https://github.com/opencv/opencv/blob/4.x/LICENSE
- Gradio license: https://github.com/gradio-app/gradio/blob/main/LICENSE
- NumPy license: https://numpy.org/doc/stable/license.html
- SciPy license: https://github.com/scipy/scipy/blob/main/LICENSE.txt

## Release Checklist

- Run `python scripts/commercial_safety_scan.py`.
- Run `python -m pytest tests/test_commercial_mediapipe_cropper.py tests/test_commercial_safety_guardrails.py -q`.
- Confirm `pretrained_weights/insightface` is absent from release artifacts.
- Confirm packaged notices include licenses for shipped Python wheels and model
  assets.
- Complete a separate Animals mode license review before enabling it
  commercially.
