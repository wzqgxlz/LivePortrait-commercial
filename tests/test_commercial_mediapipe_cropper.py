import importlib
import sys
import types

import numpy as np


def test_cropper_import_does_not_load_insightface_modules():
    sys.modules.pop("src.utils.cropper", None)
    _install_lightweight_runtime_stubs()

    cropper_module = importlib.import_module("src.utils.cropper")

    assert hasattr(cropper_module, "MediaPipeFaceAnalysis")
    assert "src.utils.face_analysis_diy" not in sys.modules
    assert not any(".dependencies.insightface" in name for name in sys.modules)


def test_crop_config_no_longer_exposes_legacy_detector_root():
    from src.config.crop_config import CropConfig

    legacy_root_attr = "insight" + "face_root"
    assert not hasattr(CropConfig(), legacy_root_attr)


def test_mediapipe_adapter_sorts_and_limits_detected_faces(monkeypatch):
    _install_lightweight_runtime_stubs()
    mediapipe_module = importlib.import_module("src.utils.mediapipe_face_analysis")
    MediaPipeFaceAnalysis = mediapipe_module.MediaPipeFaceAnalysis

    detections = [
        _fake_detection(0.10, 0.10, 0.20, 0.20, 0.70),
        _fake_detection(0.30, 0.25, 0.50, 0.55, 0.90),
        _fake_detection(0.02, 0.20, 0.10, 0.30, 0.80),
    ]

    monkeypatch.setattr(mediapipe_module, "mp_face_detection", types.SimpleNamespace(
        FaceDetection=
        lambda **kwargs: _FakeFaceDetection(detections),
    ))

    detector = MediaPipeFaceAnalysis()
    detector.prepare(ctx_id=0, det_size=(512, 512), det_thresh=0.5)
    faces = detector.get(np.zeros((100, 200, 3), dtype=np.uint8), direction="large-small", max_face_num=2)

    assert len(faces) == 2
    assert np.allclose(faces[0].bbox, np.array([60.0, 25.0, 160.0, 80.0], dtype=np.float32))
    assert faces[0].landmark_2d_106.shape == (106, 2)
    assert faces[0].det_score == 0.90
    assert np.allclose(faces[1].bbox, np.array([20.0, 10.0, 60.0, 30.0], dtype=np.float32))


def test_mediapipe_adapter_imports_with_tasks_only_runtime(monkeypatch):
    sys.modules.pop("src.utils.mediapipe_face_analysis", None)
    _install_lightweight_runtime_stubs()
    sys.modules["mediapipe"] = types.SimpleNamespace(
        Image=object,
        ImageFormat=types.SimpleNamespace(SRGB="SRGB"),
        tasks=types.SimpleNamespace(),
    )

    mediapipe_module = importlib.import_module("src.utils.mediapipe_face_analysis")

    assert mediapipe_module.mp_face_detection is None


def test_mediapipe_adapter_reads_tasks_detection_score(monkeypatch):
    _install_lightweight_runtime_stubs()
    mediapipe_module = importlib.import_module("src.utils.mediapipe_face_analysis")
    detection = types.SimpleNamespace(
        categories=[types.SimpleNamespace(score=0.87)],
    )

    assert mediapipe_module._score_from_detection(detection) == 0.87


def test_cropper_uses_crop_config_force_cpu_for_landmark_runner(monkeypatch):
    sys.modules.pop("src.utils.cropper", None)
    _install_lightweight_runtime_stubs()
    cropper_module = importlib.import_module("src.utils.cropper")
    providers = []

    class FakeFaceAnalysis:
        def prepare(self, **kwargs):
            pass

        def warmup(self):
            pass

    class FakeHumanLandmark:
        def __init__(self, **kwargs):
            providers.append(kwargs["onnx_provider"])

        def warmup(self):
            pass

    monkeypatch.setattr(cropper_module, "MediaPipeFaceAnalysis", FakeFaceAnalysis)
    monkeypatch.setattr(cropper_module, "HumanLandmark", FakeHumanLandmark)
    from src.config.crop_config import CropConfig

    cfg = CropConfig(flag_force_cpu=True)
    cropper_module.Cropper(crop_cfg=cfg)

    assert providers == ["cpu"]


def _fake_detection(xmin, ymin, width, height, score):
    relative_bounding_box = types.SimpleNamespace(
        xmin=xmin,
        ymin=ymin,
        width=width,
        height=height,
    )
    location_data = types.SimpleNamespace(
        relative_bounding_box=relative_bounding_box,
        relative_keypoints=[
            types.SimpleNamespace(x=xmin + width * 0.30, y=ymin + height * 0.40),
            types.SimpleNamespace(x=xmin + width * 0.70, y=ymin + height * 0.40),
            types.SimpleNamespace(x=xmin + width * 0.50, y=ymin + height * 0.55),
            types.SimpleNamespace(x=xmin + width * 0.50, y=ymin + height * 0.75),
            types.SimpleNamespace(x=xmin + width * 0.20, y=ymin + height * 0.60),
            types.SimpleNamespace(x=xmin + width * 0.80, y=ymin + height * 0.60),
        ],
    )
    return types.SimpleNamespace(location_data=location_data, score=[score])


class _FakeFaceDetection:
    def __init__(self, detections):
        self._detections = detections

    def process(self, image):
        return types.SimpleNamespace(detections=self._detections)


def _install_lightweight_runtime_stubs():
    sys.modules["torch"] = types.SimpleNamespace(
        Tensor=type("Tensor", (), {}),
        backends=types.SimpleNamespace(
            mps=types.SimpleNamespace(is_available=lambda: False)
        )
    )
    sys.modules["cv2"] = types.SimpleNamespace(
        COLOR_BGR2RGB=4,
        COLOR_RGB2BGR=4,
        INTER_AREA=3,
        INTER_LINEAR=1,
        ocl=types.SimpleNamespace(setUseOpenCL=lambda enabled: None),
        setNumThreads=lambda count: None,
        cvtColor=lambda image, code: image[..., ::-1],
        resize=lambda image, size, interpolation=None: np.zeros((size[1], size[0], image.shape[2]), dtype=image.dtype),
    )
    sys.modules["PIL"] = types.SimpleNamespace(Image=types.SimpleNamespace(fromarray=lambda image: image))
    sys.modules["PIL.Image"] = types.SimpleNamespace(fromarray=lambda image: image)
    sys.modules["imageio"] = types.SimpleNamespace(get_reader=lambda *args, **kwargs: None)
    sys.modules["onnxruntime"] = types.SimpleNamespace(
        SessionOptions=lambda: types.SimpleNamespace(intra_op_num_threads=0),
        InferenceSession=lambda *args, **kwargs: types.SimpleNamespace(run=lambda *run_args, **run_kwargs: []),
    )
    sys.modules["src.utils.io"] = types.SimpleNamespace(
        contiguous=lambda obj: obj if obj.flags.c_contiguous else obj.copy(order="C")
    )
