import requests
from bs4 import BeautifulSoup
import time
import datetime
import json
import os
import random

# ========== 配置区（改用低风控公开静态测试页面） ==========
API_URLS = {
    "公开静态测试站点": "https://example.com"
}
# 闲置关键词，测试阶段不会做业务筛选
KEYWORDS = ["测试"]

CACHE_FILE = "tender_cache.json"
REQUEST_INTERVAL = 3
WECOM_WEBHOOK = os.getenv("PUSH_WEBHOOK", "")

# ========== 缓存读写工具（沿用原有逻辑，兼容仓库配置） ==========
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
        "text": {"content": f"【连通性测试推送】{title}\n\n{content}"}
    }
    try:
        resp = requests.post(WECOM_WEBHOOK, json=req_body, timeout=10)
        print(f"推送接口响应码：{resp.status_code}")
    except Exception as err:
        print(f"推送请求出错：{str(err)}")

# ========== 简易爬虫：随机抽取单条页面文本做测试数据 ==========
def crawl_tender(page_url):
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(page_url, headers=req_headers, timeout=20)
        soup = BeautifulSoup(res.text, "html.parser")
        text_blocks = [seg.strip() for seg in soup.body.find_all(string=True) if seg.strip()]
        sample_data = []
        if text_blocks:
            pick_cnt = 1
            picked_items = random.sample(text_blocks, k=pick_cnt)
            for idx, text_content in enumerate(picked_items):
                sample_data.append({
                    "title": f"测试样本{idx+1}：{text_content[:60]}",
                    "link": page_url
                })
        print(f"测试页面解析得到文本片段：{len(text_blocks)}条，随机抽取{len(sample_data)}条")
        return sample_data
    except Exception as err:
        print(f"站点抓取失败：{str(err)}")
        return []

# ========== 空过滤占位（兼容原有调用链路） ==========
def keyword_filter(raw_tender_list):
    return raw_tender_list

# ========== 主执行入口 ==========
if __name__ == "__main__":
    run_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"===== 连通性测试任务启动 {run_time} =====")
    cached_history = load_cache()
    new_items_final = []

    for site_name, target_url in API_URLS.items():
        print(f"正在扫描测试站点：{site_name}")
        raw_data = crawl_tender(target_url)
        matched_data = keyword_filter(raw_data)
        # 增量去重逻辑复用旧代码
        for single in matched_data:
            if single["link"] + single["title"] not in cached_history:
                msg_line = f"▪ {single['title']}\n 来源链接: {single['link']}"
                new_items_final.append(msg_line)
                cached_history.append(single["link"] + single["title"])
        time.sleep(REQUEST_INTERVAL)

    if new_items_final:
        merge_msg = "\n\n".join(new_items_final)
        push_wecom(f"本轮新增{len(new_items_final)}条测试样本", merge_msg)
        save_cache(cached_history)
        print(f"推送完成，本轮推送{len(new_items_final)}条测试数据")
    else:
        print("本轮没有新增测试样本，不发起消息推送")
