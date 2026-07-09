import requests
import time
import json
import os
from datetime import datetime

# ===================== 配置区（自行修改）=====================
# 招标网站接口，后续替换成真实美术馆、博物馆招标数据源地址
API_URLS = {
    "美术馆项目": "https://xxx.com/api/tender/art-museum",
    "博物馆项目": "https://xxx.com/api/tender/museum"
}
# Webhook从仓库密钥读取，不用手动填写
PUSH_WEBHOOK = os.getenv("PUSH_WEBHOOK", "")
# 缓存文件，避免重复推送相同招标消息
CACHE_FILE = "tender_cache.json"
# 两次接口请求的间隔秒数
REQUEST_INTERVAL = 3
# ==========================================================

def load_cache():
    """读取本地缓存记录"""
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cache(cache_data):
    """持久化更新缓存"""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def send_push_message(title, content):
    """向钉钉/企业微信推送提醒"""
    if not PUSH_WEBHOOK:
        print("警告：未配置推送Webhook，跳过消息发送")
        return
    payload = {
        "msgtype": "text",
        "text": {
            "content": f"【博物馆招标监控】{title}\n{content}"
        }
    }
    try:
        resp = requests.post(PUSH_WEBHOOK, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"推送成功：{title}")
        else:
            print(f"推送失败，响应码：{resp.status_code}，返回内容：{resp.text}")
    except Exception as err:
        print(f"推送请求异常：{str(err)}")

def fetch_tender_data(url):
    """拉取站点招标数据"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as err:
        print(f"接口访问失败 {url}：{str(err)}")
        return None

def main():
    send_push_message("测试通知", "流水线运行成功，推送链路正常")
    print(f"===== 监控启动 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    cache = load_cache()
    new_total_count = 0

    for site_name, api_url in API_URLS.items():
        print(f"\n正在扫描站点：{site_name}")
        resp_json = fetch_tender_data(api_url)
        if not resp_json or "list" not in resp_json:
            print(f"{site_name} 没有拿到合法招标列表数据")
            time.sleep(REQUEST_INTERVAL)
            continue

        tender_items = resp_json["list"]
        history_ids = cache.get(site_name, [])
        newly_found = []

        for item in tender_items:
            tender_unique_id = str(item.get("id", ""))
            if tender_unique_id not in history_ids:
                newly_found.append(item)
                history_ids.append(tender_unique_id)

        if len(newly_found) == 0:
            print(f"{site_name} 本轮没有新增招标项目")
            continue

        new_total_count += len(newly_found)
        print(f"{site_name} 检测到 {len(newly_found)} 条新招标条目")
        push_content = ""
        for tender in newly_found:
            push_content += f"""
项目名称：{tender.get('title', '无数据')}
招标编号：{tender.get('code', '无数据')}
截止报名时间：{tender.get('end_time', '无数据')}
项目详情页：{tender.get('detail_url', '无数据')}
——————————————————
"""
        send_push_message(f"{site_name}新增{len(newly_found)}条招标", push_content.strip())
        cache[site_name] = history_ids
        time.sleep(REQUEST_INTERVAL)

    save_cache(cache)
    print(f"\n本轮扫描结束，一共发现 {new_total_count} 条全新招标项目")

if __name__ == "__main__":
    main()
