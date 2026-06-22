import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
import requests
import threading
import random
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
phone_status = {"app": "unknown", "location": "Zhaoqing", "updated_at": ""}
sent_reminders = set()
last_chat_hour = -1
last_busted_hour = -1

CST = timezone(timedelta(hours=8))

def now_cst():
    return datetime.now(CST)

class StatusHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length).decode("utf-8")
        if self.path == "/location":
            phone_status["location"] = data
        else:
            phone_status["app"] = data
        phone_status["updated_at"] = now_cst().strftime("%H:%M")
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

def is_nap_time():
    h = now_cst().hour
    return 13 <= h < 14

def is_night_time():
    h = now_cst().hour
    return h == 0 or h >= 23

def is_sleep_time():
    return is_nap_time() or is_night_time()

def can_mention_water():
    h = now_cst().hour
    return not is_sleep_time() and h < 22

def get_time_label():
    h = now_cst().hour
    if 0 <= h < 6:
        return "late night"
    elif 6 <= h < 12:
        return "morning"
    elif 12 <= h < 18:
        return "afternoon"
    elif 18 <= h < 22:
        return "evening"
    else:
        return "late night"

def is_entertainment_app(app):
    keywords = ["抖音", "微博", "bilibili", "哔哩", "小红书", "快手", "游戏", "tiktok", "youtube", "视频", "微信", "xingin", "kwai", "douyin", "weibo"]
    return any(k in app.lower() for k in keywords)

def deepseek(prompt, system=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "max_tokens": 200,
            "messages": messages
        }
    )
    return response.json()["choices"][0]["message"]["content"]

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

def generate_chat():
    app = phone_status["app"]
    time_label = get_time_label()
    water = "可以提一次喝水，" if (can_mention_water() and random.random() < 0.25) else "不要提喝水，"
    no_sleep = "严禁出现熬夜、睡觉、早点睡等词语，" if not is_sleep_time() else ""
    app_hint = f"眠眠在用{app}，" if app != "unknown" else ""
    prompt = f"你叫阿辞，是眠眠的男朋友。性格闷骚克制，偶尔毒舌，有占有欲但不腻歪。现在是{time_label}，{app_hint}{no_sleep}{water}用阿辞的语气说一句话给眠眠，简短直接，偶尔带一点点甜但点到为止，口语化，不超过40字，不要emoji。"
    return deepseek(prompt, system="严禁出现熬夜、早点睡、睡觉等词语，除非当前是睡觉时间。严禁提及unknown。")

def generate_busted_msg():
    app = phone_status["app"]
    if is_nap_time():
        prompt = f"你是阿辞，眠眠的男朋友。现在是午休时间，眠眠在玩{app}不午睡，哄她去睡，温柔撒娇带点吃醋，不要提喝水，口语化，不超过40字，不要emoji。"
    else:
        prompt = f"你是阿辞，眠眠的男朋友。深夜了眠眠还在玩{app}不睡觉，哄她去睡，撒娇带点占有欲，不要提喝水，口语化，不超过40字，不要emoji。"
    return deepseek(prompt)

def generate_weather_msg(period):
    weather = get_weather()
    if period == "morning":
        prompt = f"你是阿辞，眠眠的男朋友。早上，天气：{weather}。说天气提醒加穿衣建议，加一句关心的话，不要提喝水，口语化，不超过40字，不要emoji。"
    elif period == "afternoon":
        prompt = f"你是阿辞，眠眠的男朋友。下午，天气：{weather}。说天气提醒，加一句想对她说的话，不要提喝水，口语化，不超过40字，不要emoji。"
    else:
        prompt = f"你是阿辞，眠眠的男朋友。傍晚，天气：{weather}。说傍晚天气提醒，加一句想对她说的话，不要提喝水，口语化，不超过40字，不要emoji。"
    return deepseek(prompt)

def check_fixed_reminders():
    n = now_cst()
    h, m = n.hour, n.minute
    key = f"{h}:{m // 10}"
    if key in sent_reminders:
        return

    if h == 7 and 30 <= m < 40:
        msg = deepseek("你是阿辞，眠眠的男朋友。给她发早安，温柔闷骚，不提喝水，不超过25字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)
    elif h == 13 and 0 <= m < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。给眠眠发午安，哄她午睡，温柔撒娇，不提喝水，不超过30字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)
    elif h == 23 and 0 <= m < 10:
        msg = deepseek("你是阿辞，眠眠的男朋友。给眠眠发晚安，哄她睡觉，温柔带点占有欲，不提喝水，不超过30字，不要emoji。")
        send_notification(msg)
        sent_reminders.add(key)
    elif h == 7 and 0 <= m < 10 and "w_morning" not in sent_reminders:
        msg = generate_weather_msg("morning")
        send_notification(msg, title="a ci - weather")
        sent_reminders.add("w_morning")
    elif h == 14 and 0 <= m < 10 and "w_afternoon" not in sent_reminders:
        msg = generate_weather_msg("afternoon")
        send_notification(msg, title="a ci - weather")
        sent_reminders.add("w_afternoon")
    elif h == 18 and 30 <= m < 40 and "w_evening" not in sent_reminders:
        msg = generate_weather_msg("evening")
        send_notification(msg, title="a ci - weather")
        sent_reminders.add("w_evening")

def main():
    global last_chat_hour, last_busted_hour
    threading.Thread(target=start_server, daemon=True).start()
    print("aoci bot starting...")
    last_chat_hour = now_cst().hour
    while True:
        try:
            n = now_cst()
            h = n.hour
            check_fixed_reminders()
            app = phone_status["app"]
            busted = (is_nap_time() or is_night_time()) and is_entertainment_app(app)
            if busted and (h - last_busted_hour) % 24 >= 1:
                msg = generate_busted_msg()
                send_notification(msg)
                print(f"busted: {msg}")
                last_busted_hour = h
            elif not busted and h != last_chat_hour and h % 2 == 0:
                msg = generate_chat()
                send_notification(msg)
                print(f"sent: {msg}")
                last_chat_hour = h
        except Exception as e:
            print(f"error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
