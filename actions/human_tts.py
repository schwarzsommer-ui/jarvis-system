import os
import sys
import subprocess
import asyncio
import tempfile
import speech_recognition as sr
import threading
import wave
from pathlib import Path
from core.audio_devices import AudioDeviceManager

PIPER_MODEL = Path(__file__).resolve().parents[1] / "models" / "voices" / "de_DE-thorsten-medium.onnx"
PIPER_CONFIG = PIPER_MODEL.with_suffix(".onnx.json")

def install_if_missing(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installiere {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

def speak(text: str, voice: str = "de-DE-KillianNeural", generation=None):
    """
    Generiert menschliche deutsche Sprachausgabe mit Microsoft Edge TTS (hohe Qualität).
    Mögliche Stimmen:
    - de-DE-KillianNeural (männlich, sehr natürlich)
    - de-DE-KatjaNeural (weiblich, sehr natürlich)
    - de-DE-ConradNeural (männlich, tief)
    """
    if not text.strip():
        return
    if generation is None:
        with _speech_state_lock:
            generation = _speech_generation

    if PIPER_MODEL.is_file() and PIPER_CONFIG.is_file():
        try:
            _speak_with_piper(text, generation)
            return
        except Exception as piper_error:
            print(f"Piper-Stimme nicht verfügbar, verwende Online-Fallback: {piper_error}")

    try:
        install_if_missing("edge-tts", "edge_tts")
        install_if_missing("pygame")
        import edge_tts
        import pygame

        async def _async_speak():
            file_path = os.path.join(tempfile.gettempdir(), "jarvis_voice_output.mp3")
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate="+15%",
                pitch="-2Hz",
                volume="+0%",
            )
            await communicate.save(file_path)
            pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not _speech_was_cancelled(generation):
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()

        with _speech_lock:
            if _speech_was_cancelled(generation):
                return
            asyncio.run(_async_speak())
    except Exception as edge_error:
        if _speech_was_cancelled(generation):
            return
        # Local fallback keeps speech available if Edge TTS or audio playback
        # is unavailable.
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 195)
            engine.setProperty("volume", 1.0)
            for installed_voice in engine.getProperty("voices"):
                voice_id = f"{installed_voice.id} {installed_voice.name}".lower()
                if "de" in voice_id or "german" in voice_id or "deutsch" in voice_id:
                    engine.setProperty("voice", installed_voice.id)
                    break
            with _speech_lock:
                if _speech_was_cancelled(generation):
                    return
                engine.say(text)
                engine.runAndWait()
        except Exception as fallback_error:
            raise RuntimeError(
                f"Sprachausgabe fehlgeschlagen: {edge_error}; {fallback_error}"
            ) from fallback_error


def _speak_with_piper(text, generation):
    install_if_missing("piper-tts", "piper")
    install_if_missing("pygame")
    from piper import PiperVoice
    import pygame

    file_path = os.path.join(tempfile.gettempdir(), "jarvis_voice_output.wav")
    voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))
    with wave.open(file_path, "wb") as audio_file:
        voice.synthesize_wav(text, audio_file)
    with _speech_lock:
        if _speech_was_cancelled(generation):
            return
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and not _speech_was_cancelled(generation):
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()


_speech_lock = threading.Lock()
_speech_state_lock = threading.Lock()
_speech_generation = 0


def start_speaking():
    """Reserves a new speech generation and invalidates older utterances."""
    global _speech_generation
    with _speech_state_lock:
        _speech_generation += 1
        return _speech_generation


def _speech_was_cancelled(generation):
    with _speech_state_lock:
        return generation != _speech_generation


def stop_speaking():
    """Stops current audio playback without affecting the next response."""
    global _speech_generation
    with _speech_state_lock:
        _speech_generation += 1
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
    except Exception:
        pass


def listen_mic() -> str:
    """Nimmt einen kurzen deutschen Sprachbefehl über das Standardmikrofon auf."""
    recognizer = sr.Recognizer()
    device_index = AudioDeviceManager().selected_index()
    try:
        microphone = sr.Microphone(device_index=device_index)
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
        return recognizer.recognize_google(audio, language="de-DE")
    except (sr.WaitTimeoutError, sr.UnknownValueError):
        return ""
    except sr.RequestError as exc:
        raise RuntimeError(f"Spracherkennung nicht erreichbar: {exc}") from exc

if __name__ == "__main__":
    test_text = sys.argv[1] if len(sys.argv) > 1 else "Hallo! So klingt meine neue, menschliche Stimme. Wie gefällt sie dir?"
    speak(test_text)
