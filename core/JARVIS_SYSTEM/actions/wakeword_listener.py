import sys
import subprocess
import time

def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Fehler beim Installieren von {package}: {e}")

# Automatisches Prüfen und Installieren der Pakete
try:
    import speech_recognition as sr
except ImportError:
    print("Installiere Sprach-Komponenten...")
    install_package("SpeechRecognition")
    import speech_recognition as sr

try:
    import pyaudio
except ImportError:
    print("Installiere Audio-Treiber (PyAudio)...")
    install_package("pipwin")
    try:
        subprocess.check_call([sys.executable, "-m", "pipwin", "install", "pyaudio"])
    except Exception:
        install_package("pyaudio")

def main():
    print("========================================")
    print("   JARVIS WAKE-WORD SYSTEM GESTARTET   ")
    print("========================================")
    
    r = sr.Recognizer()
    
    # Mikrofon-Liste prüfen
    mics = sr.Microphone.list_microphone_names()
    print(f"Gefundene Mikrofone: {len(mics)}")
    for idx, name in enumerate(mics):
        print(f" [{idx}] {name}")

    print("\nInitialisiere Standard-Mikrofon...")
    try:
        mic = sr.Microphone()
        with mic as source:
            print("Passe Nebengeräusche an... Bitte 1 Sekunde ruhig sein.")
            r.adjust_for_ambient_noise(source, duration=1.5)
            r.energy_threshold = 300  # Empfindlichkeit anpassen
    except Exception as e:
        print(f"Mikrofon-Fehler: {e}")
        input("Drücke Enter zum Beenden...")
        return

    print("\n[BEREIT] Sag laut und deutlich: 'Hey Jarvis'")
    print("Höre kontinuierlich zu...\n")

    while True:
        try:
            with mic as source:
                audio = r.listen(source, phrase_time_limit=4)
            
            try:
                text = r.recognize_google(audio, language="de-DE").lower()
                print(f"Gehört: {text}")

                if "jarvis" in text or "hey jarvis" in text or "hi jarvis" in text:
                    print("\n>>> ERKANNT: 'Hey Jarvis'! <<<")
                    print("Spreche jetzt deinen Wunsch...")
                    
                    with mic as source:
                        command_audio = r.listen(source, timeout=6, phrase_time_limit=10)
                    
                    command = r.recognize_google(command_audio, language="de-DE")
                    print(f"\nDEIN BEFEHL: {command}\n")
                    
            except sr.UnknownValueError:
                # Nichts verstanden / Nebengeräusch
                pass
            except sr.RequestError as e:
                print(f"Netzwerk/API Fehler: {e}")

        except KeyboardInterrupt:
            print("\nBeendet.")
            break
        except Exception as e:
            print(f"Fehler im Ablauf: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
