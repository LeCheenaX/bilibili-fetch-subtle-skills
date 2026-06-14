# AI字幕内容验证方法

## 为什么需要验证

`x/player/v2?aid=X&cid=Y&subtitle=1` 返回的 subtitle_url 可能指向**完全无关的视频**内容。B站AI字幕缓存节点间的映射不稳定。

实测命中率（p=9, 10次）：
- 空URL（无字幕缓存）：10%
- 错误内容（串到其他视频）：60%
- 正确内容：30%

同一视频的不同 `auth_key` 路由到不同缓存节点，有些节点有正确数据，有些没有。

## 验证方法

下载 subtitle_url 的 JSON 后，检查 `body[0].content` 是否包含该P的关键词：

```python
import requests

SESSDATA = "[从用户个人信息读取]"
verify_keywords = ["连接池", "阻塞", "多路复用"]  # 从pages[].part字段提取

for attempt in range(5):  # 最多5次
    r = requests.get(
        f"https://api.bilibili.com/x/player/v2?aid={aid}&cid={cid}&subtitle=1",
        headers={"User-Agent": "Mozilla/5.0", "Cookie": f"SESSDATA={SESSDATA}"}
    )
    subs = r.json()["data"]["subtitle"]["subtitles"]
    if not subs or not subs[0].get("subtitle_url"):
        continue  # 空URL → 重试
    
    url = subs[0]["subtitle_url"]
    if url.startswith("//"): url = "https:" + url
    r2 = requests.get(url)
    body = r2.json().get("body", [])
    
    if body and any(kw in body[0]["content"] for kw in verify_keywords):
        print(f"Attempt {attempt+1}: 正确! {len(body)}条")
        break
    
    content_preview = body[0]["content"][:30] if body else "empty"
    print(f"Attempt {attempt+1}: 错误内容 \"{content_preview}\", 3s后重试...")
    time.sleep(3)
else:
    print("5次均未命中正确内容，跳过该P")
```

## 关键词提取方法

从获取视频分P信息时的 `part` 字段提取关键词：

```python
# pages = [{"page": 9, "part": "08 连接池：阻塞式连接池和多路复用连接池的差异", "cid": 1027678265}]
import re
part = pages[8]["part"]  # "08 连接池：阻塞式连接池和多路复用连接池的差异"
# 提取关键词：取冒号后的内容，分割出技术术语
content = part.split("：")[-1] if "：" in part else part
# 提取2-6字的词汇作为关键词
words = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]{2,6}', content)
keywords = [w for w in words if w not in ("差异", "实现", "实战")][:4]
# keywords = ["连接池", "阻塞", "多路复用", "复用"]
```

## 正确vs错误内容对比

| 分P | 正确内容开头 | 错误内容示例 |
|-----|-------------|-------------|
| p=9 连接池 | "连接池阻塞式连接池和多路复用连接池的差异" | "爹娘"、"音乐"、"123456刚好"、"出来给我出来" |
| p=18 Ingress/Egress | "第16讲ingress和egress" | 武侠剧、美食评测、汽车导航 |
| p=20 可观测性 | (20+次全失败) | 车载导航、健身教程、LOL解说、美食、歌曲歌词 |

## 验证通过后的操作

```python
def fmt(s):
    h=int(s/3600); m=int((s%3600)/60); sec=int(s%60); ms=int((s-int(s))*1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

srt = [f"{i}\n{fmt(e['from'])} --> {fmt(e['to'])}\n{e['content']}\n" for i,e in enumerate(body,1)]
with open(f"/tmp/bilibili-subtitles/P{p:02d}-{title}.srt", "w", encoding="utf-8") as f:
    f.write("".join(srt))
```
