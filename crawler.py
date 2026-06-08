import os
import re
import json
import sys
import argparse
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

# Load local environment variables from .env relative to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(env_path)

# We will initialize the Gemini client inside the API call to handle missing key gracefully
def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Fehler: GEMINI_API_KEY nicht in der Umgebung oder .env-Datei gefunden.")
        print("Bitte erstellen Sie eine .env-Datei mit: GEMINI_API_KEY=IhrAPIKey")
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Fehler beim Laden des Google GenAI SDKs: {e}")
        return None

def format_timestamp(seconds):
    """Converts seconds float to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def clean_filename(s):
    """Generates a safe filename slug from a string."""
    s = s.lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r'[^a-z0-9_]+', '_', s)
    return s.strip('_')

def parse_video_title(title, upload_date_str=None):
    """
    Parses Bundestag video titles to extract session, date, TOP and Topic.
    Example German: "81. Sitzung vom 22.05.2026. TOP ZP 8, 9: Arbeitszeitpolitik"
    Example English: "81st Session on 05/22/2026. Agenda Item 11: Current Affairs Debate..."
    """
    metadata = {
        "session": 0,
        "date": "N/A",
        "top": "N/A",
        "topic": title
    }
    
    # Try German regex
    # Pattern: 81. Sitzung vom 22.05.2026. TOP ZP 8, 9: Arbeitszeitpolitik
    de_match = re.search(r'(\d+)\.\s+Sitzung\s+vom\s+(\d{2}\.\d{2}\.\d{4})\.?\s+(?:TOP|Tagesordnungspunkt)\s+([^:]+):\s*(.*)', title, re.IGNORECASE)
    if de_match:
        metadata["session"] = int(de_match.group(1))
        # Convert date from DD.MM.YYYY to YYYY-MM-DD
        try:
            dt = datetime.strptime(de_match.group(2), "%d.%m.%Y")
            metadata["date"] = dt.strftime("%Y-%m-%d")
        except:
            metadata["date"] = de_match.group(2)
        metadata["top"] = de_match.group(3).strip()
        metadata["topic"] = de_match.group(4).strip()
        return metadata

    # Try English regex
    # Pattern: 81st Session on 05/22/2026. Agenda Item 11: Current Affairs...
    en_match = re.search(r'(\d+)(?:st|nd|rd|th)\s+Session\s+on\s+(\d{2}/\d{2}/\d{4})\.?\s+(?:Agenda Item|TOP)\s+([^:]+):\s*(.*)', title, re.IGNORECASE)
    if en_match:
        metadata["session"] = int(en_match.group(1))
        # Convert date from MM/DD/YYYY to YYYY-MM-DD
        try:
            dt = datetime.strptime(en_match.group(2), "%m/%d/%Y")
            metadata["date"] = dt.strftime("%Y-%m-%d")
        except:
            metadata["date"] = en_match.group(2)
        metadata["top"] = en_match.group(3).strip()
        metadata["topic"] = en_match.group(4).strip()
        return metadata

    # Generische Suche nach Sitzung, Datum und TOP als Fallback
    session_match = re.search(r'(\d+)(?:st|nd|rd|th)?\.?\s*(?:Sitzung|Session)', title, re.IGNORECASE)
    if session_match:
        sess_num = int(session_match.group(1))
        # Plenary sessions in the recent uploads are always >= 60.
        # Any session number < 60 is a committee meeting.
        if sess_num < 60:
            metadata["session"] = 0
        else:
            metadata["session"] = sess_num

    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', title)
    if date_match:
        try:
            dt = datetime.strptime(date_match.group(1), "%d.%m.%Y")
            metadata["date"] = dt.strftime("%Y-%m-%d")
        except:
            metadata["date"] = date_match.group(1)
    elif upload_date_str:
        # yt-dlp upload_date is YYYYMMDD
        try:
            dt = datetime.strptime(upload_date_str, "%Y%m%d")
            metadata["date"] = dt.strftime("%Y-%m-%d")
        except:
            metadata["date"] = upload_date_str

    top_match = re.search(r'(?:TOP|Agenda\s*Item)\s+([^:\s]+)', title, re.IGNORECASE)
    if top_match:
        metadata["top"] = top_match.group(1).strip()

    # Bereinige das Thema (lösche bekannte Muster vorne weg)
    clean_topic = title
    clean_topic = re.sub(r'^\d+\.\s+Sitzung\s+vom\s+\d{2}\.\d{2}\.\d{4}\.?\s*', '', clean_topic, flags=re.IGNORECASE)
    clean_topic = re.sub(r'^\d+(?:st|nd|rd|th)\s+Session\s+on\s+\d{2}/\d{2}/\d{4}\.?\s*', '', clean_topic, flags=re.IGNORECASE)
    clean_topic = re.sub(r'^(?:TOP|Agenda\s*Item)\s+[^:]+:\s*', '', clean_topic, flags=re.IGNORECASE)
    metadata["topic"] = clean_topic.strip()

    return metadata

def get_youtube_videos(channel_url, max_videos=30):
    """Fetches video metadata from YouTube channel using RSS Feed as primary, yt-dlp as fallback."""
    # Official Channel ID for Deutscher Bundestag
    channel_id = "UCbh5D3EdIHP4YQA5X-eK1ug"
    
    print(f"Versuche Videos über YouTube RSS-Feed abzurufen (Channel ID: {channel_id})...")
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    videos = []
    rss_success = False
    try:
        import xml.etree.ElementTree as ET
        r = requests.get(rss_url, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'yt': 'http://www.youtube.com/xml/schemas/2015'
            }
            for entry in root.findall('atom:entry', ns):
                video_id_el = entry.find('yt:videoId', ns)
                title_el = entry.find('atom:title', ns)
                published_el = entry.find('atom:published', ns)
                
                if video_id_el is not None and title_el is not None:
                    video_id = video_id_el.text
                    title = title_el.text
                    published = published_el.text
                    # convert ISO date (YYYY-MM-DD...) to YYYYMMDD
                    upload_date = published[:10].replace("-", "")
                    
                    videos.append({
                        'id': video_id,
                        'title': title,
                        'upload_date': upload_date,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
            print(f"Erfolgreich {len(videos)} Videos über RSS-Feed geladen.")
            rss_success = True
    except Exception as e:
        print(f"RSS-Feed konnte nicht geladen werden: {e}")

    # Fallback/extension with yt-dlp if RSS failed or if we need more than 15 videos
    if not rss_success or max_videos > len(videos):
        print(f"Weiche auf yt-dlp aus / lade weitere Videos: Scanne YouTube-Kanal {channel_url} (Max. {max_videos} Videos)...")
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'playlistend': max_videos,
            'quiet': True,
        }
        
        ytdlp_videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(channel_url, download=False)
                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry:
                            continue
                        ytdlp_videos.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'upload_date': entry.get('upload_date'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
            except Exception as e:
                print(f"Fehler beim Abrufen der YouTube-Videos über yt-dlp: {e}")
                
        print(f"{len(ytdlp_videos)} Videos über yt-dlp gefunden.")
        
        # Merge lists, keeping RSS videos first and adding new ones from yt-dlp
        existing_ids = {v['id'] for v in videos}
        for v in ytdlp_videos:
            if v['id'] not in existing_ids:
                videos.append(v)
                existing_ids.add(v['id'])
        
    return videos[:max_videos]

def get_transcript_text(video_id):
    """Retrieves and formats German transcript from YouTube using standard API or Playwright fallback."""
    # 1. Try standard API first (fastest)
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        # Try manual German transcript, then auto German, then others
        try:
            transcript = transcript_list.find_transcript(['de'])
        except Exception:
            try:
                transcript = transcript_list.find_transcript(['en'])
                print(f"Hinweis: Kein deutsches Transkript für {video_id} gefunden, weiche auf Englisch aus.")
            except Exception:
                transcript = next(iter(transcript_list))
                print(f"Hinweis: Keine deutschen oder englischen Transkripte für {video_id} gefunden, nehme {transcript.language}.")
        
        data = transcript.fetch()
        
        # Format transcript with timestamps
        formatted_transcript = []
        for entry in data:
            start_sec = entry.start
            timestamp = format_timestamp(start_sec)
            formatted_transcript.append(f"[{timestamp}] {entry.text}")
            
        return "\n".join(formatted_transcript), len(data)
    except Exception as api_err:
        print(f"Standard-API fehlgeschlagen für Video {video_id}: {api_err}")
        print("Weiche auf robusten Playwright-Browser-Scraper aus...")
        
        # 2. Playwright Fallback (indistinguishable from real user)
        try:
            from playwright.sync_api import sync_playwright
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='de-DE',
                    viewport={'width': 1280, 'height': 800}
                )
                page = context.new_page()
                page.goto(url)
                
                # Handle Consent Banner
                try:
                    consent_btn = page.locator('button:has-text("Alle akzeptieren"), button:has-text("Agree to all")').first
                    consent_btn.wait_for(state="visible", timeout=3000)
                    consent_btn.click()
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Expand description
                try:
                    expand_btn = page.locator('#expand, ytd-text-inline-expander #expand, #description-inner, .ytd-text-inline-expander').first
                    expand_btn.wait_for(state="visible", timeout=3000)
                    expand_btn.scroll_into_view_if_needed()
                    expand_btn.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception as exp_err:
                    print(f"Konnte Beschreibung nicht erweitern: {exp_err}")

                # Click "Transkript anzeigen"
                clicked = False
                try:
                    transcript_btn = page.locator('button:has-text("Transkript anzeigen"), button:has-text("Show transcript"), button[aria-label="Transkript anzeigen"]').first
                    transcript_btn.wait_for(state="attached", timeout=4000)
                    transcript_btn.scroll_into_view_if_needed()
                    
                    try:
                        transcript_btn.click(timeout=3000)
                        clicked = True
                        print("Transkript-Button normal geklickt.")
                    except Exception:
                        print("Normaler Klick fehlgeschlagen, versuche erzwungenen Klick...")
                        transcript_btn.click(force=True)
                        clicked = True
                        print("Transkript-Button erzwungen geklickt.")
                    page.wait_for_timeout(1500)
                except Exception as btn_err:
                    print(f"Konnte Transkript-Button über Locator nicht klicken: {btn_err}")
                
                # Direct JS click backup if Locator failed
                if not clicked:
                    try:
                        print("Versuche direkten Klick per JavaScript (Backup)...")
                        page.evaluate("""() => {
                            const btns = Array.from(document.querySelectorAll('button'));
                            const btn = btns.find(b => {
                                const text = (b.textContent || '').toLowerCase();
                                const label = (b.getAttribute('aria-label') || '').toLowerCase();
                                return text.includes('transkript') || text.includes('transcript') || label.includes('transkript') || label.includes('transcript');
                            });
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        }""")
                        page.wait_for_timeout(2000)
                        clicked = True
                    except Exception as js_err:
                        print(f"JavaScript-Backup-Klick fehlgeschlagen: {js_err}")

                # Wait for segments to load
                try:
                    page.wait_for_selector('transcript-segment-view-model', timeout=8000)
                except Exception as seg_err:
                    print(f"Transkript-Segmente wurden nicht geladen: {seg_err}")
                    # Try one more JS backup in case the panel is open but selectors are slightly different
                    try:
                        page.wait_for_timeout(2000)
                    except:
                        pass
                
                # Extract segments
                segments = page.locator('transcript-segment-view-model')
                count = segments.count()
                
                formatted_transcript = []
                # Fallback to older transcript selectors if the new view-model is not found
                if count == 0:
                    print("Keine transcript-segment-view-model Segmente gefunden, suche nach alternativen Selektoren...")
                    segments = page.locator('ytd-transcript-segment-renderer, .ytd-transcript-segment-renderer')
                    count = segments.count()
                
                for i in range(count):
                    seg = segments.nth(i)
                    try:
                        timestamp_el = seg.locator('.ytwTranscriptSegmentViewModelTimestamp, .segment-timestamp, [class*="Timestamp"]').first
                        text_el = seg.locator('.ytAttributedStringHost, .segment-text, [class*="Text"]').first
                        
                        timestamp = timestamp_el.inner_text().strip()
                        text = text_el.inner_text().strip()
                        formatted_transcript.append(f"[{timestamp}] {text}")
                    except Exception as ext_err:
                        try:
                            lines = seg.inner_text().strip().split('\n')
                            if len(lines) >= 2:
                                formatted_transcript.append(f"[{lines[0]}] {lines[1]}")
                        except:
                            pass
                    
                browser.close()
                if formatted_transcript:
                    print(f"Playwright-Scraper erfolgreich: {len(formatted_transcript)} Segmente geladen.")
                    return "\n".join(formatted_transcript), len(formatted_transcript)
                else:
                    print("Playwright-Scraper konnte keine Segmente extrahieren.")
        except Exception as pw_err:
            print(f"Playwright-Scraper fehlgeschlagen für {video_id}: {pw_err}")
            
        return None, 0

def summarize_with_gemini(client, title, metadata, transcript_text, video_url):
    """Calls Gemini API to create a detailed, objective summary and timeline."""
    if not client:
        return None
        
    print(f"Sende Transkript an Gemini für '{metadata['topic']}'...")
    
    prompt = f"""
Du bist PolitAgent, ein absolut parteipolitisch neutraler, sachlicher und präziser KI-Redaktionsassistent.
Deine Aufgabe ist es, das beigefügte Transkript einer Bundestagssitzung objektiv und strukturiert zusammenzufassen und zu protokollieren.

**WICHTIGE ANWEISUNGEN:**
1. **Absolute Neutralität**: Vermeide jegliche Wertung, emotional geladene Wörter oder Parteilichkeit. Gib die Argumente aller Fraktionen (Koalition und Opposition) gleichermaßen fair, sachlich und in gleicher Detailtiefe wieder.
2. **Deutsche Sprache**: Die Zusammenfassung muss komplett auf Deutsch verfasst sein.
3. **Übersetzung des Titels**: Übersetze das englische Thema `{metadata['topic']}` sinnentsprechend, prägnant und professionell ins Deutsche und verwende diese deutsche Übersetzung als H1-Hauptüberschrift in der allerersten Zeile des Markdowns!
4. **Markdown-Format**: Strukturiere das Protokoll genau nach den folgenden Abschnitten unter Verwendung der exakten Überschriften.
5. **Verlinkte Zeitstempel**: In der Chronologie musst du Zeitstempel aus dem Transkript verwenden und diese als klickbare YouTube-Links im Format `[HH:MM:SS](URL_MIT_SEKUNDEN)` formatieren.
   Beispiel: Wenn ein Redebeitrag bei 02:15 beginnt, berechne die Sekunden (2*60 + 15 = 135) und verlinke es wie folgt: `[00:02:15]({video_url}&t=135)`.

**GEWÜNSCHTE MARKDOWN-STRUKTUR:**

# [Hier die deutsche Übersetzung des Themas einfügen]

## Sitzungs-Metadaten
- **Sitzung:** {metadata['session']}. Sitzung
- **Datum:** {metadata['date']}
- **Tagesordnungspunkt (TOP):** {metadata['top']}
- **Originaltitel:** {title}
- **Video-Link:** [Auf YouTube ansehen]({video_url})

## Kurzzusammenfassung
*Erstelle eine prägnante, sachliche Zusammenfassung des behandelten Themas und des Debattenkerns in 3-4 Sätzen.*

## Kernaussagen und Positionen der Fraktionen
*Stelle die Argumente und Positionen der beteiligten Fraktionen und Redner neutral dar. Gliedere nach Fraktionen (z. B. SPD, CDU/CSU, Bündnis 90/Die Grünen, FDP, AfD, Die Linke, BSW oder fraktionslos), sofern diese im Transkript vorkommen.*
- **[Fraktionsname]**:
  - Kernargument 1
  - Kernargument 2
- **[Fraktionsname]**:
  - Kernargument 1

## Chronologischer Debattenverlauf
*Erstelle eine detaillierte Chronologie der wichtigsten Beiträge und Wendepunkte. Jeder Punkt MUSS mit einem klickbaren Zeitstempel beginnen, der direkt zum entsprechenden Moment im YouTube-Video führt.*
- **[00:00:00]({video_url}&t=0)** - **Sitzungsbeginn / Einleitung**: Kurze Beschreibung, wer die Debatte eröffnet.
- **[Zeitstempel]({video_url}&t=sekunden)** - **[Rednername] ([Partei])**: Zusammenfassung des Redebeitrags (sachlich, in indirekter Rede).
- **[Zeitstempel]({video_url}&t=sekunden)** - **Zwischenrufe / Störungen / Abstimmungen**: (Falls im Transkript erkennbar, z.B. Reaktionen im Plenum).

---

Hier ist das Transkript der Sitzung mit Zeitstempeln:
{transcript_text}
"""
    
    max_retries = 3
    retry_delay = 30
    for attempt in range(1, max_retries + 1):
        try:
            from google.genai import types
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="Du bist ein neutraler, sachlicher Redaktionsassistent namens PolitAgent für den Deutschen Bundestag."
                )
            )
            return response.text
        except Exception as e:
            err_msg = str(e)
            is_transient = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "503" in err_msg or "UNAVAILABLE" in err_msg or "experiencing high demand" in err_msg
            if is_transient:
                if attempt < max_retries:
                    print(f"Temporärer Gemini API Fehler ({err_msg}). Versuche es in {retry_delay} Sekunden erneut (Versuch {attempt}/{max_retries})...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
            print(f"Fehler bei der Gemini-API-Generierung: {e}")
            return None

def update_sessions_index(index_path, new_session):
    """Updates the central sessions.json index file, keeping it sorted by date desc."""
    sessions = []
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                sessions = json.load(f)
        except Exception as e:
            print(f"Fehler beim Lesen der Indexdatei {index_path}: {e}")
            sessions = []

    # Check if video already exists in index, if so, update it, else append
    existing_index = -1
    for i, s in enumerate(sessions):
        if s['id'] == new_session['id']:
            existing_index = i
            break
            
    if existing_index >= 0:
        # Keep speakers_path if it exists in the old session but is not defined in the new one
        if 'speakers_path' in sessions[existing_index] and 'speakers_path' not in new_session:
            new_session['speakers_path'] = sessions[existing_index]['speakers_path']
        # Keep documents_path if it exists in the old session but is not defined in the new one
        if 'documents_path' in sessions[existing_index] and 'documents_path' not in new_session:
            new_session['documents_path'] = sessions[existing_index]['documents_path']
        sessions[existing_index] = new_session
        print(f"Aktualisiere bestehenden Eintrag für Video {new_session['id']} im Index.")
    else:
        sessions.append(new_session)
        print(f"Füge neuen Eintrag für Video {new_session['id']} zum Index hinzu.")

    # Sort sessions by date (descending) and then by session number (descending) and top slug
    def sort_key(s):
        date_str = s.get('date', '0000-00-00')
        session_num = s.get('session', 0)
        # Handle N/A date
        if date_str == 'N/A':
            date_str = '0000-00-00'
        return (date_str, session_num, s.get('top', ''))

    sessions.sort(key=sort_key, reverse=True)

    # Write updated index
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

def save_sessions_index(index_path, sessions):
    """Saves the sessions list to the index JSON file."""
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Fehler beim Schreiben des Sessions-Index: {e}")

def robust_json_loads(text):
    """
    Robustly parses JSON from text, extracting the first dictionary-like structure
    and falling back to common cleaning methods or ast.literal_eval if standard json.loads fails.
    """
    text = text.strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError("Keine JSON-Struktur (Klammern) im Text gefunden.")
        
    extracted_text = text[start_idx:end_idx+1]
    
    # 1. Try standard JSON parse
    try:
        return json.loads(extracted_text)
    except json.JSONDecodeError as standard_err:
        # 2. Try ast.literal_eval for single-quoted Python dict-like output
        import ast
        try:
            # ast.literal_eval parses Python dict literals (e.g. {'key': 'value', 'bool': True})
            # JSON might have true/false/null which ast needs as True/False/None
            cleaned = extracted_text
            cleaned = re.sub(r'\btrue\b', 'True', cleaned)
            cleaned = re.sub(r'\bfalse\b', 'False', cleaned)
            cleaned = re.sub(r'\bnull\b', 'None', cleaned)
            
            parsed_dict = ast.literal_eval(cleaned)
            if isinstance(parsed_dict, dict):
                print("JSON erfolgreich mit ast.literal_eval geparst.")
                return parsed_dict
        except Exception as ast_err:
            print(f"ast.literal_eval Fallback ebenfalls fehlgeschlagen: {ast_err}")
            
        raise standard_err

def generate_session_documents(client, title, date, session, top, transcript_text):
    """
    Identifies the Bundestag Drucksachen (documents) mentioned in the transcript,
    finds their official PDF or info URLs, and checks if a namentliche Abstimmung took place.
    If so, gathers the voting results (Ja, Nein, Enthaltung) overall and per faction.
    """
    if not client:
        return None
        
    print(f"Führe Google Search Grounding Dokumenten- und Abstimmungs-Analyse durch für '{title}' ({date})...")
    
    prompt = f"""
    Analysiere das beigefügte Protokoll der Bundestagsdebatte vom {date} zum Thema '{title}'.
    
    **Deine Aufgaben:**
    1. Identifiziere alle in der Debatte erwähnten offiziellen Bundestags-Drucksachen (z. B. im Format 'Drucksache 20/12345' oder '21/4463').
    2. Suche im Internet nach den genauen Titeln dieser Drucksachen und ihren URLs auf bundestag.de (bevorzugt direkte PDF-Links von dserver.bundestag.de).
       - *Hinweis:* Der Link zur Drucksache 21/4463 lautet: https://dserver.bundestag.de/btd/21/044/2104463.pdf. Du kannst diese Struktur nutzen, um Links zu generieren.
    3. Ermittle, ob es zu dieser Debatte an diesem Tag eine \"namentliche Abstimmung\" im Bundestag gab.
    4. Falls eine namentliche Abstimmung stattfand:
       - Ermittle das Gesamtergebnis (Anzahl der Stimmen für Ja, Nein, Enthaltung, Nicht abgegeben/Ungültig).
       - Ermittle das Ergebnis aufgeteilt nach den einzelnen Fraktionen (SPD, CDU/CSU, Bündnis 90/Die Grünen, FDP, AfD, Die Linke, BSW, Fraktionslos).
       - Suche den offiziellen Link zur Abstimmungsseite auf bundestag.de (z. B. unter https://www.bundestag.de/abstimmung).
    5. Falls KEINE namentliche Abstimmung stattfand (oder du keine Daten dazu findest):
       - Ermittle den Beschluss oder den Verfahrensstand aus dem Protokoll (z. B. \"Die Vorlage wurde an den Ausschuss für Arbeit und Soziales überwiesen\" oder \"Der Antrag wurde mit den Stimmen der Koalitionsmehrheit abgelehnt\").
    
    Gib das Ergebnis AUSSCHLIESSLICH als gültiges JSON-Objekt zurück. Schreibe keine Erklärungen, einleitenden Text oder Markdown-Blöcke außerhalb des JSON (kein ```json). Das JSON muss exakt der folgenden Struktur entsprechen:
    {{
      "documents": [
        {{
          "number": "Drucksache 20/XXXXX" oder "Drucksache 21/XXXXX",
          "title": "Offizieller Titel der Drucksache (z. B. 'Gesetzentwurf der Bundesregierung...')",
          "url": "Der direkte Link zur PDF-Datei auf dserver.bundestag.de oder die Suchseite auf dip.bundestag.de. Wenn nicht auffindbar, setze 'N/A'.",
          "type": "Gesetzentwurf" | "Antrag" | "Beschlussempfehlung" | "Unterrichtung" | "Anderes"
        }}
      ],
      "voting": {{
        "has_namentliche_abstimmung": true | false,
        "decision_text": "Eine sachliche Beschreibung des Beschlusses bzw. Verfahrensstands der Debatte (1-2 Sätze).",
        "official_voting_url": "Die offizielle URL auf bundestag.de zur namentlichen Abstimmung. Wenn keine namentliche Abstimmung vorliegt, setze 'N/A'.",
        "overall_result": {{
          "ja": 123,
          "nein": 45,
          "enthaltung": 6,
          "nicht_abgegeben": 7
        }},
        "faction_results": [
          {{
            "faction": "SPD" | "CDU/CSU" | "Bündnis 90/Die Grünen" | "FDP" | "AfD" | "Die Linke" | "BSW" | "Fraktionslos",
            "ja": 100,
            "nein": 0,
            "enthaltung": 2,
            "nicht_abgegeben": 1
          }}
        ]
      }}
    }}
    
    Befülle das JSON sorgfältig. Falls keine Drucksachen erwähnt wurden, gib ein leeres Array für 'documents' zurück. Falls keine namentliche Abstimmung stattfand, setze 'has_namentliche_abstimmung' auf false und setze 'overall_result' und 'faction_results' auf null oder leere Listen/Objekte.
    
    Hier ist das Protokoll der Sitzung:
    {transcript_text[:12000]}
    """
    
    try:
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Du bist ein hochpräziser parlamentarischer Analyst des Deutschen Bundestags, der offizielle Dokumente und Abstimmungen ermittelt und das Ergebnis als JSON ausgibt.",
                tools=[{"google_search": {}}]
            )
        )
        text = response.text.strip()
        
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        json_data = robust_json_loads(text)
        return json_data
    except Exception as e:
        print(f"Fehler bei der Dokumenten- und Abstimmungs-Analyse mit Gemini: {e}")
        return None

def verify_and_format_documents(doc_json):
    """
    Checks all document URLs and voting URLs in doc_json.
    Verifies that they exist and return 200/300.
    If a document PDF URL fails or returns 404, we replace it with a DIP search URL.
    """
    if not doc_json:
        return
        
    import re
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Verify documents URLs
    for doc in doc_json.get('documents', []):
        num_str = doc.get('number', '')
        # Try to parse WP and Doc Number
        match = re.search(r'(\d{2})\/(\d{1,5})', num_str)
        if match:
            wp = match.group(1)
            num = match.group(2)
            padded_num = num.zfill(5)
            first_three = padded_num[:3]
            pdf_url = f"https://dserver.bundestag.de/btd/{wp}/{first_three}/{wp}{num}.pdf"
            
            try:
                r = requests.get(pdf_url, headers=headers, timeout=5, stream=True)
                if r.status_code < 400:
                    doc['url'] = pdf_url
                    print(f"Drucksachen-PDF verifiziert: {pdf_url}")
                else:
                    fallback_url = f"https://dip.bundestag.de/suche?term=Drucksache%20{wp}%2F{num}&rows=25"
                    doc['url'] = fallback_url
                    print(f"Drucksachen-PDF nicht verfuegbar ({r.status_code}), weiche auf DIP aus: {fallback_url}")
            except Exception as e:
                fallback_url = f"https://dip.bundestag.de/suche?term=Drucksache%20{wp}%2F{num}&rows=25"
                doc['url'] = fallback_url
                print(f"Fehler bei Drucksachen-Verifikation ({e}), weiche auf DIP aus: {fallback_url}")
        else:
            url = doc.get('url', 'N/A')
            if url and url != 'N/A' and url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=5, stream=True)
                    if r.status_code >= 400:
                        doc['url'] = 'N/A'
                except:
                    doc['url'] = 'N/A'
                    
    # Verify voting URL
    voting = doc_json.get('voting', {})
    if voting:
        vote_url = voting.get('official_voting_url', 'N/A')
        if vote_url and vote_url != 'N/A' and vote_url.startswith('http'):
            try:
                r = requests.get(vote_url, headers=headers, timeout=5, stream=True)
                if r.status_code >= 400:
                    print(f"Abstimmungs-URL fehlerhaft ({r.status_code}): {vote_url}")
                    voting['official_voting_url'] = 'N/A'
            except Exception as e:
                print(f"Fehler bei Abstimmungs-URL-Verifikation: {e}")
                voting['official_voting_url'] = 'N/A'

def run_retroactive_documents_analysis(client, index_path, docs_dir, max_process=3):
    """
    Runs retroactive document and voting analysis for recent sessions.
    """
    if not client:
        print("Kein Gemini-Client vorhanden. Überspringe retroaktive Dokumenten-Analyse.")
        return

    if not os.path.exists(index_path):
        print("Indexdatei existiert nicht. Überspringe Dokumenten-Analyse.")
        return

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden des Index für Dokumenten-Analyse: {e}")
        return

    now = datetime.now()
    sessions_to_update = []

    for s in sessions:
        date_str = s.get('date', 'N/A')
        is_recent = False
        if date_str != 'N/A':
            try:
                session_date = datetime.strptime(date_str, "%Y-%m-%d")
                if (now - session_date).days <= 14:  # up to 14 days ago
                    is_recent = True
            except:
                pass
        
        has_docs = s.get('documents_path') is not None
        
        if not has_docs:
            priority = 2 if is_recent else 1
            sessions_to_update.append((priority, s))

    # Sort by priority desc (recent first) and date desc
    def get_sort_key(item):
        priority, s = item
        date_str = s.get('date', '0000-00-00')
        if date_str == 'N/A' or not date_str:
            date_str = '0000-00-00'
        return (priority, date_str)
    
    sessions_to_update.sort(key=get_sort_key, reverse=True)
    
    # Process up to max_process
    targets = [s for _, s in sessions_to_update[:max_process]]
    if not targets:
        print("Keine Sitzungen für retroaktive Dokumenten-Analyse gefunden.")
        return

    print(f"Starte retroaktive Dokumenten-Analyse für {len(targets)} Sitzungen...")
    
    for s in targets:
        summary_path = s.get('summary_path')
        if not summary_path:
            continue
            
        absolute_protocol_path = os.path.join(docs_dir, summary_path)
        if not os.path.exists(absolute_protocol_path):
            print(f"Protokolldatei fehlt: {summary_path}")
            continue
            
        try:
            with open(absolute_protocol_path, 'r', encoding='utf-8') as f:
                protocol_text = f.read()
        except Exception as e:
            print(f"Konnte Protokolldatei nicht lesen: {e}")
            continue
            
        base, ext = os.path.splitext(summary_path)
        relative_docs_path = f"{base}_documents.json"
        absolute_docs_path = os.path.join(docs_dir, relative_docs_path)
        
        doc_json = generate_session_documents(
            client, 
            s.get('topic') or s.get('title'), 
            s.get('date'), 
            s.get('session'),
            s.get('top'),
            protocol_text
        )
        
        if doc_json:
            verify_and_format_documents(doc_json)
            
            try:
                os.makedirs(os.path.dirname(absolute_docs_path), exist_ok=True)
                with open(absolute_docs_path, 'w', encoding='utf-8') as f:
                    json.dump(doc_json, f, indent=2, ensure_ascii=False)
                print(f"Dokumente & Abstimmungen erfolgreich gespeichert unter: {relative_docs_path}")
                
                # Update session object in our loaded list
                s['documents_path'] = relative_docs_path
                
                # Save index incrementally
                save_sessions_index(index_path, sessions)
            except Exception as e:
                print(f"Fehler beim Schreiben der Dokumenten-JSON für {s['id']}: {e}")
        else:
            print(f"Dokumenten-Analyse für {s['id']} fehlgeschlagen oder keine Ergebnisse.")
            
        # Small delay between calls to respect API limits
        time.sleep(5)

def generate_speaker_statements(client, title, date, video_url, transcript_text):
    """
    Identifies the main speakers in the Bundestag debate transcript/protocol,
    then searches the web for their external statements (Abgeordnetenwatch, Twitter/X, personal websites, press releases)
    and summarizes them in a structured JSON.
    """
    if not client:
        return None
        
    print(f"Führe Google Search Grounding Abgeordneten-Stimmen-Analyse durch für '{title}' ({date})...")
    
    prompt = f"""
    Analysiere das beigefügte Protokoll der Bundestagsdebatte vom {date} zum Thema '{title}'.
    
    **Deine Aufgabe:**
    1. Identifiziere die wichtigsten 3 bis 5 Abgeordneten (Redner), die in dieser Debatte im Plenum gesprochen haben (z. B. an den namentlich genannten Beiträgen im Protokoll).
    2. Suche im Internet nach **externen Aussagen, Reaktionen oder Beiträgen** genau dieser Abgeordneten zu diesem Thema. Suche auf folgenden Kanälen:
       - Abgeordnetenwatch (Antworten auf Bürgerfragen)
       - Persönliche Websites der Politiker (Pressemitteilungen, Blogeinträge)
       - Social-Media-Kanäle der Abgeordneten (Twitter/X, Instagram, etc.)
       - Fraktions-Websites der Parteien (Pressemeldungen)
    
    Gib das Ergebnis AUSSCHLIESSLICH als gültiges JSON-Objekt zurück. Schreibe keine Erklärungen, einleitenden Text oder Markdown-Blöcke außerhalb des JSON (kein ```json). Das JSON muss exakt der folgenden Struktur entsprechen:
    {{
      "synthesis": "Eine kurze, neutrale Zusammenfassung (ca. 4-5 Sätze) der Reaktionen und Positionen der Abgeordneten außerhalb des Bundestages zu diesem Thema.",
      "sources": [
        {{
          "name": "Vollständiger Name des Abgeordneten",
          "party": "SPD" | "CDU/CSU" | "Bündnis 90/Die Grünen" | "FDP" | "AfD" | "Die Linke" | "BSW" | "Fraktionslos",
          "found": true,
          "statement": "Prägnante Zusammenfassung (2-3 Sätze) der externen Aussage/Reaktion des Abgeordneten zum Thema.",
          "source_title": "Titel des Quellbeitrags (z.B. 'Bürgerfrage zu Heizungsgesetz' oder 'Pressemitteilung auf spdfraktion.de')",
          "url": "Der exakte, echte Link zu dieser Aussage (z.B. der direkte Link auf das Abgeordnetenwatch-Profil des Abgeordneten, die Pressemitteilung oder den Tweet). Erfinde NIEMALS URLs und rate keine IDs. Wenn kein exakter Link vorliegt, setze 'N/A'.",
          "platform": "Abgeordnetenwatch" | "Social Media" | "Website" | "Presse"
        }}
      ]
    }}
    
    Befülle das Array 'sources' für ALLE identifizierten Redner der Debatte. Setze 'found' auf false (und lasse statement, source_title, url auf 'N/A' bzw. leere Werte), falls du für einen der Redner absolut keine externen Stellungnahmen finden konntest.
    
    Hier ist das Protokoll der Sitzung:
    {transcript_text[:12000]}
    """
    
    try:
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Du bist ein hochpräziser politischer Analyst des Deutschen Bundestags, der das Verhalten von Abgeordneten außerhalb des Plenums vergleicht und das Ergebnis als JSON ausgibt.",
                tools=[{"google_search": {}}]
            )
        )
        text = response.text.strip()
        
        # Robustly extract JSON object between first '{' and last '}'
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        json_data = robust_json_loads(text)
        return json_data
    except Exception as e:
        print(f"Fehler bei der Abgeordneten-Stimmen-Analyse mit Gemini: {e}")
        try:
            print(f"API-Antwortvorschau: {response.text[:200]}...")
        except:
            pass
        return None

def verify_speaker_urls(speaker_json):
    """
    Checks all sources in speaker_json.
    Verifies that the URLs exist and do not return 404 (Not Found).
    If a URL returns 404, it resets it to 'N/A' and sets found to False.
    """
    if not speaker_json or 'sources' not in speaker_json:
        return
        
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for src in speaker_json.get('sources', []):
        if not src.get('found'):
            continue
        url = src.get('url', 'N/A')
        if url and url != 'N/A' and url.startswith('http'):
            # Check typical dummy patterns first
            if any(pat in url for pat in ('888888', '123456', 'c0a6-4c4f', 'd2d1e2e1')):
                print(f"URL als Dummy erkannt: {url}")
                src['url'] = 'N/A'
                src['found'] = False
                continue
                
            try:
                # Follow redirects, stream=True to avoid loading large pages
                r = requests.get(url, headers=headers, timeout=5, stream=True)
                if r.status_code == 404:
                    print(f"Geringere Gueltigkeit (404 Not Found): {url}")
                    src['url'] = 'N/A'
                    src['found'] = False
                else:
                    final_url = r.url
                    print(f"URL verifiziert (HTTP {r.status_code}): {url} -> {final_url}")
                    src['url'] = final_url
            except Exception as e:
                print(f"URL-Verifikationsfehler (Verbindung fehlgeschlagen): {url} - {e}")
                src['url'] = 'N/A'
                src['found'] = False

def run_retroactive_speaker_analysis(client, index_path, docs_dir, max_process=3):
    """
    Runs retroactive speaker statement analysis for recent sessions.
    Also cleans up existing speaker statements that have no valid direct links.
    """
    if not client:
        print("Kein Gemini-Client vorhanden. Überspringe retroaktive Abgeordneten-Analyse.")
        return

    if not os.path.exists(index_path):
        print("Indexdatei existiert nicht. Überspringe Abgeordneten-Analyse.")
        return

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden des Index für Abgeordneten-Analyse: {e}")
        return

    # Clean up existing sessions that have speakers_path but no valid direct links
    updated_index = False
    for s in sessions:
        speakers_path = s.get('speakers_path')
        if speakers_path:
            absolute_speakers_path = os.path.join(docs_dir, speakers_path)
            if not os.path.exists(absolute_speakers_path):
                s['speakers_path'] = None
                updated_index = True
                continue
                
            try:
                with open(absolute_speakers_path, 'r', encoding='utf-8') as f:
                    speaker_json = json.load(f)
                
                # Verify and filter URLs inside the loaded JSON
                verify_speaker_urls(speaker_json)
                
                # Check if there is still at least one real direct link left
                has_real_url = False
                if 'sources' in speaker_json:
                    from urllib.parse import urlparse
                    for src in speaker_json['sources']:
                        if not src.get('found'):
                            continue
                        url = src.get('url', 'N/A')
                        if url and url != 'N/A' and url.startswith('http'):
                            try:
                                parsed = urlparse(url)
                                if parsed.path not in ('', '/'):
                                    has_real_url = True
                                    break
                            except:
                                pass
                                
                if not has_real_url:
                    print(f"Entferne ungueltige Abgeordneten-Stimmen fuer {s['id']} (keine Direkt-Links).")
                    s['speakers_path'] = None
                    updated_index = True
                    try:
                        os.remove(absolute_speakers_path)
                    except:
                        pass
                else:
                    # Save updated JSON with corrected/filtered URLs
                    with open(absolute_speakers_path, 'w', encoding='utf-8') as f:
                        json.dump(speaker_json, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Fehler bei der Bereinigung von {speakers_path}: {e}")
                
    if updated_index:
        save_sessions_index(index_path, sessions)

    now = datetime.now()
    sessions_to_update = []

    for s in sessions:
        date_str = s.get('date', 'N/A')
        is_recent = False
        if date_str != 'N/A':
            try:
                session_date = datetime.strptime(date_str, "%Y-%m-%d")
                if (now - session_date).days <= 7:
                    is_recent = True
            except:
                pass
        
        has_speakers = s.get('speakers_path') is not None
        
        if not has_speakers:
            priority = 2 if is_recent else 1
            sessions_to_update.append((priority, s))

    # Sort by priority desc (recent first) and date desc
    def get_sort_key(item):
        priority, s = item
        date_str = s.get('date', '0000-00-00')
        if date_str == 'N/A' or not date_str:
            date_str = '0000-00-00'
        return (priority, date_str)
    
    sessions_to_update.sort(key=get_sort_key, reverse=True)
    
    # Process up to max_process
    targets = [s for _, s in sessions_to_update[:max_process]]
    if not targets:
        print("Keine Sitzungen für retroaktive Abgeordneten-Analyse gefunden.")
        return

    print(f"Starte retroaktive Abgeordneten-Analyse für {len(targets)} Sitzungen...")
    
    for s in targets:
        summary_path = s.get('summary_path')
        if not summary_path:
            continue
            
        absolute_protocol_path = os.path.join(docs_dir, summary_path)
        if not os.path.exists(absolute_protocol_path):
            print(f"Protokolldatei fehlt: {summary_path}")
            continue
            
        try:
            with open(absolute_protocol_path, 'r', encoding='utf-8') as f:
                protocol_text = f.read()
        except Exception as e:
            print(f"Konnte Protokolldatei nicht lesen: {e}")
            continue
            
        base, ext = os.path.splitext(summary_path)
        relative_speakers_path = f"{base}_speakers.json"
        absolute_speakers_path = os.path.join(docs_dir, relative_speakers_path)
        
        speaker_json = generate_speaker_statements(
            client, 
            s.get('topic') or s.get('title'), 
            s.get('date'), 
            s.get('youtube_url'),
            protocol_text
        )
        
        if speaker_json:
            # Perform live HTTP check on all generated URLs first
            verify_speaker_urls(speaker_json)
            
            # Verify if there is at least one real, direct link
            has_real_url = False
            if 'sources' in speaker_json:
                from urllib.parse import urlparse
                for src in speaker_json['sources']:
                    if not src.get('found'):
                        continue
                    url = src.get('url', 'N/A')
                    if url and url != 'N/A' and url.startswith('http'):
                        try:
                            parsed = urlparse(url)
                            # Exclude generic homepages
                            if parsed.path not in ('', '/'):
                                has_real_url = True
                                break
                        except:
                            pass
            
            if not has_real_url:
                print(f"Abgeordneten-Analyse fuer {s['id']} verworfen (keine validen Direkt-Links gefunden).")
                if 'speakers_path' in s:
                    s['speakers_path'] = None
                save_sessions_index(index_path, sessions)
                if os.path.exists(absolute_speakers_path):
                    try:
                        os.remove(absolute_speakers_path)
                    except:
                        pass
                continue

            try:
                os.makedirs(os.path.dirname(absolute_speakers_path), exist_ok=True)
                with open(absolute_speakers_path, 'w', encoding='utf-8') as f:
                    json.dump(speaker_json, f, indent=2, ensure_ascii=False)
                print(f"Abgeordneten-Stimmen erfolgreich gespeichert unter: {relative_speakers_path}")
                
                # Update session object in our loaded list
                s['speakers_path'] = relative_speakers_path
                
                # Save index incrementally
                save_sessions_index(index_path, sessions)
            except Exception as e:
                print(f"Fehler beim Schreiben der Abgeordneten-JSON für {s['id']}: {e}")
        else:
            print(f"Abgeordneten-Analyse für {s['id']} fehlgeschlagen oder keine Ergebnisse.")
            
        # Small delay between calls to respect API limits
        time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="PolitAgent Crawler - Dokumentiert und fasst Bundestagssitzungen zusammen.")
    parser.add_argument("--days", type=int, default=3, help="Anzahl der letzten Sitzungstage, die erfasst werden sollen (nur bei Erstbefüllung relevant).")
    parser.add_argument("--max-videos", type=int, default=300, help="Maximale Anzahl der zu prüfenden YouTube-Videos.")
    parser.add_argument("--max-process", type=int, default=10, help="Maximale Anzahl der in diesem Durchlauf zu verarbeitenden Videos (schützt Quota).")
    parser.add_argument("--max-speakers-process", type=int, default=3, help="Maximale Anzahl der retroaktiv zu analysierenden Sitzungen für Abgeordneten-Stimmen.")
    parser.add_argument("--max-documents-process", type=int, default=3, help="Maximale Anzahl der retroaktiv zu analysierenden Sitzungen für Dokumente & Abstimmungen.")
    parser.add_argument("--force-video", type=str, default=None, help="Erzwinge die Verarbeitung einer bestimmten YouTube Video-ID.")
    args = parser.parse_args()

    print("=== PolitAgent Crawler & Analyzer ===")
    
    # Initialize Gemini client
    client = get_gemini_client()
    if not client:
        print("Crawler läuft im Offline-Modus (keine Zusammenfassungen mit Gemini möglich).")
        print("Erstellen Sie eine .env Datei und tragen Sie Ihren GEMINI_API_KEY ein, um Protokolle zu generieren.")

    # Setup directories
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(workspace_dir, "docs")
    data_dir = os.path.join(docs_dir, "data")
    protocols_dir = os.path.join(docs_dir, "protocols")
    
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(protocols_dir, exist_ok=True)
    
    index_path = os.path.join(data_dir, "sessions.json")
    
    # Load already processed videos
    processed_ids = set()
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                processed_ids = {item['id'] for item in existing_data}
            print(f"{len(processed_ids)} bereits verarbeitete Videos im Index gefunden.")
        except Exception as e:
            print(f"Index konnte nicht gelesen werden, starte neu: {e}")

    # Fetch recent videos from Bundestag YouTube Channel
    # Channel URL for Deutscher Bundestag
    channel_url = "https://www.youtube.com/@bundestag/videos"
    videos = get_youtube_videos(channel_url, max_videos=args.max_videos)
    
    if not videos:
        print("Keine Videos gefunden. Beende.")
        return

    # Parse metadata for all videos
    parsed_videos = []
    for v in videos:
        meta = parse_video_title(v['title'], v['upload_date'])
        v.update(meta)
        parsed_videos.append(v)

    # Filter videos to process
    videos_to_process = []
    
    if args.force_video:
        # Force single video
        force_vid = next((v for v in parsed_videos if v['id'] == args.force_video), None)
        if force_vid:
            videos_to_process = [force_vid]
            print(f"Erzwinge Verarbeitung für Video-ID: {args.force_video}")
        else:
            print(f"Erzwungene Video-ID {args.force_video} wurde nicht in den neuesten Videos gefunden.")
            # Create a mock entry if it's not in the list
            videos_to_process = [{
                'id': args.force_video,
                'title': 'Erzwungenes Video',
                'url': f"https://www.youtube.com/watch?v={args.force_video}",
                'session': 0,
                'date': datetime.now().strftime("%Y-%m-%d"),
                'top': 'N/A',
                'topic': 'Erzwungene Sitzung'
            }]
    elif not processed_ids:
        # Initial run: process the last N unique session days
        # Group videos by parsed date
        dates_with_videos = {}
        for v in parsed_videos:
            d = v['date']
            if d != 'N/A':
                if d not in dates_with_videos:
                    dates_with_videos[d] = []
                dates_with_videos[d].append(v)
        
        # Get sorted unique dates (descending)
        unique_dates = sorted(list(dates_with_videos.keys()), reverse=True)
        target_dates = unique_dates[:args.days]
        print(f"Erstbefüllung: Verarbeite die letzten {args.days} Sitzungstage ({', '.join(target_dates)})...")
        
        for d in target_dates:
            videos_to_process.extend(dates_with_videos[d])
            
        # Reverse to process older sessions first
        videos_to_process.reverse()
    else:
        # Continuous run: process all new videos
        for v in parsed_videos:
            if v['id'] not in processed_ids:
                videos_to_process.append(v)
        print(f"Fortlaufender Betrieb: {len(videos_to_process)} neue Videos zum Verarbeiten gefunden.")
        # Process older first
        videos_to_process.reverse()

    # Apply limit on max process to protect daily Gemini API quota
    if len(videos_to_process) > args.max_process:
        print(f"Limitiere Verarbeitung von {len(videos_to_process)} auf {args.max_process} Videos, um API-Quota-Limits zu wahren.")
        videos_to_process = videos_to_process[:args.max_process]

    success_count = 0
    if not videos_to_process:
        print("Keine neuen Videos zu verarbeiten.")
    else:
        print(f"Es werden {len(videos_to_process)} Videos verarbeitet.")
        for i, v in enumerate(videos_to_process, 1):
            print(f"\n[{i}/{len(videos_to_process)}] Verarbeite Video: {v['title']} (ID: {v['id']})")
            
            # 1. Fetch transcript
            transcript_text, length = get_transcript_text(v['id'])
            if not transcript_text:
                print(f"Überspringe Video {v['id']} aufgrund fehlenden Transkripts.")
                continue
                
            print(f"Transkript erfolgreich geladen ({length} Untertitel-Einträge).")

            # Create protocol paths
            sess_slug = f"session_{v['session']}" if v['session'] > 0 else "session_unknown"
            top_slug = clean_filename(v['top']) if v['top'] != 'N/A' else "top_unknown"
            topic_slug = clean_filename(v['topic'])[:50] # cap topic slug length
            
            filename = f"{top_slug}_{topic_slug}.md"
            relative_protocol_path = os.path.join("protocols", sess_slug, filename).replace("\\", "/")
            absolute_protocol_path = os.path.join(docs_dir, "protocols", sess_slug, filename)
            
            # 2. Summarize with Gemini
            summary_markdown = None
            if client:
                summary_markdown = summarize_with_gemini(client, v['title'], v, transcript_text, v['url'])
            else:
                # Offline dummy summary
                summary_markdown = f"""# {v['topic']}
    
    ## Sitzungs-Metadaten
    - **Sitzung:** {v['session']}. Sitzung
    - **Datum:** {v['date']}
    - **Tagesordnungspunkt (TOP):** {v['top']}
    - **Originaltitel:** {v['title']}
    - **Video-Link:** [Auf YouTube ansehen]({v['url']})
    
    > [!WARNING]
    > Dieses Protokoll wurde im Offline-Modus erstellt, da kein `GEMINI_API_KEY` verfügbar war. Das Transkript konnte nicht analysiert werden.
    """
            
            if not summary_markdown:
                print(f"Fehler beim Erzeugen der Zusammenfassung für Video {v['id']}.")
                continue

            # Extract German title from the first header line of the generated markdown
            if client and summary_markdown:
                lines = summary_markdown.strip().split('\n')
                for line in lines:
                    if line.startswith('# '):
                        german_title = line[2:].strip()
                        if german_title:
                            v['topic'] = german_title
                            print(f"Deutsche Übersetzung für das Thema extrahiert: '{german_title}'")
                            break

            # 3. Save markdown protocol
            os.makedirs(os.path.dirname(absolute_protocol_path), exist_ok=True)
            try:
                with open(absolute_protocol_path, 'w', encoding='utf-8') as f:
                    f.write(summary_markdown)
                print(f"Markdown-Protokoll gespeichert unter: {relative_protocol_path}")
            except Exception as e:
                print(f"Fehler beim Schreiben des Protokolls für {v['id']}: {e}")
                continue

            # 3b. Generate session documents
            relative_docs_path = None
            if client:
                base, ext = os.path.splitext(relative_protocol_path)
                relative_docs_path = f"{base}_documents.json"
                absolute_docs_path = os.path.join(docs_dir, relative_docs_path)
                
                doc_json = generate_session_documents(
                    client,
                    v['title'],
                    v['date'],
                    v['session'],
                    v['top'],
                    summary_markdown
                )
                if doc_json:
                    verify_and_format_documents(doc_json)
                    try:
                        os.makedirs(os.path.dirname(absolute_docs_path), exist_ok=True)
                        with open(absolute_docs_path, 'w', encoding='utf-8') as f:
                            json.dump(doc_json, f, indent=2, ensure_ascii=False)
                        print(f"Dokumente & Abstimmungen gespeichert unter: {relative_docs_path}")
                    except Exception as e:
                        print(f"Fehler beim Schreiben der Dokumente-JSON: {e}")
                        relative_docs_path = None
                else:
                    relative_docs_path = None

            # 4. Update index database
            session_entry = {
                "id": v['id'],
                "title": v['title'],
                "session": v['session'],
                "date": v['date'],
                "top": v['top'],
                "topic": v['topic'],
                "summary_path": relative_protocol_path,
                "documents_path": relative_docs_path,
                "youtube_url": v['url'],
                "processed_at": datetime.now().isoformat()
            }
            update_sessions_index(index_path, session_entry)
            success_count += 1
            
            # Sleep to respect YouTube's rate limits and prevent 429 errors
            if i < len(videos_to_process):
                sleep_time = 8
                print(f"Pausiere für {sleep_time} Sekunden vor dem nächsten Video, um YouTube Rate-Limits zu vermeiden...")
                time.sleep(sleep_time)
            
        print(f"\n=== Video-Verarbeitung abgeschlossen: {success_count} von {len(videos_to_process)} Videos erfolgreich verarbeitet. ===")

    # Run retroactive speaker statements analysis (configurable to protect quota)
    run_retroactive_speaker_analysis(client, index_path, docs_dir, max_process=args.max_speakers_process)
    
    # Run retroactive documents and voting analysis
    run_retroactive_documents_analysis(client, index_path, docs_dir, max_process=args.max_documents_process)
    
    print("\n=== PolitAgent Crawler & Abgeordneten- und Dokumenten-Analyse beendet. ===")

if __name__ == "__main__":
    main()
