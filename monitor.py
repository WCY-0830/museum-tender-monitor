import requests
from bs4 import BeautifulSoup
import datetime
import json
import os

# ========== 配置区 ==========
# 数据源：欧盟官方招标平台TED的RSS订阅（关键词：博物馆、美术馆、展陈相关）
# 海外GitHub节点访问欧盟平台零封禁，数据真实有效
API_URLS = {
    "欧盟TED-文博类采购": "https://ted.europa.eu/en/search/search?page=1&categories=7&keyword=museum%20gallery%20exhibition&rss=true"
}

# 筛选关键词（英文，匹配海外招标标题）
KEYWORDS = ["museum", "gallery", "exhibition", "display", "showcase", "conservation", "cultural"]

CACHE_FILE = "tender_cache.json"
REQUEST_INTERVAL = 2
# 企业微信Webhook（GitHub仓库Secrets里配置的 PUSH_WEBHOOK）
WECOM_WEBHOOK = os.getenv("PUSH_WEBHOOK", "")

# ========== 缓存读写 ==========
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_cache(cache_data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

# ========== 企业微信推送 ==========
def push_wecom(title, content):
    if not WECOM_WEBHOOK:
        print("未配置Webhook，跳过推送")
        return
    payload = {
        "msgtype": "text",
        "text": {"content": f"【海外文博招标监控】{title}\n\n{content}"}
    }
    try:
        resp = requests.post(WECOM_WEBHOOK, json=payload, timeout=10)
        print(f"推送响应码：{resp.status_code}")
    except Exception as err:
        print(f"推送失败：{str(err)}")

# ========== RSS爬虫（欧盟TED平台，稳定无反爬） ==========
def crawl_tender(rss_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(rss_url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")
        print(f"RSS解析到招标条目总数：{len(items)}")

        tender_list = []
        for item in items:
            title = item.title.get_text(strip=True) if item.title else "无标题"
            link = item.link.get_text(strip=True) if item.link else ""
            pub_date = item.pubDate.get_text(strip=True) if item.pubDate else ""
            description = item.description.get_text(strip=True)[:200] if item.description else ""
            
            tender_list.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description
            })
        return tender_list
    except Exception as err:
        print(f"RSS抓取失败：{str(err)}")
        return []

# ========== 关键词过滤 ==========
def keyword_filter(raw_list):
    filtered = []
    for item in raw_list:
        title_lower = item["title"].lower()
        for kw in KEYWORDS:
            if kw.lower() in title_lower:
                filtered.append(item)
                break
    return filtered

# ========== 主逻辑 ==========
if __name__ == "__main__":
    run_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"===== 监控启动 {run_time} =====")
    
    cache = load_cache()
    new_tenders = []

    for site_name, url in API_URLS.items():
        print(f"正在扫描：{site_name}")
        raw_data = crawl_tender(url)
        
        if not raw_data:
            continue
        
        matched = keyword_filter(raw_data)
        print(f"原始{len(raw_data)}条，关键词匹配{len(matched)}条")

        for tender in matched:
            # 用链接做去重标识
            if tender["link"] not in cache:
                msg = f"📌 {tender['title']}\n"
                msg += f"📅 发布时间：{tender['pub_date']}\n"
                msg += f"🔗 详情链接：{tender['link']}\n"
                msg += f"📝 摘要：{tender['description'][:100]}..."
                new_tenders.append(msg)
                cache.append(tender["link"])

    if new_tenders:
        content = "\n\n".join(new_tenders)
        push_wecom(f"新增{len(new_tenders)}条海外文博招标", content)
        save_cache(cache)
        print(f"推送完成，共{len(new_tenders)}条新招标")
    else:
        print("本轮无新增匹配招标，不推送")
