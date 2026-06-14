# SESSDATA + x/player/v2 JSON API 字幕下载

## 背景

B站 AI 智能字幕可通过两个接口获取：

| 接口 | 格式 | CDN | DNS | 备注 |
|------|------|-----|-----|------|
| `x/v2/subtitle/web/view` | Protobuf | `subtitle.bilibili.com` | NXDOMAIN ❌ | 浏览器播放器实际使用，但CDN不可解析 |
| `x/player/v2?subtitle=1` | JSON | `aisubtitle.hdslb.com` | ✅ 可解析 | 需SESSDATA登录，返回相同字幕数据 |

两个接口使用相同的字幕ID和字幕内容，只是CDN主机不同。`aisubtitle.hdslb.com` 是工作路径。

## 前置条件

- B站 SESSATA cookie（存于 memory target=user）
- aid（视频系列ID）和 cid（分P ID）

## 完整操作流程

### 步骤1：获取全集分P信息

```bash
curl -s "https://api.bilibili.com/x/web-interface/view?aid=482622519" \
  -H 'User-Agent: Mozilla/5.0' | python3 -c "
import json, sys
d = json.load(sys.stdin)['data']
print(f\"Title: {d['title']}\")
print(f\"AID: {d['aid']} BVID: {d['bvid']}\")
for p in d['pages']:
    print(f\"  P{p['page']}: cid={p['cid']} dur={p['duration']}s {p['part']}\")
"
```

### 步骤2：对每个分P调API获取字幕URL

```bash
AID=482622519
CID=1027675975
SESSDATA="your_sessdata_here"
BUVID3="your_buvid3"

curl -s "https://api.bilibili.com/x/player/v2?aid=${AID}&cid=${CID}&subtitle=1" \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  -H 'Referer: https://www.bilibili.com/video/av${AID}?p=3' \
  -H "Cookie: SESSDATA=${SESSDATA}; buvid3=${BUVID3}" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
subs = d['data']['subtitle']['subtitles']
for s in subs:
    print(f\"ID={s['id']} lang={s['lan']}({s['lan_doc']}) url={s['subtitle_url']}\")
"
```

API返回示例：
```json
{
  "allow_submit": false,
  "subtitles": [{
    "id": 1168214173574924032,
    "lan": "ai-zh",
    "lan_doc": "中文",
    "subtitle_url": "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/...?auth_key=..."
  }]
}
```

### 步骤3：下载字幕JSON并转为SRT

```bash
# 下载
curl -s "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/4826225191027675975ca2bc81e145f390edcedf0fd1e128b6c?auth_key=..." \
  -H 'User-Agent: Mozilla/5.0' \
  -o /tmp/p3_subtitle.json

# 转SRT
python3 << 'PYEOF'
import json
with open('/tmp/p3_subtitle.json') as f:
    data = json.load(f)
body = data.get('body', [])
print(f"字幕条目数: {len(body)}")
srt_lines = []
def fmt_ts(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
for i, item in enumerate(body, 1):
    start = fmt_ts(item['from'])
    end = fmt_ts(item['to'])
    srt_lines.append(f"{i}\n{start} --> {end}\n{item['content']}\n")
with open('/tmp/p3.srt', 'w', encoding='utf-8') as f:
    f.writelines(srt_lines)
print("SRT saved to /tmp/p3.srt")
PYEOF
```

## 与浏览器 DevTools 方法的关系

两种方法互为补充：

| 场景 | 推荐方法 |
|------|---------|
| 用户在自己浏览器操作 | F12 → Network → filter "subtitle" → 查看 `x/v2/subtitle/web/view` Response |
| 自动脚本/批量处理 | SESSDATA + `x/player/v2?subtitle=1` → `aisubtitle.hdslb.com` 下载 |

## 已知问题

1. **auth_key 有时效性**：字幕URL中的 auth_key 有时间限制，过期后需要重新调API获取新URL
2. **内容串问题**：`x/player/v2` 偶发返回其他视频的字幕URL（B站后端映射不稳定），需验证 `body[0].content` 含目标视频关键词
3. **wbi/v2 接口**：`x/player/wbi/v2` 需要WBI签名参数（wts、w_rid），更稳定但不易用curl直接调用

## 实测数据（2026-06-08, av482622519 p=3）

- AID: 482622519, CID: 1027675975
- 字幕类型: ai-zh (AI中文智能字幕)
- 字幕条目: 275条
- 时长: 733秒
- 内容: "注册中心微服务重中之重" 到 "我们下一讲再见"
