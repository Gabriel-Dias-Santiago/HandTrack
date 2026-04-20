from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class LoopEvent:
    time_pos: float
    event_type: str
    payload: Dict


@dataclass
class LoopLayer:
    length: float
    events: List[LoopEvent] = field(default_factory=list)
    started_at: float = 0.0
    prev_phase: float = 0.0


class Looper:
    def __init__(self, bpm: int = 110, quantize_division: int = 4) -> None:
        self.bpm = bpm
        self.quantize_division = quantize_division
        self.is_recording = False
        self.loop_enabled = True
        self.record_start = 0.0
        self.record_events: List[LoopEvent] = []
        self.layers: List[LoopLayer] = []

    @property
    def beat_duration(self) -> float:
        return 60.0 / max(1, self.bpm)

    def _quantize(self, t: float) -> float:
        step = self.beat_duration / max(1, self.quantize_division)
        if step <= 0:
            return t
        return round(t / step) * step

    def set_bpm(self, bpm: int) -> None:
        self.bpm = max(40, min(220, bpm))

    def toggle_recording(self, now: float) -> bool:
        if self.is_recording:
            self.stop_recording(now)
        else:
            self.start_recording(now)
        return self.is_recording

    def start_recording(self, now: float) -> None:
        self.is_recording = True
        self.record_start = now
        self.record_events = []

    def stop_recording(self, now: float) -> None:
        self.is_recording = False
        length = max(1.0, now - self.record_start)
        if not self.record_events:
            return
        # Quantize the loop length to a whole beat.
        length = max(self.beat_duration, round(length / self.beat_duration) * self.beat_duration)
        layer = LoopLayer(length=length, events=self.record_events.copy(), started_at=now, prev_phase=0.0)
        self.layers.append(layer)

    def toggle_loop(self) -> bool:
        self.loop_enabled = not self.loop_enabled
        return self.loop_enabled

    def clear(self) -> None:
        self.layers.clear()
        self.record_events.clear()
        self.is_recording = False

    def record_event(self, now: float, event_type: str, payload: Dict) -> None:
        if not self.is_recording:
            return
        t = max(0.0, now - self.record_start)
        t = self._quantize(t)
        self.record_events.append(LoopEvent(time_pos=t, event_type=event_type, payload=payload.copy()))

    def _events_between(self, events: List[LoopEvent], prev_phase: float, phase: float, length: float) -> List[LoopEvent]:
        if phase >= prev_phase:
            return [ev for ev in events if prev_phase < ev.time_pos <= phase]
        wrapped = [ev for ev in events if ev.time_pos > prev_phase or ev.time_pos <= phase]
        return wrapped

    def update(self, now: float, dispatch: Callable[[LoopEvent], None]) -> None:
        if not self.loop_enabled:
            return
        for layer in self.layers:
            if layer.length <= 0:
                continue
            elapsed = now - layer.started_at
            phase = elapsed % layer.length
            due = self._events_between(layer.events, layer.prev_phase, phase, layer.length)
            layer.prev_phase = phase
            for ev in due:
                dispatch(ev)
