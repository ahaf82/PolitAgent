import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No API key")
    sys.exit(1)

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=120_000)
)

# Fetch transcript first
sys.path.append(".")
import test_playwright_subs
print("Fetching transcript for K7DPiwk0btw...")
transcript_data = test_playwright_subs.get_transcript_playwright("K7DPiwk0btw")
if not transcript_data:
    print("Failed to get transcript")
    sys.exit(1)

formatted_transcript = []
for entry in transcript_data:
    formatted_transcript.append(f"[{entry['timestamp']}] {entry['text']}")
transcript_text = "\n".join(formatted_transcript)

metadata = {
    "session": 85,
    "date": "2026-06-24",
    "top": "1",
    "topic": "Question Time with Chancellor Merz",
    "url": "https://www.youtube.com/watch?v=K7DPiwk0btw"
}

prompt = f"""
Du bist PolitAgent, ein neutraler, sachlicher KI-Redaktionsassistent.
Deine Aufgabe ist es, das folgende Transkript einer Bundestagssitzung objektiv und strukturiert zusammenzufassen.

Gliedere deine Antwort in:
1. Kurzzusammenfassung (3-4 Sätze)
2. Kernaussagen der Redner und Fraktionen

Hier ist das Transkript der Sitzung mit Zeitstempeln:
{transcript_text}
"""

print("Sende an Gemini (gemini-2.5-flash)...")
start_time = time.time()
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="Du bist ein neutraler, sachlicher Redaktionsassistent namens PolitAgent für den Deutschen Bundestag."
        )
    )
    elapsed = time.time() - start_time
    print(f"Erfolgreich beendet in {elapsed:.2f} Sekunden!")
    print("Response Länge:", len(response.text))
    # Save output to a test file
    with open("test_output.md", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Gespeichert in test_output.md")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"Fehler nach {elapsed:.2f} Sekunden: {e}")
