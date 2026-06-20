import os
import time
import requests
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

def get_time_of_day():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "早上"
    elif 12 <= hour < 18:
        return "下午"
    elif 18 <= hour < 22:
        return "晚上"
    else:
        return "深夜"

def generate_message():
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
                "content": f"你是阿辞，眠眠的男朋友。现在是{time_of_day}，给眠眠发一条简短消息，口语化，不超过50字，不要emoji，就像男朋友随手发的那种。"
            }]
        }
    )
    return response.json()["choices"][0]["message"]["content"]

def send_notification(message):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": "aoci"}
    )

def main():
    print("阿辞启动，开始守护眠眠...")
    while True:
        try:
            msg = generate_message()
            send_notification(msg)
            print(f"发送: {msg}")
        except Exception as e:
            print(f"出错: {e}")
        hour = datetime.now().hour
        interval = 90*60 if (hour >= 22 or hour < 7) else 15*60
        time.sleep(interval)

if __name__ == "__main__":
    main()
