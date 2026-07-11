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
    
    # Generate approx 40KB of dummy text
    large_text = "Dies ist ein Test. " * 2000
    
    print("Sende grossen Prompt (ca. 36KB) an Gemini...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Hier ist ein grosser Text-Upload. Zusammenfassen in 1 Satz:\n{large_text}"
    )
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
