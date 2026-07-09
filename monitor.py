import requests
from bs4 import BeautifulSoup
import time
import datetime
import json
import os

# ========== 配置区 ==========
# 替换为剑鱼标讯「美术馆、博物馆」关键词检索页（浏览器搜完复制浏览器地址栏链接填入）
API_URLS = {
    "剑鱼标讯-文博类招标": "https://www.jianyu360.cn/search?keyword=美术馆%20博物馆"
}

# 筛选关键词（可按需补充：文博、展馆、展厅、文博展陈）
KEYWORDS = ["美术馆", "博物馆", "展陈", "展柜", "通柜", "陈列", "布展", "文博", "展厅"]

CACHE_FILE = "tender_cache.json"
REQUEST_INTERVAL = 3
# 仓库环境变量读取企业微信机器人地址
WECOM_WEBHOOK = os.getenv("PUSH_WEBHOOK", "")

# ========== 缓存读写工具 ==========
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

# ========== 企业微信消息推送 ==========
def push_wecom(title, content):
    if not WECOM_WEBHOOK:
        print("未读取到Webhook配置，跳过推送")
        return
    req_body = {
        "msgtype": "text",
        "text": {"content": f"【文博招标监控】{title}\n\n{content}"}
    }
    try:
        resp = requests.post(WECOM_WEBHOOK, json=req_body, timeout=10)
        print(f"推送接口响应码：{resp.status_code}")
    except Exception as err:
        print(f"推送请求出错：{str(err)}")

# ========== 网页爬虫（适配剑鱼标讯请求头） ==========
def crawl_tender(page_url):
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.jianyu360.cn/",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    try:
        res = requests.get(page_url, headers=req_headers, timeout=20)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        # 剑鱼标讯通用招标列表选择器，页面结构变动时按需微调
        item_blocks = soup.select(".search-list-item")
        print(f"页面解析识别到招标条目总数：{len(item_blocks)}")

        tender_result = []
        for block in item_blocks:
            title_node = block.select_one(".item-title a")
            if not title_node:
                continue
            item_title = title_node.get_text(strip=True)
            item_link = title_node["href"]
            # 拼接完整域名（页面一般返回相对路径）
            if item_link.startswith("/"):
                item_link = "https://www.jianyu360.cn" + item_link
            tender_result.append({"title": item_title, "link": item_link})
        return tender_result
    except Exception as err:
        print(f"站点抓取失败：{str(err)}")
        return []

# ========== 关键词过滤逻辑 ==========
def keyword_filter(raw_tender_list):
    out_list = []
    for item in raw_tender_list:
        for kw in KEYWORDS:
            if kw in item["title"]:
                out_list.append(item)
                break
    return out_list

# ========== 主执行入口 ==========
if __name__ == "__main__":
    run_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"===== 监控启动 {run_time} =====")
    cached_history = load_cache()
    new_items_final = []

    for site_name, target_url in API_URLS.items():
        print(f"正在扫描站点：{site_name}")
        raw_data = crawl_tender(target_url)
        if not raw_data:
            time.sleep(REQUEST_INTERVAL)
            continue
        matched_data = keyword_filter(raw_data)
        print(f"原始抓取{len(raw_data)}条公告，关键词筛选后剩余{len(matched_data)}条")
        # 增量去重：只推送缓存没存过的新项目
        for single in matched_data:
            if single["link"] not in cached_history:
                msg_line = f"▪ {single['title']}\n 详情链接: {single['link']}"
                new_items_final.append(msg_line)
                cached_history.append(single["link"])
        time.sleep(REQUEST_INTERVAL)

    if new_items_final:
        merge_msg = "\n\n".join(new_items_final)
        push_wecom(f"本轮新增{len(new_items_final)}条匹配招标", merge_msg)
        save_cache(cached_history)
        print(f"推送完成，本轮推送{len(new_items_final)}条招标资讯")
    else:
        print("本轮没有新增符合条件的招标，不发起消息推送")
