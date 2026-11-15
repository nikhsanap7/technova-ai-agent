import sys
print("Python:", sys.version)

import fastapi, uvicorn, httpx, streamlit, mcp
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()
print("All packages imported OK")
print("Gemini key found:", bool(os.getenv("GEMINI_API_KEY")))