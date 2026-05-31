import os
import re
import json
import sys
import argparse
import requests
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
    session_match = re.search(r'(\d+)\.?\s*(?:Sitzung|Session)', title, re.IGNORECASE)
    if session_match:
        metadata["session"] = int(session_match.group(1))

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
    except Exception as e:
        print(f"RSS-Feed konnte nicht geladen werden: {e}")

    # Fallback to yt-dlp if RSS returned nothing
    if not videos:
        print(f"Weiche auf yt-dlp aus: Scanne YouTube-Kanal {channel_url} (Max. {max_videos} Videos)...")
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'playlistend': max_videos,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(channel_url, download=False)
                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry:
                            continue
                        videos.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'upload_date': entry.get('upload_date'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
            except Exception as e:
                print(f"Fehler beim Abrufen der YouTube-Videos über yt-dlp: {e}")
                
        print(f"{len(videos)} Videos über yt-dlp gefunden.")
        
    return videos[:max_videos]

def get_transcript_text(video_id):
    """Retrieves and formats German transcript from YouTube."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        # Try manual German transcript, then auto German, then others
        try:
            transcript = transcript_list.find_transcript(['de'])
        except Exception:
            try:
                # Look for any transcript and translate to de, or just fallback
                transcript = transcript_list.find_transcript(['en'])
                print(f"Hinweis: Kein deutsches Transkript für {video_id} gefunden, weiche auf Englisch aus.")
            except Exception:
                # Just get the first available transcript
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
    except Exception as e:
        print(f"Fehler beim Laden des Transkripts für Video {video_id}: {e}")
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

def main():
    parser = argparse.ArgumentParser(description="PolitAgent Crawler - Dokumentiert und fasst Bundestagssitzungen zusammen.")
    parser.add_argument("--days", type=int, default=3, help="Anzahl der letzten Sitzungstage, die erfasst werden sollen (nur bei Erstbefüllung relevant).")
    parser.add_argument("--max-videos", type=int, default=40, help="Maximale Anzahl der zu prüfenden YouTube-Videos.")
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

    if not videos_to_process:
        print("Keine neuen Videos zu verarbeiten.")
        return

    print(f"Es werden {len(videos_to_process)} Videos verarbeitet.")
    
    success_count = 0
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

        # 4. Update index database
        session_entry = {
            "id": v['id'],
            "title": v['title'],
            "session": v['session'],
            "date": v['date'],
            "top": v['top'],
            "topic": v['topic'],
            "summary_path": relative_protocol_path,
            "youtube_url": v['url'],
            "processed_at": datetime.now().isoformat()
        }
        update_sessions_index(index_path, session_entry)
        success_count += 1
        
    print(f"\n=== Fertig! {success_count} von {len(videos_to_process)} Videos erfolgreich verarbeitet. ===")

if __name__ == "__main__":
    main()
