import os
import requests
from dotenv import load_dotenv

# Load env variables from root directory
env_path = r"c:\Users\a_h82\OneDrive\Dokumente\Projects\PolitAgent\.env"
load_dotenv(env_path)

app_id = os.getenv("ONESIGNAL_APP_ID")
rest_api_key = os.getenv("ONESIGNAL_REST_API_KEY")
app_url = os.getenv("APP_URL", "https://ahaf82.github.io/PolitAgent")

print("Env Path:", env_path)
print("OneSignal App ID:", app_id)

def send_test_notification():
    if not app_id or not rest_api_key:
        print("Error: ONESIGNAL_APP_ID or ONESIGNAL_REST_API_KEY not found in .env!")
        return

    url = "https://api.onesignal.com/notifications"
    headers = {
        "Authorization": f"Basic {rest_api_key}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {
        "app_id": app_id,
        "included_segments": ["All"],
        "headings": {
            "de": "PolitAgent Test 🔔",
            "en": "PolitAgent Test 🔔"
        },
        "contents": {
            "de": "Test der Push-Benachrichtigung auf deinem Smartphone. Sieht gut aus!",
            "en": "Testing push notifications on your smartphone. Looks good!"
        },
        "url": app_url
    }

    try:
        print("Sending push notification...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print("HTTP Status Code:", response.status_code)
        print("Response:", response.json())
    except Exception as e:
        print("Error sending notification:", e)

if __name__ == "__main__":
    send_test_notification()
