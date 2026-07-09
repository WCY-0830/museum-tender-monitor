import requests
from bs4 import BeautifulSoup
import time
import datetime
import json
import os

# ========== 配置区 ==========
# 监控站点：中国政府采购网 关键词搜索结果页
API_URLS = {
    "中国政府采购网-美术馆博物馆": "https://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0&buyerName=&projectId=&pinMu=0&bidType=1&dbselect=bidx&kw=%E7%BE%8E%E6%9C%AF%E9%A6%86+%E5%8D%9A%E7%89%A9%E9%A6%86&start_time=2026%3A01%3A01&end_time=2026%3A12%3A31&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName="
}

# 只推送包含以下关键词的公告，过滤无关信息
KEYWORDS = ["美术馆", "博物馆", "展陈", "展柜", "通柜", "陈列", "布展"]

# 缓存文件名
CACHE_FILE = "tender_cache.json"

# 请求间隔（秒）
REQUEST_INTERVAL = 3

# 从环境变量读取企业微信webhook
PUSH_WEBHOOK = os.getenv("PUSH_WEBHOOK", "")


# ========== 功能函数 ==========
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_cache(cache_data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def send_push_message(title, content):
    if not PUSH_WEBHOOK:
        print("未配置推送webhook，跳过发送")
        return
    payload = {
        "msgtype": "text",
        "text": {
            "content": f"【招标监控】{title}\n\n{content}"
        }
    }
    try:
        requests.post(PUSH_WEBHOOK, json=payload, timeout=10)
        print("推送消息已发送")
    except Exception as err:
        print(f"推送失败: {str(err)}")


def fetch_tender_data(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select(".vT-srch-result-list-bid li")
        tender_list = []
        for item in items:
            a_tag = item.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            link = a_tag["href"]
            tender_list.append({
                "title": title,
                "link": link
            })
        return tender_list
    except Exception as err:
        print(f"站点访问失败 {url}: {str(err)}")
        return None


def filter_by_keyword(tender_list):
    filtered = []
    for t in tender_list:
        for kw in KEYWORDS:
            if kw in t["title"]:
                filtered.append(t)
                break
    return filtered


# ========== 主逻辑 ==========
def main():
    print(f"===== 监控启动 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    cache = load_cache()
    all_new_tenders = []

    for site_name, api_url in API_URLS.items():
        print(f"正在扫描: {site_name}")
        tender_list = fetch_tender_data(api_url)
        if not tender_list:
            time.sleep(REQUEST_INTERVAL)
            continue

        # 关键词过滤
        matched = filter_by_keyword(tender_list)
        print(f"抓到{len(tender_list)}条，关键词匹配{len(matched)}条")

        # 去重
        for tender in matched:
            if tender["link"] not in cache:
                all_new_tenders.append(f"▪ {tender['title']}\n  链接: {tender['link']}")
                cache.append(tender["link"])

        time.sleep(REQUEST_INTERVAL)

    # 有新标就推送
    if all_new_tenders:
        content = "\n\n".join(all_new_tenders)
        send_push_message(f"新增{len(all_new_tenders)}条匹配招标", content)
        save_cache(cache)
        print(f"推送完成，共{len(all_new_tenders)}条新招标")
    else:
        print("暂无新增匹配招标，不推送")


if __name__ == "__main__":
    main()
