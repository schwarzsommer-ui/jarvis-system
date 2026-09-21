import os


# NVIDIA NIM is preferred when configured; Ollama remains the local fallback.
NIM_API_KEY = os.getenv("NIM_API_KEY", "")
NIM_MODEL = os.getenv("NIM_MODEL", "meta/llama-3.1-8b-instruct")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("NIM_MODEL", os.getenv("OLLAMA_MODEL", "llama3.1:8b"))