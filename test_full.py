import test_playwright_subs

print("Fetching full transcript...")
data = test_playwright_subs.get_transcript_playwright('49oAuGr4T8A')
if data:
    with open("transcript_full.txt", "w", encoding="utf-8") as f:
        for entry in data:
            f.write(f"[{entry['timestamp']}] {entry['text']}\n")
    print("Done! Saved to transcript_full.txt")
else:
    print("Failed to get transcript.")
