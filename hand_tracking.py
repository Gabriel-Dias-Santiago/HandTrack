from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Dict, List, Tuple

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


@dataclass
class HandData:
    label: str
    landmarks: List
    wrist: Tuple[float, float]
    wrist_velocity: Tuple[float, float]
    openness: float
    finger_count: int
    depth: float
    bbox: Tuple[int, int, int, int]


class HandTracker:
    def __init__(
        self,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
        max_num_hands: int = 2,
    ) -> None:
        self.backend = "solutions" if hasattr(mp, "solutions") else "tasks"
        self.hands = None
        self.landmarker = None

        if self.backend == "solutions":
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                model_complexity=1,
            )
        else:
            model_path = Path("./models/hand_landmarker.task")
            if not model_path.exists():
                raise RuntimeError(
                    "MediaPipe sem 'solutions' detectado e modelo nao encontrado em "
                    f"'{model_path.resolve()}'.\n"
                    "Opcao 1: instalar mediapipe com 'solutions' (ex.: pip install mediapipe==0.10.14).\n"
                    "Opcao 2: baixar 'hand_landmarker.task' e salvar em ./models/."
                )
            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_hands=max_num_hands,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self.landmarker = vision.HandLandmarker.create_from_options(options)

        self._last_pos: Dict[str, Tuple[float, float]] = {}
        self._last_time: Dict[str, float] = {}

    def _count_fingers(self, landmarks: List, label: str) -> int:
        tips = [4, 8, 12, 16, 20]
        pips = [3, 6, 10, 14, 18]
        count = 0

        # Thumb uses x-axis relation because it bends differently.
        if label == "Right":
            if landmarks[tips[0]].x < landmarks[pips[0]].x:
                count += 1
        else:
            if landmarks[tips[0]].x > landmarks[pips[0]].x:
                count += 1

        for tip, pip in zip(tips[1:], pips[1:]):
            if landmarks[tip].y < landmarks[pip].y:
                count += 1
        return count

    def _openness(self, landmarks: List) -> float:
        wrist = np.array([landmarks[0].x, landmarks[0].y], dtype=np.float32)
        tip_ids = [4, 8, 12, 16, 20]
        dists = []
        for idx in tip_ids:
            tip = np.array([landmarks[idx].x, landmarks[idx].y], dtype=np.float32)
            dists.append(float(np.linalg.norm(tip - wrist)))
        return float(np.mean(dists))

    def process(self, frame_bgr) -> Dict[str, HandData]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = frame_bgr.shape[:2]
        now = time.perf_counter()
        hands: Dict[str, HandData] = {}

        if self.backend == "solutions":
            result = self.hands.process(rgb)
            if not result.multi_hand_landmarks or not result.multi_handedness:
                return hands
            iterable = []
            for hand_lms, handedness in zip(result.multi_hand_landmarks, result.multi_handedness):
                iterable.append((handedness.classification[0].label, hand_lms.landmark))
        else:
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self.landmarker.detect(image)
            if not result.hand_landmarks or not result.handedness:
                return hands
            iterable = []
            for idx, lm_list in enumerate(result.hand_landmarks):
                label = result.handedness[idx][0].category_name
                iterable.append((label, lm_list))

        for label, landmarks in iterable:
            xs = [lm.x for lm in landmarks]
            ys = [lm.y for lm in landmarks]
            min_x = int(max(0, min(xs) * w))
            max_x = int(min(w - 1, max(xs) * w))
            min_y = int(max(0, min(ys) * h))
            max_y = int(min(h - 1, max(ys) * h))
            wrist = (landmarks[0].x, landmarks[0].y)

            last = self._last_pos.get(label, wrist)
            last_t = self._last_time.get(label, now)
            dt = max(now - last_t, 1e-4)
            velocity = ((wrist[0] - last[0]) / dt, (wrist[1] - last[1]) / dt)
            self._last_pos[label] = wrist
            self._last_time[label] = now

            hands[label] = HandData(
                label=label,
                landmarks=landmarks,
                wrist=wrist,
                wrist_velocity=velocity,
                openness=self._openness(landmarks),
                finger_count=self._count_fingers(landmarks, label),
                depth=float(np.mean([lm.z for lm in landmarks])),
                bbox=(min_x, min_y, max_x, max_y),
            )

        return hands

    def close(self) -> None:
        if self.hands is not None:
            self.hands.close()
        if self.landmarker is not None and hasattr(self.landmarker, "close"):
            self.landmarker.close()
