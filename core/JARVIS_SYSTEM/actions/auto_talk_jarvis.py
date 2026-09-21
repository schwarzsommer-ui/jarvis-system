import sys
import subprocess
import time

def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Installationsfehler bei {package}: {e}")

try:
    import speech_recognition as sr
except ImportError:
    install_package("SpeechRecognition")
    import speech_recognition as sr

try:
    import pyautogui
except ImportError:
    install_package("pyautogui")
    import pyautogui

try:
    import pyaudio
except ImportError:
    install_package("pyaudio")

def start_handsfree_jarvis():
    print("==================================================")
    print("   JARVIS HANDS-FREE AUTOMATION GESTARTET         ")
    print("==================================================")
    print("1. Klicke jetzt einmal in das Chat-Eingabefeld.")
    print("2. Sag einfach 'Hey Jarvis ...' gefolgt von deiner Frage.")
    print("3. Der Text wird automatisch getippt und mit ENTER gesendet!\n")

    r = sr.Recognizer()
    try:
        mic = sr.Microphone()
        with mic as source:
            r.adjust_for_ambient_noise(source, duration=1)
            r.energy_threshold = 300
    except Exception as e:
        print(f"Fehler beim Zugriff auf das Mikrofon: {e}")
        input("Drücke Enter zum Beenden...")
        return

    while True:
        try:
            with mic as source:
                print("Höre zu...")
                audio = r.listen(source, phrase_time_limit=8)
            
            try:
                text = r.recognize_google(audio, language="de-DE")
                print(f"Erkannt: {text}")

                # Wenn Text erkannt wurde, in das aktive Chatfeld tippen und Enter drücken
                if text.strip():
                    # Falls der Satz mit "hey jarvis" beginnt, schneiden wir es optional ab oder lassen es stehen
                    clean_text = text
                    if clean_text.lower().startswith("hey jarvis"):
                        clean_text = clean_text[10:].strip()
                    elif clean_text.lower().startswith("jarvis"):
                        clean_text = clean_text[6:].strip()

                    if not clean_text:
                        clean_text = text

                    print(f"Sende an Chat: {clean_text}")
                    pyautogui.write(clean_text, interval=0.02)
                    time.sleep(0.1)
                    pyautogui.press("enter")
                    print("Automatisch gesendet!")

            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"API Fehler: {e}")

        except KeyboardInterrupt:
            print("\nHands-Free beendet.")
            break
        except Exception as e:
            print(f"Fehler: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_handsfree_jarvis()
