from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from hand_tracking import HandData


@dataclass
class DJState:
    filter_amount: float = 0.0
    volume: float = 0.85
    reverb: float = 0.15
    delay: float = 0.12
    buildup_active: bool = False
    buildup_progress: float = 0.0
    drop_flash_until: float = 0.0
    stutter_enabled: bool = False


class DJController:
    """
    DJ mode simplified for live performance:
    - Right hand: continuous controls (filter + volume)
    - Left hand: discrete triggers by finger count with hold
    """

    def __init__(self) -> None:
        self.state = DJState()
        self._build_start = 0.0
        self._build_length = 3.0
        self._next_roll = 0.0
        self._last_drop = 0.0
        self._gesture_candidate: Optional[str] = None
        self._gesture_since: Optional[float] = None

    def _is_closed(self, hand: HandData) -> bool:
        return hand.openness < 0.31 or hand.finger_count <= 1

    def _stable(self, hand: HandData, limit: float = 0.23) -> bool:
        return abs(hand.wrist_velocity[0]) < limit and abs(hand.wrist_velocity[1]) < limit

    def _set_candidate(self, action_id: Optional[str], now: float) -> float:
        if action_id is None:
            self._gesture_candidate = None
            self._gesture_since = None
            return 0.0
        if self._gesture_candidate != action_id:
            self._gesture_candidate = action_id
            self._gesture_since = now
            return 0.0
        if self._gesture_since is None:
            self._gesture_since = now
            return 0.0
        return now - self._gesture_since

    def process(
        self,
        left: Optional[HandData],
        right: Optional[HandData],
        now: float,
        base_bpm: int,
    ) -> tuple[List[Dict], Dict]:
        actions: List[Dict] = []

        # Right hand: smooth and predictable parameters.
        if right is not None:
            # y: bottom (-1 low-pass feeling), top (+1 high-pass feeling)
            self.state.filter_amount = max(-1.0, min(1.0, (1.0 - right.wrist[1]) * 2.0 - 1.0))
            # x: left low, right high volume with minimum floor.
            self.state.volume = max(0.5, min(1.0, 0.5 + right.wrist[0] * 0.5))
            # depth only for ambience, limited range for stability.
            depth_norm = max(0.0, min(1.0, (0.08 - right.depth) / 0.42))
            self.state.reverb = 0.08 + 0.35 * depth_norm
            self.state.delay = 0.06 + 0.25 * depth_norm
            actions.append(
                {
                    "type": "dj_params",
                    "filter": self.state.filter_amount,
                    "volume": self.state.volume,
                    "reverb": self.state.reverb,
                    "delay": self.state.delay,
                }
            )

        # Left hand triggers (simple set):
        # 1 finger hold: toggle buildup
        # 2 fingers hold: toggle stutter
        # fist pulse: drop
        # open still 0.8s: kill FX
        if left is not None:
            trigger_id: Optional[str] = None
            if self._is_closed(left):
                trigger_id = "drop"
            elif left.finger_count == 1 and self._stable(left):
                trigger_id = "buildup"
            elif left.finger_count == 2 and self._stable(left):
                trigger_id = "stutter"
            elif left.finger_count >= 4 and self._stable(left):
                trigger_id = "kill_fx"

            hold = self._set_candidate(trigger_id, now)
            if trigger_id == "drop" and hold >= 0.1 and now - self._last_drop > 0.9:
                actions.append({"type": "dj_drop"})
                self.state.drop_flash_until = now + 0.25
                self._last_drop = now
                self.state.buildup_active = False
                self.state.buildup_progress = 0.0
                self._gesture_candidate = None
                self._gesture_since = None
            elif trigger_id == "buildup" and hold >= 0.45:
                self.state.buildup_active = not self.state.buildup_active
                if self.state.buildup_active:
                    self._build_start = now
                    self._next_roll = now
                else:
                    self.state.buildup_progress = 0.0
                self._gesture_candidate = None
                self._gesture_since = None
            elif trigger_id == "stutter" and hold >= 0.45:
                self.state.stutter_enabled = not self.state.stutter_enabled
                actions.append({"type": "dj_stutter_toggle", "enabled": self.state.stutter_enabled})
                self._gesture_candidate = None
                self._gesture_since = None
            elif trigger_id == "kill_fx" and hold >= 0.8:
                actions.append({"type": "dj_kill_fx"})
                self._gesture_candidate = None
                self._gesture_since = None

        bpm_scale = 1.0
        if self.state.buildup_active:
            p = max(0.0, min(1.0, (now - self._build_start) / self._build_length))
            self.state.buildup_progress = p
            bpm_scale = 1.0 + (0.22 * p)
            if now >= self._next_roll:
                actions.append({"type": "drum", "name": "snare", "velocity": int(95 + 30 * p)})
                self._next_roll = now + max(0.055, 0.22 - 0.16 * p)

        bpm = int(base_bpm * bpm_scale)
        hud = {
            "filter": self.state.filter_amount,
            "volume": self.state.volume,
            "reverb": self.state.reverb,
            "delay": self.state.delay,
            "buildup_progress": self.state.buildup_progress,
            "drop_flash": now <= self.state.drop_flash_until,
            "stutter": self.state.stutter_enabled,
            "bpm": bpm,
            "dj_help_1": "Esq: 1 dedo build | 2 dedos stutter",
            "dj_help_2": "Punho drop | mao aberta parada kill FX",
        }
        return actions, hud
