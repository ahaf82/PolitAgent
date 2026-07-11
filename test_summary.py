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
Du bist PolitAgent, ein absolut parteipolitisch neutraler, sachlicher und präziser KI-Redaktionsassistent.
Deine Aufgabe ist es, das beigefügte Transkript einer Bundestagssitzung objektiv und strukturiert zusammenzufassen und zu protokollieren.

**WICHTIGE ANWEISUNGEN:**
1. **Absolute Neutralität**: Vermeide jegliche Wertung, emotional geladene Wörter oder Parteilichkeit. Gib die Argumente aller Fraktionen (Koalition und Opposition) gleichermaßen fair, sachlich und in gleicher Detailtiefe wieder.
2. **Deutsche Sprache**: Die Zusammenfassung muss komplett auf Deutsch verfasst sein.
3. **Übersetzung des Titels**: Übersetze das englische Thema `{metadata['topic']}` sinnentsprechend, prägnant und professionell ins Deutsche und verwende diese deutsche Übersetzung als H1-Hauptüberschrift in der allerersten Zeile des Markdowns!
4. **Markdown-Format**: Strukturiere das Protokoll genau nach den folgenden Abschnitten unter Verwendung der exakten Überschriften.
5. **Verlinkte Zeitstempel**: In der Chronologie musst du Zeitstempel aus dem Transkript verwenden und diese als klickbare YouTube-Links im Format `[HH:MM:SS](URL_MIT_ZEIT)` formatieren.
   Beispiel: Wenn ein Redebeitrag bei 02:15 beginnt, verlinke es wie folgt: `[00:02:15]({metadata['url']}&t=2m15s)`. Wenn ein Redebeitrag bei 01:02:15 beginnt, verlinke es wie folgt: `[01:02:15]({metadata['url']}&t=1h2m15s)`.

**GEWÜNSCHTE MARKDOWN-STRUKTUR:**

# [Hier die deutsche Übersetzung des Themas einfügen]

## Sitzungs-Metadaten
- **Sitzung:** {metadata['session']}. Sitzung
- **Datum:** {metadata['date']}
- **Tagesordnungspunkt (TOP):** {metadata['top']}
- **Originaltitel:** {metadata['topic']}
- **Video-Link:** [Auf YouTube ansehen]({metadata['url']})

## Kurzzusammenfassung
*Erstelle eine prägnante, sachliche Zusammenfassung des behandelten Themas und des Debattenkerns in 3-4 Sätzen.*

## Kernaussagen und Positionen der Fraktionen
*Stelle die Argumente und Positionen der beteiligten Fraktionen und Redner neutral dar. Gliedere nach Fraktionen (z. B. SPD, CDU/CSU, Bündnis 90/Die Grünen, FDP, AfD, Die Linke, BSW oder fraktionslos), sofern diese im Transkript vorkommen.*

## Chronologischer Debattenverlauf
*Erstelle eine detaillierte Chronologie der wichtigsten Beiträge und Wendepunkte. Jeder Punkt MUSS mit einem klickbaren Zeitstempel beginnen, der direkt zum entsprechenden Moment im YouTube-Video führt.*

---

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
