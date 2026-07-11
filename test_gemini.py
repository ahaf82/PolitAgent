import os
import sys
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print("API Key exists:", bool(api_key))
if not api_key:
    sys.exit(1)

try:
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello! Tell me in 1 sentence if you can hear me."
    )
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
