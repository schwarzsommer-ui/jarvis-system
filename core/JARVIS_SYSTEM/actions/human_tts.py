import os
import sys
import subprocess
import asyncio
import tempfile

def install_if_missing(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installiere {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

def speak(text: str, voice: str = "de-DE-KillianNeural"):
    """
    Generiert menschliche deutsche Sprachausgabe mit Microsoft Edge TTS (hohe Qualität).
    Mögliche Stimmen:
    - de-DE-KillianNeural (männlich, sehr natürlich)
    - de-DE-KatjaNeural (weiblich, sehr natürlich)
    - de-DE-ConradNeural (männlich, tief)
    """
    install_if_missing("edge-tts", "edge_tts")
    install_if_missing("pygame")

    import edge_tts
    import pygame

    async def _async_speak():
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "jarvis_voice_output.mp3")

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_path)

        # Audio wiedergeben
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.quit()

    asyncio.run(_async_speak())

if __name__ == "__main__":
    test_text = sys.argv[1] if len(sys.argv) > 1 else "Hallo! So klingt meine neue, menschliche Stimme. Wie gefällt sie dir?"
    speak(test_text)
