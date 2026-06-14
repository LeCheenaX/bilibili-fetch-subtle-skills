# 浏览器 DevTools 抓取 B站字幕（F12 Network 方法）

## 适用条件

- B站有 **AI 智能字幕**（播放器字幕面板显示"登录可享"）
- 或 **上传者字幕**（播放器面板直接可选）
- 需要 **已登录 B站** 的浏览器环境（SESSDATA）

**不适用于**连 AI 字幕都没有的视频（面板显示"暂无字幕"且没有"登录可享"）。

## 操作步骤

1. 在已登录 B站的 Chrome/Edge 中打开目标视频
   - 单 P：`https://www.bilibili.com/video/BVxxx`
   - 多 P 指定分P：`https://www.bilibili.com/video/BVxxx?p=N`

2. 按 **F12** 打开开发者工具，切换到 **Network（网络）** 面板

3. 在过滤框中输入 `subtitle` 或 `.json`

4. **刷新页面（F5）或等待视频加载** — AI字幕可能需要视频开始播放后才触发请求

5. 观察出现的网络请求，找到包含字幕数据的请求：

   | 端点 | 格式 | CDN | 说明 |
   |------|------|-----|------|
   | `x/v2/subtitle/web/view?oid=X&pid=Y&type=1` | Protobuf | `subtitle.bilibili.com` (NXDOMAIN) | **浏览器实际使用的接口**，可靠性高 |
   | `x/player/v2?aid=X&cid=Y&subtitle=1` | JSON | `aisubtitle.hdslb.com` (可解析) | 备选，需SESSDATA，可自动下载 |

6. 对于 protobuf 格式：在 Network 面板点击该请求 → **Response** 标签 → 查看二进制数据
   - 内容包含字幕 ID、语言（如 `ai-zh`）和 CDN URL
   - CDN URL 无法从服务器端直接解析，需在登录的浏览器中访问

7. 对于 JSON 格式：复制 Response 中的 `body[]` 数据，编程转为 SRT：
   ```python
   import json
   data = json.loads(json_text)
   srt_lines = []
   for i, item in enumerate(data["body"], 1):
       def fmt(sec):
           h = int(sec // 3600)
           m = int((sec % 3600) // 60)
           s = int(sec % 60)
           ms = int((sec - int(sec)) * 1000)
           return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
       srt_lines.append(f"{i}\n{fmt(item['from'])} --> {fmt(item['to'])}\n{item['content']}\n")
   srt_content = "\n".join(srt_lines)
   ```

## 两个接口的区别

| | `x/v2/subtitle/web/view` | `x/player/v2?subtitle=1` |
|---|---|---|
| **格式** | Protobuf（二进制） | JSON |
| **CDN** | `subtitle.bilibili.com` | `aisubtitle.hdslb.com` |
| **CDN可解析** | ❌ NXDOMAIN | ✅ `aisubtitle.hdslb.com.w.cdngslb.com` |
| **需要SESSDATA** | 是（API本身需要） | 是（返回JSON数据需要） |
| **内容串问题** | 无（返回即确权） | 偶发（需验证内容关键词） |
| **curl可用** | ❌ 难以解析protobuf | ✅ 返回标准JSON |

**关键发现：** 两个接口返回相同字幕数据（同字幕ID `1168214173574924032`），只是CDN主机和格式不同。浏览器播放器使用 protobuf 接口，但 `subtitle.bilibili.com` 域名不对外公开解析。如需自动下载，用 `x/player/v2?subtitle=1` + SESSDATA 获取 `aisubtitle.hdslb.com` URL。

详见 `references/sessdata-subtitle-download.md`。

## 注意事项

- 如果 Network 面板过滤 `subtitle` 没有结果，尝试过滤 `json` 或查看所有请求的 Response
- B站可能使用 WBI 签名或带时间戳的 URL，每次刷新都会变化
- 多 P 视频需要切换分P后再次刷新页面
- protobuf 响应中的 `subtitle.bilibili.com` URL 可能包含混入的二进制字节（protobuf编码残余），在浏览器 Network 面板中查看会很混乱
