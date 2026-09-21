import os


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.1:8b")