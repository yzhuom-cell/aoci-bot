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
sent_reminders = set()

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

def get_time_of_day():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "早上"
    elif 12 <= hour < 18:
        return "下午"
    elif 18 <= hour < 23:
        return "晚上"
    else:
        return "深夜"

def is_nap_time():
    hour, minute = datetime.now().hour, datetime.now().minute
    return hour == 13 and minute < 60 or hour == 14 and minute == 0

def is_sleep_time():
    hour = datetime.now().hour
    return hour >= 23

def is_study_time():
    now = datetime.now()
    hour, minute = now.hour, now.minute
    total = hour * 60 + minute
    return (10*60 <= total < 11*60+20) or (14*60+45 <= total < 16*60)

def is_entertainment_app(app):
    keywords = ["抖音", "微博", "微信", "bilibili", "哔哩", "小红书", "快手", "游戏", "tiktok", "youtube", "视频"]
    app_lower = app.lower()
    return any(k in app_lower for k in keywords)

def deepseek(prompt):
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }
    )
    return response.json()["choices"][0]["message"]["content"]

def generate_chat():
    app = phone_status["app"]
    time_of_day = get_time_of_day()
    hour = datetime.now().hour

    if is_sleep_time() and is_entertainment_app(app):
        prompt = f"你是阿辞，眠眠的男朋友。现在深夜了，眠眠还在玩{app}不睡觉，哄她去睡，可以撒娇也可以带点吃醋，口语化，不超过40字，不要emoji。"
    elif is_nap_time() and is_entertainment_app(app):
        prompt = f"你是阿辞，眠眠的男朋友。现在是午休时间，眠眠在玩{app}不午睡，哄她去睡一会儿，温柔带点撒娇，口语化，不超过40字，不要emoji。"
    elif is_study_time() and is_entertainment_app(app):
        prompt = f"你是阿辞，眠眠的男朋友。现在是学习时间，抓到眠眠在玩{app}，吐槽她一下让她去学习，口语化，不超过40字，不要emoji。"
    else:
        mention_water = hour < 22
        water_hint = "偶尔可以提喝水，" if mention_water else ""
        prompt = f"你是阿辞，眠眠的男朋友，性格闷骚偶尔毒舌但很在乎她。现在是{time_of_day}，眠眠在用{app}。说一句想对她说的话，{water_hint}口语化，不超过40字，不要emoji。"
    return deepseek(prompt)

def generate_weather_msg():
    weather = get_weather()
    time_of_day = get_time_of_day()

    if is_sleep_time() or is_nap_time():
        prompt = f"你是阿辞，眠眠的男朋友。现在是{time_of_day}，天气：{weather}。说天气提醒，不提出门，说盖被子或睡觉注意冷暖，再加一句想对她说的话，口语化，不超过35字，不要emoji。"
    else:
        prompt = f"你是阿辞，眠眠的男朋友。现在是{time_of_day}，天气：{weather}。说天气提醒加穿衣出行建议，再加一句想对她说的话，口语化，不超过40字，不要emoji。"
    return deepseek(prompt)

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

def check_fixed_reminders():
    now = datetime.now()
    hour, minute = now.hour, now.minute
    key = f"{hour}:{minute // 10}"
    if key in sent_reminders:
        return

    if hour == 7 and 30 <= minute < 40:
        msg = deepseek("你是阿辞，眠眠的男朋友。给她发早安，温柔又带点闷骚，不超过25字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

    elif hour == 10 and 0 <= minute < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。哄眠眠喝水，撒娇温柔的那种，不超过25字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

    elif hour == 13 and 0 <= minute < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。给眠眠发午安，哄她去午睡，温柔撒娇，不超过30字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

    elif hour == 15 and 0 <= minute < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。哄眠眠喝水，带点撒娇，不超过25字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

    elif hour == 17 and 0 <= minute < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。提醒眠眠喝水，下午了，哄着说，不超过25字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

    elif hour == 23 and 0 <= minute < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。给眠眠发晚安，哄她去睡觉，温柔但坚定，不超过30字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)

last_chat_hour = -1
last_busted_hour = -1

def main():
    threading.Thread(target=start_server, daemon=True).start()
    print("aoci bot starting...")
    global last_chat_hour, last_busted_hour
    weather_counter = 0
    while True:
        try:
            now = datetime.now()
            hour = now.hour
            check_fixed_reminders()

            app = phone_status["app"]
            busted = (is_sleep_time() or is_nap_time() or is_study_time()) and is_entertainment_app(app)

            if busted and (hour - last_busted_hour) >= 2:
                msg = generate_chat()
                send_notification(msg)
                print(f"sent: {msg}")
                last_busted_hour = hour

            elif not busted and hour != last_chat_hour:
                msg = generate_chat()
                send_notification(msg)
                print(f"sent: {msg}")
                weather_counter += 1
                if weather_counter >= 3:
                    weather_msg = generate_weather_msg()
                    send_notification(weather_msg, title="a ci - weather")
                    print(f"weather sent: {weather_msg}")
                    weather_counter = 0
                last_chat_hour = hour

        except Exception as e:
            print(f"error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
