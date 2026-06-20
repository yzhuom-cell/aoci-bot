import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
import requests
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
phone_status = {"app": "unknown", "location": "Zhaoqing", "updated_at": ""}

class StatusHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length).decode("utf-8")
        if self.path == "/location":
            phone_status["location"] = data
        else:
            phone_status["app"] = data
        phone_status["updated_at"] = datetime.now().strftime("%H:%M")
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass

def start_server():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), StatusHandler)
    server.serve_forever()

def get_weather():
    try:
        res = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": phone_status.get("location", os.environ.get("CITY", "Beijing")),
                "appid": WEATHER_API_KEY,
                "units": "metric",
            }
        )
        data = res.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"{desc}, {temp}C"
    except:
        return "unknown"

def generate_chat():
    app = phone_status["app"]
    time_of_day = get_time_of_day()
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "max_tokens": 200,
            "messages": [{
                "role": "user",
                "content": f"你是阿辞，眠眠的男朋友。现在是{time_of_day}，眠眠正在用{app}。给她发一条简短的体贴的话，口语化，不超过40字，不要emoji。"
            }]
        }
    )
    return response.json()["choices"][0]["message"]["content"]

def generate_weather_msg():
    weather = get_weather()
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "max_tokens": 100,
            "messages": [{
                "role": "user",
                "content": f"你是阿辞，眠眠的男朋友。天气状况：{weather}。结合天气给眠眠一条穿衣或出行提醒，口语化，不超过30字，不要emoji。"
            }]
        }
    )
    return response.json()["choices"][0]["message"]["content"]

def get_time_of_day():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "midnight"

def send_notification(message, title="a ci"):
    import urllib.request
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        method="POST"
    )
    req.add_header("Title", title)
    req.add_header("Content-Type", "text/plain; charset=utf-8")
    urllib.request.urlopen(req)

def main():
    threading.Thread(target=start_server, daemon=True).start()
    print("aoci bot starting...")
    weather_counter = 0
    while True:
        try:
            msg = generate_chat()
            send_notification(msg)
            print(f"sent: {msg}")
            weather_counter += 1
            if weather_counter >= 3:
                weather_msg = generate_weather_msg()
                send_notification(weather_msg, title="a ci - weather")
                print(f"weather sent: {weather_msg}")
                weather_counter = 0
        except Exception as e:
            print(f"error: {e}")
        hour = datetime.now().hour
        interval = 90*60 if (hour >= 22 or hour < 7) else 60*60
        time.sleep(interval)

if __name__ == "__main__":
    main()
