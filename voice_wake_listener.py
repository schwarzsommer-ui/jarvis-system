"""Local wake listener: two claps, then "Hey Jarvis", then a command.

Only the locally recognized voice command is sent to the local API. The
``voice_confirmed`` flag is intentionally limited to this wake-listener path;
typed dashboard commands still use the normal confirmation flow.
"""

from __future__ import annotations

import os
import socket
import sys
import time
from collections import deque

import numpy as np
import requests
import sounddevice as sd
import speech_recognition as sr

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None


API_URL = os.getenv("JARVIS_API_URL", "http://127.0.0.1:8787").rstrip("/")
SAMPLE_RATE = 16000
CLAP_WINDOW_SECONDS = 1.4
CLAP_COOLDOWN_SECONDS = 0.18
ENERGY_MULTIPLIER = float(os.getenv("JARVIS_CLAP_SENSITIVITY", "2.8"))
MIN_CLAP_PEAK = float(os.getenv("JARVIS_MIN_CLAP_PEAK", "900"))
MIN_CLAP_RMS = float(os.getenv("JARVIS_MIN_CLAP_RMS", "260"))
INSTANCE_PORT = int(os.getenv("JARVIS_WAKE_INSTANCE_PORT", "8799"))
VOICE_OUTPUT = os.getenv("JARVIS_VOICE_OUTPUT", "1") != "0"
INSTANCE_MUTEX = "Global\\JARVIS_VOICE_WAKE_LISTENER"


def speech_text(recognizer: sr.Recognizer, seconds: float) -> str:
    samples = sd.rec(
        int(SAMPLE_RATE * seconds),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    audio = sr.AudioData(samples.tobytes(), SAMPLE_RATE, 2)
    try:
        text = recognizer.recognize_google(audio, language="de-DE").strip()
        print(f"Sprache erkannt: {text}", flush=True)
        return text
    except (sr.UnknownValueError, sr.RequestError):
        print("Sprache nicht verstanden oder Spracherkennung nicht erreichbar.", flush=True)
        return ""


def is_clap(chunk: np.ndarray, ambient: float) -> bool:
    values = chunk.astype(np.float32)
    rms = float(np.sqrt(np.mean(np.square(values))))
    peak = float(np.max(np.abs(values)))
    return peak > max(ambient * ENERGY_MULTIPLIER, MIN_CLAP_PEAK) and rms > max(
        ambient * 1.35,
        MIN_CLAP_RMS,
    )


def speak(text: str) -> None:
    if not VOICE_OUTPUT or pyttsx3 is None or not text:
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.say(text)
        engine.runAndWait()
    except (RuntimeError, OSError) as exc:
        print(f"Sprachausgabe nicht verfügbar: {exc}", file=sys.stderr, flush=True)


def acquire_single_instance():
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.CreateMutexW(None, False, INSTANCE_MUTEX)
        if not handle:
            return None
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            return None
        return ("windows", handle)
    instance = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        instance.bind(("127.0.0.1", INSTANCE_PORT))
        instance.listen(1)
    except OSError:
        instance.close()
        return None
    return ("socket", instance)


def run() -> int:
    instance_lock = acquire_single_instance()
    if instance_lock is None:
        print("J.A.R.V.I.S. Wake Listener läuft bereits.")
        return 0
    recognizer = sr.Recognizer()
    clap_times: deque[float] = deque(maxlen=2)
    ambient = 180.0
    active = False
    last_clap = 0.0
    print(
        "J.A.R.V.I.S. Wake Listener: bereit "
        "(zweimal klatschen + Hey Jarvis)",
        flush=True,
    )
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=512,
    )
    stream.start()
    print(
        f"Mikrofon aktiv: Gerät {sd.default.device[0]}, "
        f"Schwellenwert Peak {MIN_CLAP_PEAK:g}",
        flush=True,
    )
    try:
        while True:
            data, _ = stream.read(512)
            chunk = np.asarray(data).reshape(-1)
            ambient = ambient * 0.995 + float(
                np.sqrt(np.mean(np.square(chunk.astype(np.float32))))
            ) * 0.005
            now = time.monotonic()

            if not active:
                if now - last_clap >= CLAP_COOLDOWN_SECONDS and is_clap(chunk, ambient):
                    clap_times.append(now)
                    last_clap = now
                while clap_times and now - clap_times[0] > CLAP_WINDOW_SECONDS:
                    clap_times.popleft()
                if len(clap_times) == 2:
                    clap_times.clear()
                    print("Zwei Klatscher erkannt. Warte auf Hey Jarvis …", flush=True)
                    speak("Ja?")
                    stream.stop()
                    phrase = speech_text(recognizer, 2.5).lower()
                    stream.start()
                    if "hey jarvis" in phrase or "hey, jarvis" in phrase:
                        active = True
                        print("J.A.R.V.I.S. aktiv.", flush=True)
                        speak("Ich höre.")
                    else:
                        print("Kein Wake-Word erkannt. Zurück im Standby.", flush=True)
                continue

            stream.stop()
            phrase = speech_text(recognizer, 8.0)
            stream.start()
            if not phrase:
                continue
            if phrase.lower() in {"jarvis aus", "hey jarvis aus"}:
                active = False
                print("J.A.R.V.I.S. im Standby.", flush=True)
                speak("Standby.")
                continue
            try:
                response = requests.post(
                    f"{API_URL}/plan/execute",
                    json={
                        "prompt": phrase,
                        "source": "voice",
                        "voice_confirmed": True,
                    },
                    timeout=90,
                )
                response.raise_for_status()
                result = response.json()
                if result.get("status") in {"needs_clarification", "rejected", "blocked"}:
                    response = requests.post(
                        f"{API_URL}/chat",
                        json={
                            "prompt": phrase,
                            "source": "voice",
                            "voice_confirmed": True,
                        },
                        timeout=90,
                    )
                    response.raise_for_status()
                    result = response.json()
                response_text = result.get(
                    "response",
                    result.get("message", "Auftrag verarbeitet."),
                )
                print(response_text, flush=True)
                speak(str(response_text))
            except requests.RequestException as exc:
                print(f"API nicht erreichbar: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        stream.close()
        if instance_lock[0] == "windows":
            import ctypes

            ctypes.windll.kernel32.CloseHandle(instance_lock[1])
        else:
            instance_lock[1].close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
