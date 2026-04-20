from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from dj_controller import DJController
from hand_tracking import HandData


MELODY_MODE = "MELODY"
PERCUSSION_MODE = "PERCUSSION"
DJ_MODE = "DJ"
ALL_MODES = [MELODY_MODE, PERCUSSION_MODE, DJ_MODE]


@dataclass
class GestureOutput:
    actions: List[Dict] = field(default_factory=list)
    mode: str = MELODY_MODE
    hud: Dict = field(default_factory=dict)


class GestureController:
    def __init__(self) -> None:
        self.mode = MELODY_MODE
        self.note_active = False
        self.note_value: Optional[int] = None
        self.left_was_closed = False
        self.last_drum_tap = 0.0
        self.last_loop_gesture = 0.0
        self.path: List[Tuple[float, float]] = []
        self.path_t: List[float] = []
        self.right_smooth = (0.5, 0.5)
        self.note_candidate: Optional[int] = None
        self.note_candidate_since: Optional[float] = None
        self.mode_candidate: Optional[str] = None
        self.mode_candidate_since: Optional[float] = None
        self.instrument_candidate: Optional[int] = None
        self.instrument_candidate_since: Optional[float] = None
        self.last_instrument_change = 0.0
        self.dj = DJController()

    def _is_open(self, hand: HandData) -> bool:
        return hand.openness > 0.43 and hand.finger_count >= 4

    def _is_closed(self, hand: HandData) -> bool:
        return hand.openness < 0.31 or hand.finger_count <= 1

    def _cycle_mode(self) -> str:
        idx = ALL_MODES.index(self.mode)
        self.mode = ALL_MODES[(idx + 1) % len(ALL_MODES)]
        return self.mode

    def force_mode(self, mode: str) -> None:
        if mode in ALL_MODES:
            self.mode = mode

    def _pinch_distance(self, hand: HandData) -> float:
        thumb = hand.landmarks[4]
        index = hand.landmarks[8]
        dx = thumb.x - index.x
        dy = thumb.y - index.y
        return (dx * dx + dy * dy) ** 0.5

    def _is_pinch(self, hand: HandData) -> bool:
        # Mais estável que "mão fechada" para tocar nota.
        return self._pinch_distance(hand) < 0.055

    def _compute_melody_note(self, right: HandData) -> Tuple[int, int]:
        # Pentatônica maior para soar musical e reduzir notas "feias".
        scale = [0, 2, 4, 7, 9]
        # Suaviza posição para reduzir tremulação.
        alpha = 0.18
        sx = self.right_smooth[0] * (1.0 - alpha) + right.wrist[0] * alpha
        sy = self.right_smooth[1] * (1.0 - alpha) + right.wrist[1] * alpha
        self.right_smooth = (sx, sy)

        octave = int(max(3, min(5, round(3 + sx * 2))))
        degree = int(max(0, min(len(scale) - 1, round((1.0 - sy) * (len(scale) - 1)))))
        note = 12 * (octave + 1) + scale[degree]
        velocity = int(max(55, min(127, 85 + (0.5 - sy) * 40)))
        return note, velocity

    def _is_circle(self) -> bool:
        if len(self.path) < 10:
            return False
        path_len = 0.0
        for i in range(1, len(self.path)):
            dx = self.path[i][0] - self.path[i - 1][0]
            dy = self.path[i][1] - self.path[i - 1][1]
            path_len += (dx * dx + dy * dy) ** 0.5
        start = self.path[0]
        end = self.path[-1]
        disp = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        return path_len > 0.32 and disp < 0.1 and (path_len / max(disp, 1e-4)) > 3.0

    def _update_mode_by_zone(self, left: Optional[HandData], now: float, out: GestureOutput) -> None:
        """
        Zona superior (y < 0.30), mão esquerda estável:
        - 1 dedo -> MELODY
        - 2 dedos -> PERCUSSION
        - 3 dedos -> DJ
        """
        if left is None:
            self.mode_candidate = None
            self.mode_candidate_since = None
            return

        stable = abs(left.wrist_velocity[0]) < 0.2 and abs(left.wrist_velocity[1]) < 0.2
        if not (stable and left.wrist[1] < 0.30):
            self.mode_candidate = None
            self.mode_candidate_since = None
            return

        target = None
        if left.finger_count == 1:
            target = MELODY_MODE
        elif left.finger_count == 2:
            target = PERCUSSION_MODE
        elif left.finger_count == 3:
            target = DJ_MODE

        out.hud["mode_zone_hint"] = "Topo: 1=Melody 2=Perc 3=DJ"

        if target is None:
            self.mode_candidate = None
            self.mode_candidate_since = None
            return

        if self.mode_candidate != target:
            self.mode_candidate = target
            self.mode_candidate_since = now
            return

        hold = now - (self.mode_candidate_since or now)
        out.hud["mode_hold"] = round(hold, 2)
        out.hud["mode_target"] = target
        if hold >= 0.55 and target != self.mode:
            self.mode = target
            out.actions.append({"type": "mode_changed", "mode": target})
            self.mode_candidate = None
            self.mode_candidate_since = None

    def _update_instrument_by_zone(self, left: Optional[HandData], now: float, out: GestureOutput) -> None:
        """
        Zona inferior (y > 0.72), mão esquerda aberta e estável:
        seleção por posição X em 6 faixas de instrumentos.
        """
        if left is None:
            self.instrument_candidate = None
            self.instrument_candidate_since = None
            return

        stable = abs(left.wrist_velocity[0]) < 0.18 and abs(left.wrist_velocity[1]) < 0.18
        valid_pose = left.wrist[1] > 0.72 and left.finger_count >= 3 and stable
        if not valid_pose:
            self.instrument_candidate = None
            self.instrument_candidate_since = None
            return

        idx = int(max(0, min(5, left.wrist[0] * 6)))
        out.hud["inst_zone_hint"] = "Base: segure p/ trocar instrumento"
        out.hud["inst_target"] = idx
        if self.instrument_candidate != idx:
            self.instrument_candidate = idx
            self.instrument_candidate_since = now
            return

        hold = now - (self.instrument_candidate_since or now)
        out.hud["inst_hold"] = round(hold, 2)
        if hold >= 0.45 and now - self.last_instrument_change > 0.9:
            out.actions.append({"type": "instrument_index", "index": idx})
            self.last_instrument_change = now
            self.instrument_candidate = None
            self.instrument_candidate_since = None

    def _left_control_actions(self, left: HandData, now: float, out: GestureOutput) -> None:
        closed = self._is_closed(left)
        if closed and not self.left_was_closed:
            out.actions.append({"type": "toggle_record"})
        self.left_was_closed = closed

        if self._is_circle() and now - self.last_loop_gesture > 1.2:
            out.actions.append({"type": "toggle_loop"})
            self.last_loop_gesture = now

    def _melody_actions(self, right: HandData, now: float, out: GestureOutput) -> None:
        note, velocity = self._compute_melody_note(right)
        pinched = self._is_pinch(right)

        if pinched and not self.note_active:
            out.actions.append({"type": "note_on", "note": note, "velocity": velocity})
            self.note_active = True
            self.note_value = note
            self.note_candidate = None
            self.note_candidate_since = None
        elif pinched and self.note_active and note != self.note_value:
            if self.note_candidate != note:
                self.note_candidate = note
                self.note_candidate_since = now
            # delay breve para evitar troca nervosa de nota
            if self.note_candidate == note and self.note_candidate_since is not None and now - self.note_candidate_since >= 0.12:
                out.actions.append({"type": "note_off", "note": self.note_value})
                out.actions.append({"type": "note_on", "note": note, "velocity": velocity})
                self.note_value = note
                self.note_candidate = None
                self.note_candidate_since = None
        elif not pinched and self.note_active:
            out.actions.append({"type": "note_off", "note": self.note_value})
            self.note_active = False
            self.note_value = None
            self.note_candidate = None
            self.note_candidate_since = None

        out.hud["current_note"] = note
        out.hud["right_state"] = "PINCH" if pinched else "OPEN"

    def _percussion_actions(self, right: HandData, frame_w: int, frame_h: int, now: float, out: GestureOutput) -> None:
        _, vy = right.wrist_velocity
        x_px = int(right.wrist[0] * frame_w)
        y_px = int(right.wrist[1] * frame_h)
        tap = vy > 0.62 and now - self.last_drum_tap > 0.14
        if not tap:
            return

        self.last_drum_tap = now
        top = y_px < frame_h // 2
        left = x_px < frame_w // 2

        if top and left:
            drum = "kick"
        elif top and not left:
            drum = "snare"
        elif not top and left:
            drum = "hihat_closed"
        else:
            drum = "clap"
        velocity = int(max(70, min(127, 70 + abs(vy) * 25)))
        out.actions.append({"type": "drum", "name": drum, "velocity": velocity})
        out.hud["last_drum"] = drum
        out.hud["tap_velocity"] = round(vy, 2)

    def process(self, hands: Dict[str, HandData], frame_shape, now: float, bpm: int) -> GestureOutput:
        out = GestureOutput(mode=self.mode)
        frame_h, frame_w = frame_shape[:2]
        left = hands.get("Left")
        right = hands.get("Right")

        if left:
            self.path.append(left.wrist)
            self.path_t.append(now)
            while self.path_t and now - self.path_t[0] > 1.0:
                self.path_t.pop(0)
                self.path.pop(0)

        self._update_mode_by_zone(left, now, out)
        self._update_instrument_by_zone(left, now, out)

        if self.mode == DJ_MODE:
            dj_actions, dj_hud = self.dj.process(left, right, now, bpm)
            out.actions.extend(dj_actions)
            out.hud.update(dj_hud)
            out.mode = self.mode
            return out

        if left:
            self._left_control_actions(left, now, out)
        if right:
            if self.mode == MELODY_MODE:
                self._melody_actions(right, now, out)
            elif self.mode == PERCUSSION_MODE:
                self._percussion_actions(right, frame_w, frame_h, now, out)

        out.mode = self.mode
        return out
