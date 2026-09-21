import pyttsx3
import speech_recognition as sr

def speak(text: str):
    """Liest den übergebenen Text über die Lautsprecher vor."""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 180)
        voices = engine.getProperty('voices')
        for v in voices:
            if "german" in v.name.lower() or "deutsch" in v.name.lower() or "de_" in v.id.lower():
                engine.setProperty('voice', v.id)
                break
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[Sprachausgabe-Fehler]: {e}")

def listen_mic() -> str:
    """Nimmt Sprache über das Mikrofon auf und wandelt sie in Text um."""
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("\n🎤 JARVIS hört zu... (Jetzt sprechen)")
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
            text = r.recognize_google(audio, language="de-DE")
            print(f"🗣️ Du: {text}")
            return text
    except sr.WaitTimeoutError:
        print("Keine Sprache erkannt.")
        return ""
    except Exception as e:
        print(f"Spracheingabe-Fehler: {e}")
        return ""
