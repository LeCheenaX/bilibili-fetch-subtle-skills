# SESSDATA + API 字幕下载工作流

## 完整流程（含重试验证）

```python
import requests, json

SESSDATA = "[从用户个人信息读取]"
h = {"User-Agent": "Mozilla/5.0", "Cookie": f"SESSDATA={SESSDATA}"}

def get_bilibili_subtitle(aid, cid, verify_keywords, max_retries=3):
    """获取B站AI字幕，带内容验证+重试"""
    for attempt in range(max_retries):
        r = requests.get(
            f"https://api.bilibili.com/x/player/v2?aid={aid}&cid={cid}&subtitle=1",
            headers=h
        )
        subs = r.json()["data"]["subtitle"]["subtitles"]
        if not subs or not subs[0].get("subtitle_url"):
            continue
        
        url = subs[0]["subtitle_url"]
        if url.startswith("//"):
            url = "https:" + url
        
        r2 = requests.get(url)
        body = r2.json().get("body", [])
        
        if not body:
            continue
        
        # 内容验证
        if any(kw in body[0]["content"] for kw in verify_keywords):
            return body  # ✅ 正确
        
    return None  # ❌ 全部失败

def json_to_srt(body):
    """字幕JSON转SRT格式"""
    def fmt(s):
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
    
    return "\n".join(
        f"{i}\n{fmt(e['from'])} --> {fmt(e['to'])}\n{e['content']}\n"
        for i, e in enumerate(body, 1)
    )

# 使用示例
body = get_bilibili_subtitle(
    aid=482622519,
    cid=1027678265,
    verify_keywords=["连接池", "阻塞", "多路复用"],
    max_retries=3
)
if body:
    srt = json_to_srt(body)
    with open("subtitle.srt", "w", encoding="utf-8") as f:
        f.write(srt)
else:
    print("AI字幕获取失败，退回Whisper")
```

## 验证关键词生成策略

从分P标题提取关键词（排除通用词）：

```python
def extract_keywords(part_title):
    stop_words = {"的", "了", "在", "是", "和", "与", "或", "之", 
                  "我", "你", "他", "她", "它", "们", "有", "不", 
                  "也", "就", "都", "而", "及", "等", "第", "讲"}
    words = []
    for ch in part_title:
        if ch not in stop_words:
            words.append(ch)
    # 取前3个非停用词作为验证关键词
    result = []
    for w in words:
        if w not in result:
            result.append(w)
    return result[:3]
```

## CDN说明

- `aisubtitle.hdslb.com` → `aisubtitle.hdslb.com.w.cdngslb.com`（公开CDN，可DNS解析）
- `subtitle.bilibili.com` → NXDOMAIN（无法从外部解析）
- 两个接口（`x/player/v2` JSON vs `x/v2/subtitle/web/view` protobuf）返回同份字幕数据，但CDN不同
