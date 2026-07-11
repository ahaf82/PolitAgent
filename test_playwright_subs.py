import sys
import time
from playwright.sync_api import sync_playwright

def get_transcript_playwright(video_id):
    print(f"Starte Playwright für Video-ID: {video_id}...")
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set realistic user agent and German locale
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-DE',
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        page.goto(url)
        
        # 1. Handle Consent Banner if present
        print("Prüfe auf YouTube-Zustimmungsbanner...")
        try:
            # Look for "Alle akzeptieren" button
            consent_btn = page.locator('button:has-text("Alle akzeptieren"), button:has-text("Agree to all")').first
            consent_btn.wait_for(state="visible", timeout=5000)
            consent_btn.click()
            print("Zustimmungsbanner akzeptiert.")
            page.wait_for_timeout(1500)
        except Exception as e:
            print("Kein Zustimmungsbanner gefunden oder Fehler beim Klicken:", e)

        # 2. Click "...mehr" (expand description)
        print("Erweitere Videobeschreibung...")
        try:
            # Standard YouTube expand button ID is '#expand' or '#description-inner'
            expand_btn = page.locator('#expand, ytd-text-inline-expander #expand, #description-inner').first
            expand_btn.wait_for(state="visible", timeout=5000)
            expand_btn.click()
            print("Beschreibung erweitert.")
            page.wait_for_timeout(500)
        except Exception as e:
            print("Fehler beim Erweitern der Beschreibung, mache Screenshot:", e)
            page.screenshot(path="error_expand.png")
            browser.close()
            return None

        # 3. Click "Transkript anzeigen"
        print("Suche nach 'Transkript anzeigen' Button...")
        try:
            # Try German and English button text
            transcript_btn = page.locator('button:has-text("Transkript anzeigen"), button:has-text("Show transcript"), button[aria-label="Transkript anzeigen"]').first
            transcript_btn.wait_for(state="visible", timeout=5000)
            transcript_btn.scroll_into_view_if_needed()
            transcript_btn.click()
            print("Transkript-Button geklickt.")
            page.wait_for_timeout(1500)
        except Exception as e:
            print("Konnte den Transkript-Button nicht finden. Mache Screenshot.")
            page.screenshot(path="error_transcript_btn.png")
            browser.close()
            return None

        # 4. Wait for transcript segments to load
        print("Warte auf Transkript-Segmente...")
        try:
            page.wait_for_selector('transcript-segment-view-model', timeout=10000)
            print("Transkript-Segmente geladen.")
        except Exception as e:
            print("Transkript-Segmente wurden nicht geladen. Mache Screenshot.")
            page.screenshot(path="error_segments.png")
            browser.close()
            return None

        # 5. Extract segments
        segments = page.locator('transcript-segment-view-model')
        count = segments.count()
        print(f"{count} Segmente gefunden. Extrahiere Text...")
        
        transcript_data = []
        for i in range(count):
            seg = segments.nth(i)
            # Get timestamp
            timestamp = seg.locator('.ytwTranscriptSegmentViewModelTimestamp').inner_text().strip()
            # Get text
            text = seg.locator('.ytAttributedStringHost').inner_text().strip()
            
            transcript_data.append({
                'timestamp': timestamp,
                'text': text
            })
            
        browser.close()
        return transcript_data

if __name__ == "__main__":
    import sys
    video_id = sys.argv[1] if len(sys.argv) > 1 else 'CPa1rLMiv64'
    data = get_transcript_playwright(video_id)
    if data:
        print(f"\nErfolgreich extrahiert! Insgesamt {len(data)} Zeilen.")
        print("Erste 5 Zeilen:")
        for entry in data[:5]:
            print(f"[{entry['timestamp']}] {entry['text']}")
    else:
        print("\nFehler: Transkript konnte nicht geladen werden.")
