from __future__ import annotations

import time
from typing import Optional

import cv2

from audio_engine import AudioEngine
from gesture_controller import DJ_MODE, MELODY_MODE, PERCUSSION_MODE, GestureController
from hand_tracking import HandTracker
from looper import LoopEvent, Looper


DEFAULT_BPM = 110


def draw_hand_overlays(frame, hands: dict) -> None:
    for hand in hands.values():
        x1, y1, x2, y2 = hand.bbox
        color = (0, 220, 100) if hand.label == "Right" else (255, 160, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            f"{hand.label} open={hand.openness:.2f} fingers={hand.finger_count}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
        )


def draw_percussion_pads(frame) -> None:
    h, w = frame.shape[:2]
    pads = [
        ((0, 0), (w // 2, h // 2), "KICK"),
        ((w // 2, 0), (w, h // 2), "SNARE"),
        ((0, h // 2), (w // 2, h), "HI-HAT"),
        ((w // 2, h // 2), (w, h), "CLAP"),
    ]
    for (x1, y1), (x2, y2), name in pads:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 80, 80), 1)
        cv2.putText(frame, name, (x1 + 10, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)


def draw_dj_hud(frame, hud: dict) -> None:
    h, w = frame.shape[:2]
    panel_w = 220
    x0 = w - panel_w - 12
    y0 = 20
    cv2.rectangle(frame, (x0, y0), (x0 + panel_w, y0 + 246), (15, 15, 15), -1)
    cv2.rectangle(frame, (x0, y0), (x0 + panel_w, y0 + 246), (120, 120, 120), 1)

    filter_val = hud.get("filter", 0.0)
    volume_val = hud.get("volume", 0.8)
    reverb_val = hud.get("reverb", 0.1)
    buildup = hud.get("buildup_progress", 0.0)

    cv2.putText(frame, "DJ MODE", (x0 + 12, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(frame, f"Filter {filter_val:+.2f}", (x0 + 12, y0 + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    cv2.putText(frame, f"Volume {volume_val:.2f}", (x0 + 12, y0 + 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    cv2.putText(frame, f"Reverb {reverb_val:.2f}", (x0 + 12, y0 + 94), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

    bar_x = x0 + 12
    bar_y = y0 + 110
    bar_w = panel_w - 24
    bar_h = 18
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
    cv2.rectangle(
        frame,
        (bar_x, bar_y),
        (bar_x + int(bar_w * max(0.0, min(1.0, buildup))), bar_y + bar_h),
        (0, 180, 255),
        -1,
    )
    cv2.putText(frame, "Build-up", (bar_x, bar_y + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

    stutter = "ON" if hud.get("stutter", False) else "OFF"
    cv2.putText(frame, f"Stutter {stutter}", (x0 + 12, y0 + 170), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 220, 255), 1)
    cv2.putText(frame, f"BPM {hud.get('bpm', DEFAULT_BPM)}", (x0 + 12, y0 + 194), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 255, 150), 2)
    cv2.putText(frame, hud.get("dj_help_1", ""), (x0 + 12, y0 + 216), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1)
    cv2.putText(frame, hud.get("dj_help_2", ""), (x0 + 12, y0 + 232), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1)

    if hud.get("drop_flash", False):
        flash = frame.copy()
        cv2.rectangle(flash, (0, 0), (w, h), (255, 255, 255), -1)
        cv2.addWeighted(flash, 0.15, frame, 0.85, 0, frame)
        cv2.putText(frame, "DROP!", (w // 2 - 70, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4)


def draw_status(frame, mode: str, audio: AudioEngine, looper: Looper, note: Optional[int]) -> None:
    status = "REC" if looper.is_recording else "IDLE"
    loop_state = "ON" if looper.loop_enabled else "OFF"
    note_txt = "-" if note is None else str(note)
    cv2.putText(frame, f"Mode: {mode}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 0), 2)
    cv2.putText(frame, f"Instrument: {audio.current_instrument}", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 220), 2)
    cv2.putText(frame, f"Note: {note_txt}", (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (220, 220, 220), 1)
    cv2.putText(frame, f"Loop: {loop_state} | Record: {status} | Layers: {len(looper.layers)}", (12, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 180, 120), 1)
    cv2.putText(frame, "Q=quit C=clear +/- BPM  1/2/3 modos  I/O instrumento", (12, 126), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)


def draw_control_zones(frame, hud: dict) -> None:
    h, w = frame.shape[:2]
    top_h = int(h * 0.18)
    bot_h = int(h * 0.20)
    cv2.rectangle(frame, (0, 0), (w, top_h), (30, 60, 30), 1)
    cv2.rectangle(frame, (0, h - bot_h), (w, h), (60, 30, 30), 1)
    cv2.putText(frame, "MODE ZONE (esquerda no topo): 1 dedo=Melody 2=Percussion 3=DJ", (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 255, 120), 1)
    cv2.putText(frame, "INSTRUMENT ZONE (esquerda na base, mao aberta): segure na faixa X", (12, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 180, 180), 1)

    # Segmentar base em 6 instrumentos.
    for i in range(1, 6):
        x = int(w * i / 6)
        cv2.line(frame, (x, h - bot_h), (x, h), (90, 90, 90), 1)

    mode_target = hud.get("mode_target")
    mode_hold = hud.get("mode_hold")
    if mode_target is not None and mode_hold is not None:
        cv2.putText(frame, f"Mode -> {mode_target} ({mode_hold:.2f}s)", (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 255, 120), 2)

    inst_target = hud.get("inst_target")
    inst_hold = hud.get("inst_hold")
    if inst_target is not None and inst_hold is not None:
        cv2.putText(frame, f"Instrument slot {inst_target + 1} ({inst_hold:.2f}s)", (12, h - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 180, 180), 2)


def run_app() -> None:
    tracker = HandTracker()
    gesture = GestureController()
    audio = AudioEngine()
    looper = Looper(bpm=DEFAULT_BPM, quantize_division=4)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    if not cap.isOpened():
        print("Erro: webcam nao abriu.")
        return

    print("Gesture Music System iniciado.")
    print("Mantenha duas maos abertas para alternar MELODY/PERCUSSION/DJ.")

    current_note: Optional[int] = None

    def dispatch_live(action: dict, now_ts: float) -> None:
        nonlocal current_note
        t = action["type"]
        if t == "note_on":
            audio.note_on(action["note"], action.get("velocity", 100))
            current_note = action["note"]
            looper.record_event(now_ts, "note_on", {"note": action["note"], "velocity": action.get("velocity", 100)})
        elif t == "note_off":
            audio.note_off(action.get("note"))
            current_note = None
            looper.record_event(now_ts, "note_off", {"note": action.get("note")})
        elif t == "drum":
            audio.trigger_drum(action["name"], action.get("velocity", 115), now_ts)
            looper.record_event(now_ts, "drum", {"name": action["name"], "velocity": action.get("velocity", 115)})
        elif t == "instrument_next":
            audio.next_instrument()
        elif t == "instrument_index":
            audio.set_instrument_by_index(action["index"])
        elif t == "toggle_record":
            looper.toggle_recording(now_ts)
        elif t == "toggle_loop":
            looper.toggle_loop()
        elif t == "dj_params":
            audio.apply_dj_params(action["filter"], action["volume"], action["reverb"], action["delay"])
        elif t == "dj_drop":
            audio.trigger_drop(now_ts)
        elif t == "dj_kill_fx":
            audio.apply_dj_params(0.0, 0.9, 0.0, 0.0)
        elif t == "dj_stutter_toggle":
            audio.set_stutter(action.get("enabled", False))

    def dispatch_loop(ev: LoopEvent) -> None:
        if ev.event_type == "note_on":
            audio.note_on(ev.payload["note"], ev.payload.get("velocity", 100))
        elif ev.event_type == "note_off":
            audio.note_off(ev.payload.get("note"))
        elif ev.event_type == "drum":
            audio.trigger_drum(ev.payload["name"], ev.payload.get("velocity", 110))

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            now = time.perf_counter()

            hands = tracker.process(frame)
            out = gesture.process(hands, frame.shape, now, looper.bpm)
            looper.set_bpm(out.hud.get("bpm", looper.bpm))

            for action in out.actions:
                dispatch_live(action, now)

            looper.update(now, dispatch_loop)
            audio.tick(now, looper.bpm)

            draw_status(frame, out.mode, audio, looper, current_note)
            draw_hand_overlays(frame, hands)
            draw_control_zones(frame, out.hud)

            for hand in hands.values():
                h, w = frame.shape[:2]
                for lm in hand.landmarks:
                    x, y = int(lm.x * w), int(lm.y * h)
                    cv2.circle(frame, (x, y), 2, (0, 255, 255), -1)

            if out.mode == PERCUSSION_MODE:
                draw_percussion_pads(frame)
            if out.mode == DJ_MODE:
                draw_dj_hud(frame, out.hud)

            cv2.imshow("Gesture Music Studio", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                looper.clear()
            if key == ord("1"):
                gesture.force_mode(MELODY_MODE)
            if key == ord("2"):
                gesture.force_mode(PERCUSSION_MODE)
            if key == ord("3"):
                gesture.force_mode(DJ_MODE)
            if key in (ord("i"), ord("I")):
                audio.next_instrument()
            if key in (ord("o"), ord("O")):
                # volta instrumento anterior
                keys = list(audio.INSTRUMENTS.keys())
                idx = keys.index(audio.current_instrument)
                prev = (idx - 1) % len(keys)
                audio.set_instrument_by_index(prev)
            if key in (ord("+"), ord("=")):
                looper.set_bpm(looper.bpm + 2)
            if key == ord("-"):
                looper.set_bpm(looper.bpm - 2)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        audio.close()
        tracker.close()
        print("Encerrado.")


if __name__ == "__main__":
    run_app()
