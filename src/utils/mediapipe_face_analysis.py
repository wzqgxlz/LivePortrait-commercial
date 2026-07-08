# coding: utf-8

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

try:
    import mediapipe as mp
except ModuleNotFoundError:  # pragma: no cover - exercised by runtime environments without deps
    mp = None

from .rprint import rlog as log

if mp is not None:
    mp_face_detection = mp.solutions.face_detection
else:
    mp_face_detection = None


@dataclass
class MediaPipeFace:
    bbox: np.ndarray
    kps: Optional[np.ndarray]
    det_score: float
    landmark_2d_106: np.ndarray

    def __getitem__(self, key):
        return getattr(self, key)


def sort_by_direction(faces: List[MediaPipeFace], direction: str = "large-small", face_center=None):
    if len(faces) <= 0:
        return faces

    if direction == "left-right":
        return sorted(faces, key=lambda face: face.bbox[0])
    if direction == "right-left":
        return sorted(faces, key=lambda face: face.bbox[0], reverse=True)
    if direction == "top-bottom":
        return sorted(faces, key=lambda face: face.bbox[1])
    if direction == "bottom-top":
        return sorted(faces, key=lambda face: face.bbox[1], reverse=True)
    if direction == "small-large":
        return sorted(faces, key=lambda face: _bbox_area(face.bbox))
    if direction == "large-small":
        return sorted(faces, key=lambda face: _bbox_area(face.bbox), reverse=True)
    if direction == "distance-from-retarget-face" and face_center is not None:
        return sorted(faces, key=lambda face: _distance_from_center(face.bbox, face_center))
    return faces


class MediaPipeFaceAnalysis:
    def __init__(self, model_selection: int = 1, min_detection_confidence: float = 0.5, **kwargs):
        self.model_selection = model_selection
        self.min_detection_confidence = min_detection_confidence
        self.det_thresh = min_detection_confidence
        self.detector = None

    def prepare(self, ctx_id=0, det_size=(512, 512), det_thresh=0.5):
        if mp_face_detection is None:
            raise ImportError(
                "mediapipe is required for commercial-safe face detection. "
                "Install it with `pip install mediapipe`."
            )
        self.det_thresh = det_thresh
        self.detector = mp_face_detection.FaceDetection(
            model_selection=self.model_selection,
            min_detection_confidence=det_thresh,
        )

    def warmup(self):
        if self.detector is None:
            self.prepare(det_thresh=self.det_thresh)
        img_bgr = np.zeros((512, 512, 3), dtype=np.uint8)
        self.get(img_bgr)
        log("MediaPipeFaceAnalysis warmup completed.")

    def get(self, img_bgr, **kwargs):
        if self.detector is None:
            self.prepare(det_thresh=self.det_thresh)

        max_num = kwargs.get("max_face_num", 0)
        direction = kwargs.get("direction", "large-small")

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        results = self.detector.process(img_rgb)
        detections = getattr(results, "detections", None) or []

        faces = []
        h, w = img_bgr.shape[:2]
        for detection in detections:
            score = float(detection.score[0]) if getattr(detection, "score", None) else 0.0
            if score < self.det_thresh:
                continue

            bbox = _bbox_from_detection(detection, w, h)
            kps = _keypoints_from_detection(detection, w, h)
            landmark_2d_106 = _landmark_106_from_bbox_and_keypoints(bbox, kps)
            faces.append(
                MediaPipeFace(
                    bbox=bbox,
                    kps=kps,
                    det_score=score,
                    landmark_2d_106=landmark_2d_106,
                )
            )

        faces = sort_by_direction(faces, direction)
        if max_num and max_num > 0:
            faces = faces[:max_num]
        return faces


def _bbox_from_detection(detection, width: int, height: int) -> np.ndarray:
    relative_bbox = detection.location_data.relative_bounding_box
    x1 = np.clip(relative_bbox.xmin * width, 0, width)
    y1 = np.clip(relative_bbox.ymin * height, 0, height)
    x2 = np.clip((relative_bbox.xmin + relative_bbox.width) * width, 0, width)
    y2 = np.clip((relative_bbox.ymin + relative_bbox.height) * height, 0, height)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def _keypoints_from_detection(detection, width: int, height: int) -> Optional[np.ndarray]:
    relative_keypoints = getattr(detection.location_data, "relative_keypoints", None)
    if not relative_keypoints:
        return None
    return np.array([[point.x * width, point.y * height] for point in relative_keypoints], dtype=np.float32)


def _landmark_106_from_bbox_and_keypoints(bbox: np.ndarray, kps: Optional[np.ndarray]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    width = max(float(x2 - x1), 1.0)
    height = max(float(y2 - y1), 1.0)
    center_x = float(x1 + width * 0.5)
    center_y = float(y1 + height * 0.54)

    angles = np.linspace(np.pi, -np.pi, 64, endpoint=False)
    oval = np.column_stack(
        [
            center_x + np.cos(angles) * width * 0.48,
            center_y + np.sin(angles) * height * 0.55,
        ]
    )

    if kps is not None and len(kps) >= 6:
        right_eye, left_eye, nose, mouth, right_ear, left_ear = kps[:6]
    else:
        right_eye = np.array([x1 + width * 0.35, y1 + height * 0.40], dtype=np.float32)
        left_eye = np.array([x1 + width * 0.65, y1 + height * 0.40], dtype=np.float32)
        nose = np.array([x1 + width * 0.50, y1 + height * 0.55], dtype=np.float32)
        mouth = np.array([x1 + width * 0.50, y1 + height * 0.74], dtype=np.float32)
        right_ear = np.array([x1 + width * 0.18, y1 + height * 0.55], dtype=np.float32)
        left_ear = np.array([x1 + width * 0.82, y1 + height * 0.55], dtype=np.float32)

    feature_points = np.vstack(
        [
            _ellipse_points(right_eye, width * 0.07, height * 0.035, 8),
            _ellipse_points(left_eye, width * 0.07, height * 0.035, 8),
            _line_points(right_ear, nose, 5),
            _line_points(nose, left_ear, 5),
            _ellipse_points(mouth, width * 0.13, height * 0.04, 10),
            _line_points(nose, mouth, 6),
        ]
    )

    landmarks = np.vstack([oval, feature_points])
    if landmarks.shape[0] < 106:
        padding = np.repeat(mouth.reshape(1, 2), 106 - landmarks.shape[0], axis=0)
        landmarks = np.vstack([landmarks, padding])
    return landmarks[:106].astype(np.float32)


def _ellipse_points(center, radius_x: float, radius_y: float, count: int) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, count, endpoint=False)
    return np.column_stack([center[0] + np.cos(angles) * radius_x, center[1] + np.sin(angles) * radius_y])


def _line_points(start, end, count: int) -> np.ndarray:
    return np.linspace(start, end, count, dtype=np.float32)


def _bbox_area(bbox: np.ndarray) -> float:
    return float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))


def _distance_from_center(bbox: np.ndarray, face_center) -> float:
    center_x = (bbox[2] + bbox[0]) / 2
    center_y = (bbox[3] + bbox[1]) / 2
    return float(((center_x - face_center[0]) ** 2 + (center_y - face_center[1]) ** 2) ** 0.5)
