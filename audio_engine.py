from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Dict, List, Optional, Tuple

import pygame.midi


@dataclass
class ScheduledEvent:
    trigger_at: float
    event_type: str
    payload: Dict


class AudioEngine:
    """MIDI engine with low-latency note triggering and live FX via MIDI CC."""

    DRUM_NOTES = {
        "kick": 36,
        "snare": 38,
        "hihat_closed": 42,
        "hihat_open": 46,
        "clap": 39,
        "tom": 45,
    }
    DRUM_GAIN = {
        "kick": 1.25,
        "snare": 1.2,
        "hihat_closed": 1.35,
        "hihat_open": 1.25,
        "clap": 1.2,
        "tom": 1.15,
    }

    INSTRUMENTS = {
        "Piano": 0,
        "EPiano": 4,
        "Organ": 19,
        "SynthLead": 80,
        "Pad": 88,
        "Bass": 32,
    }

    def __init__(self) -> None:
        pygame.midi.init()
        self.output = None
        self.channel = 0
        self.drum_channel = 9
        self.current_instrument = "Piano"
        self.current_note: Optional[int] = None
        self.current_velocity = 100
        self.last_note_for_stutter: Optional[int] = None
        self.last_stutter_time = 0.0
        self.stutter_enabled = False
        self.pending: List[ScheduledEvent] = []

        default_id = pygame.midi.get_default_output_id()
        if default_id >= 0:
            self.output = pygame.midi.Output(default_id, latency=0)
        elif pygame.midi.get_count() > 0:
            self.output = pygame.midi.Output(0, latency=0)

        if self.output:
            self.set_instrument(self.current_instrument)
            # Keep melodic channel slightly lower so drums stand out more.
            self._cc(7, 96, channel=self.channel)
            # Keep drum channel louder by default.
            self._cc(7, 127, channel=self.drum_channel)
            self._cc(11, 127, channel=self.drum_channel)

    @property
    def available(self) -> bool:
        return self.output is not None

    def _cc(self, cc_num: int, value: int, channel: Optional[int] = None) -> None:
        if self.output:
            ch = self.channel if channel is None else channel
            self.output.write_short(0xB0 | ch, cc_num, max(0, min(127, value)))

    def set_instrument(self, name: str) -> None:
        if name not in self.INSTRUMENTS:
            return
        self.current_instrument = name
        if self.output:
            self.output.set_instrument(self.INSTRUMENTS[name], self.channel)

    def next_instrument(self) -> str:
        keys = list(self.INSTRUMENTS.keys())
        idx = keys.index(self.current_instrument)
        new_name = keys[(idx + 1) % len(keys)]
        self.set_instrument(new_name)
        return new_name

    def set_instrument_by_index(self, idx: int) -> str:
        keys = list(self.INSTRUMENTS.keys())
        idx = max(0, min(len(keys) - 1, idx))
        self.set_instrument(keys[idx])
        return keys[idx]

    def note_on(self, midi_note: int, velocity: int = 100) -> None:
        velocity = max(1, min(127, velocity))
        self.current_note = midi_note
        self.current_velocity = velocity
        self.last_note_for_stutter = midi_note
        if self.output:
            self.output.note_on(midi_note, velocity, self.channel)

    def note_off(self, midi_note: Optional[int] = None) -> None:
        note = self.current_note if midi_note is None else midi_note
        if note is None:
            return
        if self.output:
            self.output.note_off(note, 0, self.channel)
        if midi_note is None:
            self.current_note = None

    def all_notes_off(self) -> None:
        if self.output:
            self._cc(123, 0)
        self.current_note = None

    def trigger_drum(self, name: str, velocity: int = 115, now: Optional[float] = None) -> None:
        note = self.DRUM_NOTES.get(name)
        if note is None:
            return
        if self.output:
            gain = self.DRUM_GAIN.get(name, 1.0)
            vel = int(max(1, min(127, velocity * gain)))
            vel = max(100, vel)
            self.output.note_on(note, vel, self.drum_channel)
            # Important: do not cut drums immediately; short hold improves audibility a lot.
            t0 = time.perf_counter() if now is None else now
            self.pending.append(ScheduledEvent(t0 + 0.055, "drum_off", {"note": note}))

    def apply_dj_params(self, filter_amount: float, volume: float, reverb: float, delay: float) -> None:
        """
        Applies DJ controls with MIDI CC:
        - CC74 filter/cutoff
        - CC7 channel volume
        - CC91 reverb send
        - CC94 delay send
        """
        filter_val = int((filter_amount + 1.0) * 63.5)  # -1..1 -> 0..127
        vol_val = int(max(0.0, min(1.0, volume)) * 127)
        rev_val = int(max(0.0, min(1.0, reverb)) * 127)
        del_val = int(max(0.0, min(1.0, delay)) * 127)
        self._cc(74, filter_val)
        self._cc(7, vol_val)
        self._cc(91, rev_val)
        self._cc(94, del_val)

    def trigger_drop(self, now: float) -> None:
        self.all_notes_off()
        self.pending.append(ScheduledEvent(now + 0.12, "drop_impact", {}))

    def set_stutter(self, enabled: bool) -> None:
        self.stutter_enabled = enabled

    def tick(self, now: float, bpm: int) -> None:
        due: List[ScheduledEvent] = []
        future: List[ScheduledEvent] = []
        for ev in self.pending:
            if ev.trigger_at <= now:
                due.append(ev)
            else:
                future.append(ev)
        self.pending = future

        for ev in due:
            if ev.event_type == "drop_impact":
                self.trigger_drum("kick", velocity=127)
                self.note_on(36, 120)
                self.pending.append(ScheduledEvent(now + 0.08, "drop_off", {"note": 36}))
            elif ev.event_type == "drop_off":
                self.note_off(ev.payload["note"])
            elif ev.event_type == "drum_off":
                if self.output:
                    self.output.note_off(ev.payload["note"], 0, self.drum_channel)

        if self.stutter_enabled and self.last_note_for_stutter is not None:
            step = max(0.04, 60.0 / max(40, bpm) / 4.0)
            if now - self.last_stutter_time >= step:
                self.last_stutter_time = now
                self.note_on(self.last_note_for_stutter, self.current_velocity)
                self.note_off(self.last_note_for_stutter)

    def close(self) -> None:
        if self.output:
            self.all_notes_off()
            self.output.close()
            self.output = None
        pygame.midi.quit()
