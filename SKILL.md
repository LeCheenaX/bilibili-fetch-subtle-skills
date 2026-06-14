---
name: bilibili-subtitle-hybrid
description: B站字幕获取 — 三路径：①API+SESSDATA+内容验证(最快~0.25s) ②Kedou浏览器(无需登录,~35s/P) ③本地Whisper(CPU~实时×1.3,最后手段)
---

# B站视频字幕混合获取方案 (BiliSub-Hybrid)

## 登录凭据

B站登录凭据（SESSDATA、buvid3）存于 Netscape cookie 文件：`/tmp/bilibili_netscape.txt`（由 yt-dlp 生成）。使用前从该文件读取，格式为标准 Netscape HTTP Cookie File。API调用时注入 Cookie header：`Cookie: SESSDATA=xxx; buvid3=xxx`。

## 重试参数

| 参数 | 值 | 说明 |
|------|----|------|
| 最大重试次数（API路径） | **5次/分P，严格固定，不得减少** | 满5次且全部失败后才能跳过该P，记入跳过列表 |
| 重试间隔 | **3秒，严格固定，不得缩短** | 每次API调用之间必须等待3秒，用 `time.sleep(3)` |
| 内容验证方式 | 检查 `body[0].content` 含该P关键词 | 不匹配视为失败 |
| 跳过记录文件 | `/tmp/bilibili-subtitles/{BV号}/.skipped.json` | 记录分P号、失败原因、时间戳 |

## 实测耗时基准

| 路径 | 单P耗时 | 说明 |
|------|---------|------|
| 浏览器 DevTools 操作（打开网页→播放→抓取→下载） | **~40s** | 固定开销，与视频时长无关。调度器中记为"API"通道 |
| API 请求 + 验证 + SRT 保存 | **~0.25s/次** | 每次请求+下载+验证，不经过浏览器 |
| Kedou 云端提取 | **~35s/P** | 固定开销，与视频时长无关 |
| Whisper base 转写 (CPU) | **~实时×0.8~1.5** | 本机CPU上远慢于预期，813s视频~17min；仅短≤200s视频可快速完成，长视频需放后台(~实时×1.3) |
| Whisper small 转写 (CPU) | **~实时×1**（实测远慢于估算） | 340s视频300s+未完成；仅在base精度不够且时间充裕时用 |

## 触发条件

**本 skill 是 B站字幕获取的主入口。** 用户发送B站链接要求"学习""总结""获取字幕"时，**必须先加载本 skill，绝对不允许不加载skill就自己开始做** — 用户已为此骂过多次。

用户要求爬取/下载/获取以下任意内容的字幕/文本时：
- B站视频（单个、多分P、合集/系列）
- BV号或B站URL（含 `bilibili.com/video/BV`）
- "爬字幕"、"下载字幕"、"提取字幕"、"获取文本内容"
- "学习一下这个视频"、"总结这个视频"（需要字幕做素材）

**执行流程**：
1. 先 `skill_view(name='bilibili-subtitle-hybrid')` 加载本skill
2. 读取skill中的流程和约束
3. 然后再开始执行任务

**禁止行为**：
- ❌ 不加载skill直接开始操作
- ❌ 自己猜测流程而不读skill
- ❌ "我觉得应该这样做"而不按skill规定的流程

## ⚠️ 首要原则：用户指示优先于 skill 流程

**用户的直接指令永远优先于本 skill 的任何流程。** 尤其在以下场景：

1. **用户给了具体的方法（如"用浏览器 devtools"、"用某个网站"）→ 优先按用户说的做**，不要自创 API 调用方案。用户不需要你发明替代方案。本 skill 的各个路径只是备选方案。
2. **用户说"跳过"或"不要乱试"→ 立即停。** 除非用户给了新指示，否则不要擅自尝试其他方案。
3. **用户问"为什么"→ 先解释原因再继续，不要埋头干。** 尤其是长时间操作（Whisper 转写、Kedou 提取）前，先告诉用户要做什么、大概多久。
4. **用户给了 URL 或工具 → 先试用户给的。失败后再汇报，等用户指示下一步。** 不要自己判断"这个不行"然后换方案。
5. **长时间任务提前报知。** Whisper 转写等预计超过 2 分钟的任务，先说明预计时长、用的什么模型、为什么选这个模型，得到确认后再启动。

用户在本会话中明确纠正过的行为（永不再犯）：
- ❌ 用 CID API 直接请求字幕而没有用用户指定的方法
- ❌ 把自创的 curl API（`x/player/v2?subtitle=1`）当成正确路径写入成功案例——**浏览器 DevTools 方法才是正确的**
- ❌ 被 Cloudflare 拦截后不解释原因就直接尝试其他方案
- ❌ 运行中的 Whisper 任务直接停掉换模型，没等用户决定
- ❌ 对同一问题试多个方案不逐个汇报结果
- ❌ **未经用户明确说「更新skills」就自己动手改 skill 文件。** 用户只说"总结"就只总结汇报，等用户自己说要更新再动手。这是红线。
- ❌ **API 重试不足 5 次就放弃换通道。** skill 写死 5 次/分P 就不能用 3 次。必须跑满 5 次 × 3 秒间隔，全错才换通道。
- ❌ **不跑调度脚本（allocate.py）就手动分配通道。** 哪怕只有一集也必须跑脚本，不得自己脑补走哪条路。
- ❌ **拿了串台字幕就直接总结，没有先验证内容是否匹配视频标题。** 以后每次API获取的字幕，必须先用 body[0].content 和视频标题关键词做对比验证。如果用户基于错误字幕提问，必须先承认错误再重新总结。
- ❌ **对自己之前获取的"缓存"数据不加验证就直接复用。** 即使是同一CID之前取到过，下次请求仍可能串台。每次API调用都必须独立验证内容，不能信任缓存。

### 默认执行原则

当用户没有给出具体指示时，按本 skill 的流程执行：
- P ≤ 4 → 纯 Kedou
- P > 4 → 混合调度（必须跑 allocate.py）
- 有官方字幕 → 直接下载
- **API 重试：严格 5 次/分P × 3秒间隔，不得自行减少**
- **调度决策：必须跑 allocate.py 脚本，不得手动分配**

### 风格红线
1. **不要评价下载结果**。SRT 下载成功就是完成，不需要说"正确""内容看起来不错"。
2. **严格顺序执行**。Kedou 一次只做一个 P → 保存 → 下一 P。严禁一次性提交多个 URL。
3. **复合任务用 todo 跟踪**。3步以上的任务先设 todo 列表，完成后更新。
4. **复杂任务完成后整理失败/成功经验**，反过来修正相关 skill。这是流程的一部分。
5. **术语注意：用户说"下载脚本"时，"脚本"指字幕文件（.srt transcript），不是代码脚本。** 用户对此混淆发过火，务必区分上下文。

## ⚠️ 关键警示（先读，否则会犯错）

### 1. Kedou 字幕提取路径和视频下载路径不同

| 用途 | URL | 特点 |
|------|-----|------|
| **字幕提取（正确）** | `https://www.kedou.life/caption/subtitle/bilibili` | 每日约8-10次ASR提取额度，按钮是"提取" |
| 视频下载（错误） | `https://kedou.life/`（主页） | 每天免费 2 次，按钮是"开始" |

**绝对不要**去主页 `/` 提取字幕。主页是视频下载页，有每日配额限制。字幕提取页没有配额限制。

### ⚠️ Kedou 每日总配额限制（实测 2026-06-08）

字幕提取页同样有每日总请求数限制。超出后返回提示：
```
您今日的使用次数已达上限，请明天再试！
```
**大约每日可提取 ~20次**（与视频长短无关），次日凌晨 UTC+8 重置。如果一批任务超过 20 个 P，需要分天完成，或者改用 yt-dlp + whisper 本地路径。

触发限制后 Pinia store 的 `subtitleExtractInfo` 字段全部为空字符串（`status: ""`, `title: ""`, `subtitleItemVoList: undefined`），**不会**返回 530 错误——所以空结果不等于无字幕，要先检查是否触达上限。

### 2. Kedou 字幕提取页操作详解（自含，不依赖外部 skill）

**页面 URL:** `https://www.kedou.life/caption/subtitle/bilibili`
**目标按钮:** 按钮文字为"**提取**"（不是主页的"**开始**"）

**Pinia Store 数据结构（解析成功后）：**
```javascript
window.__NUXT__.pinia.captionStore  // 全局状态
  .inputUrl                          // 当前输入的 URL（可写）
  .subtitleExtractInfo               // 字幕提取结果
    .vid                             // 视频标识："BVxxx_N"
    .host                            // 平台："bilibili_zm"
    .hostAlias                       // 平台别名："哔哩哔哩"
    .title                           // 字幕文件名："视频名_N.srt"
    .status                          // 状态："解析完成" 或 ""（空=处理中）
    .subtitleItemVoList[]            // 字幕条目列表
      [0].lang                       // 语言："中文"
      [0].langDesc                   // 语言描述："中文"
      [0].content                    // SRT格式字幕全文（字符串）
```

**读取 SRT 内容的两种方式：**
- **方式 A（推荐，最快）**：直接从 Pinia store 读
  ```javascript
  window.__NUXT__.pinia.captionStore.subtitleExtractInfo.subtitleItemVoList[0].content
  ```
- **方式 B（备用，可靠性更高）**：先点击"查看"按钮，再从 textarea 读
  ```python
  browser_click("@查看-ref")
  srt_content = browser_console("document.querySelector('textarea').value")
  ```

**注意事项：**
- 浏览器 session 在空转时会超时断开，每提取完一个 P 后立即保存结果
- 每次操作新 P 前最好重新 `browser_navigate` 到字幕页
- 提取频率无硬性限制，但建议每 P 完成后立即处理再继续下一 P

### 3. Kedou 浏览器操作严格顺序执行

每次只提交一个 URL → 等待解析完成 → 读取结果 → 保存 SRT → 输入下一个 URL。
**严禁一次性提交多个 URL**。这是用户明确要求的约束。

### 4. 三路调度器（走脚本，agent不手动决策）—— 🔴 铁律

**所有调度决策必须走 `scripts/allocate.py`，不得让 agent 手动分配。** 这是用户明确纠正过的红线。

**违反后果：** agent 擅自手动分配（不跑 allocate.py）属于违规操作，用户已明确批评过此类行为。哪怕只有一集要分配，也要跑 allocate.py（传入单元素的 pending 列表），不得自己脑补该走哪条通道。

**调度流程铁律：**
1. 必须先 `python3 scripts/status.py` 读取通道状态
2. 构造包含所有 pending P 的 JSON 输入
3. 调用 `python3 scripts/allocate.py '<JSON>'` 得到分配方案
4. 严格按脚本输出执行，不得擅自变更通道分配

#### 4.1 调度器新格式（三路：API/Kedou/Whisper）

```bash
cd ~/.hermes/skills/media/bilibili-subtitle-hybrid
python3 scripts/allocate.py '<JSON>'
```

JSON 输入格式：
```json
{
  "channels": {
    "api":       {"available": 0|1},
    "kedou":     {"remaining": <int>},
    "whisper_base":  {"exists": 0|1},
    "whisper_small": {"exists": 0|1}
  },
  "running": [
    {"p": <int>, "channel": "kedou"|"base"|"small", "duration": <秒>, "elapsed": <已耗时秒>}
  ],
  "pending": [
    {"p": <int>, "duration": <秒>, "status": "pending"|"retry"|"skipped", "failures": <int>}
  ]
}
```

通道可用性从 `scripts/status.py` 读取，Kedou 配额在每次使用后递减。

#### 4.2 调度器调用格式

```bash
cd ~/.hermes/skills/media/bilibili-subtitle-hybrid
python3 scripts/allocate.py '<JSON>'
```

JSON 输入格式同 4.1 节。当前仅支持新格式（三路），旧二路格式已废弃。

#### 4.3 调度算法核心

通道时间常数：
| 通道 | 单P耗时 | 特性 |
|------|---------|------|
| API (浏览器DevTools) | **40s固定** | 与视频时长无关，串行 |
| Kedou | **35s固定** | 与视频时长无关，串行 |
| Whisper Small | **时长/1**（实测~1×实时） | CPU极慢，慎用 |
| Whisper Base | **时长×1.3** | 实测远慢于早期估算，本机CPU上约实时×0.8~1.5；仅短视频可用，长视频放后台 |

核心策略：**长视频→API/Kedou（固定成本），短视频→Whisper（可变成本，短=便宜）**\n\n```text\n1. 待分配P按时长降序排列\n2. 暴力搜索所有 (api_count, kedou_count) 组合\n3. 最长的api_count个→API，次长的kedou_count个→Kedou，剩余→Whisper\n4. Whisper统一用base，耗时=时长×1.3（实测CPU上远慢于早期估算的时长/6）\n5. 约束：除非API和Kedou都已耗尽，否则Whisper总时长≤max(api总时, kedou总时)\n6. 目标：满足约束下，min(max(api_total, kedou_total, whisper_total))\n```

"已耗尽"定义：API不可用(0) 且 Kedou余量不够覆盖所有待分配视频。

注意：因为Small成本(时长/2.4)通常远高于Kedou(35s)和API(40s)，**仅在API+Kedou无法覆盖所有P时才使用Whisper**。

场景文件：`references/scheduler-scenarios.md`

#### 4.4 执行反馈格式

每次调度（含重调度）后，按以下格式向用户汇报执行状态：

```
三路分配：
  - API:    X 个视频, 预估 ~Ys
  - Kedou:  Y 个视频, 预估 ~Zs
  - Whisper: Z1 Base + Z2 Small, 预估 ~Ws
预估总耗时（取max）：**Ns**
```

预估耗时从调度器输出的 `report` 读取：
- `api.est_time`、`kedou.est_time`、`whisper.est_time`
- `bottleneck` 即为 `max(三路耗时)`

注意：Whisper内 Base 和 Small 共享CPU串行，合并为一条队列上报，时间为两者之和。

#### 4.5 重调度机制

##### 触发条件

以下两种情况触发第二轮调度，不得继续用旧分配方案执行：

1. **API 路线某 P 被跳过**（5次重试失败，标记为 `skipped`）：等 API 当天所有 P 跑完（API 路线空闲后），立即触发重调度。
2. **Kedou 额度意外提前用尽**（实际限制比输入值小）：发现 Kedou 不能再使用时，立即触发重调度。

##### 重调度流程

```text
1. 读取当前状态：
   - channels: API可用性、Kedou 剩余额度、Whisper 模型是否可用
   - running: 尚未完成的任务（Kedou/Whisper 正在跑的P，含已用时elapsed）
   - pending: 被跳过的 P（status=skipped）+ 剩余未被分配的 P
2. 再次调用 allocate.py 做调度
3. 向用户重新汇报三路分配方案和预估总耗时
```

##### 注意事项

- 正在运行的 Kedou/Whisper 任务不中断，继续在后台执行
- 重调度时将这些 running 任务的剩余时间计入新方案
- 若重调度后仍无可行方案（如所有通道均不可用），汇报给用户并给出建议

## 0. 环境检测

当前 skill 目录结构：
```
~/.hermes/skills/media/bilibili-subtitle-hybrid/
├── SKILL.md
├── scripts/
│   ├── allocate.py         # 三路调度器 (API/Kedou/Whisper)
│   ├── status.py           # 状态管理（每日配额、通道可用性）
│   ├── setup_env.sh        # 环境初始化（首次运行）
│   ├── check_env.sh        # 环境检测脚本
│   ├── brotli_fix.py       # brotli兼容补丁
├── models/
│   ├── base.pt             # Whisper base 模型 (139MB)
│   └── small.pt            # Whisper small 模型 (461MB)
├── venv/                   # Python 虚拟环境
├── references/             # 参考文档（API验证、场景测试等）
└── biliSub/                # 克隆的字幕项目
    └── enhanced_bilisub.py
```

### 0.0 状态管理（每日配额）

每次使用前（或在每日首次调用时）运行状态检测，自动重置配额：

```bash
# 查看当前状态（自动重置过期数据）
python3 ~/.hermes/skills/media/bilibili-subtitle-hybrid/scripts/status.py

# 消耗 Kedou 配额
python3 ~/.hermes/skills/media/bilibili-subtitle-hybrid/scripts/status.py use-kedou <数量>
```

状态文件路径：`~/.hermes/credentials/bilibili-subtitle-status.json`
格式：`{"date":"2026-06-09","api_available":1,"kedou_remaining":20,"base_exists":1,"small_exists":1}`

### 0.1 检测本地模型和依赖

开始工作前，先执行环境检测：

```bash
bash ~/.hermes/skills/media/bilibili-subtitle-hybrid/scripts/check_env.sh
```

输出示例：
```
✓ venv ready
✓ ffmpeg detected
✓ torch installed
✓ whisper installed
✓ biliSub project cloned
✓ base model exists (139MB)
✗ small model missing (461MB)
```

### 0.2 缺失处理策略

| 缺失项 | 处理方式 | 存储位置 |
|--------|---------|---------|
| venv/deps | 静默自动安装（pip install -r...） | skill目录/venv/ |
| biliSub 项目 | 静默自动 `git clone` | skill目录/biliSub/ |
| base/small 模型 | **先检查** `~/.cache/whisper/` 或 `~/.local/share/whisper/`，有则 `cp` 到技能目录；都没有再**询问用户** → 下载到 skill目录/models/ |
| ffmpeg | 报错提示安装 | 系统级 |

**模型下载函数：**

```python
import whisper

SKILL_DIR = os.path.expanduser("~/.hermes/skills/media/bilibili-subtitle-hybrid")
MODELS_DIR = os.path.join(SKILL_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# 下载到 skill 子目录
whisper.load_model("base", download_root=MODELS_DIR)   # → models/base.pt
whisper.load_model("small", download_root=MODELS_DIR)  # → models/small.pt

# 使用模型时传入 download_root
model = whisper.load_model("base", download_root=MODELS_DIR)
```

### 0.3 brotli 修复（版本依赖性）

brotli 兼容性因 aiohttp 版本而异：
- **aiohttp ≥ 3.14**: brotli 1.1+ 已修复兼容性，`HttpParser._decompress_data` 不存在，**无需修补**
- **aiohttp < 3.14**: brotli 1.0 与 aiohttp 不兼容，需打补丁

setup_env.sh 自动写入 `scripts/brotli_fix.py`，它对两种版本做防御性处理。
在调用 biliSub 前 import 该补丁即可。补丁内容：

```python
import aiohttp.http_parser
if hasattr(aiohttp.http_parser.HttpParser, '_decompress_data'):
    # aiohttp < 3.14: 修补 _decompress_data
    orig = aiohttp.http_parser.HttpParser._decompress_data
    def _patched(self, data):
        try: return orig(self, data)
        except (TypeError, Exception): return b""
    aiohttp.http_parser.HttpParser._decompress_data = _patched
# aiohttp >= 3.14: 无需修补
```

## 1. 获取视频全集信息

```python
from bilibili_api import sync
from bilibili_api.video import Video
from bilibili_api.utils.parse_link import parse_link

# 支持 URL 或 BV 号
video_info, _ = sync(parse_link(url))  # 返回 (Video, ResourceType)
v = video_info if isinstance(video_info, Video) else Video(bvid=bvid)

info = sync(v.get_info())
pages = sync(v.get_pages())
# pages[i] = {"page": N, "part": "标题", "cid": 12345, "duration": 秒}

# 检查 Cookie（biliSub 需要）
credential = Credential(sessdata="mock", buvid3="mock")


**关键字段：** `page`（P序号）、`part`（标题）、`cid`（分P ID）、`duration`（秒）

### ⚠️ URL格式说明

bilibili_api 的 `parse_link` 支持以下URL格式，注意区分：
- **标准BV号：** `https://www.bilibili.com/video/BV1qfEL6XE7g` → 提取BVID
- **b23.tv短链+BV：** `https://b23.tv/BV1qfEL6XE7g` → 同上
- **b23.tv短链+av号（新格式）：** `https://b23.tv/av116718907168519` → av号作为数字字符串传入 `Video(avid=116718907168519)`。注意：av号可能是超长数字（15位），parse_link可以解析但返回的resource_type是字符串av号而非BVID，需要特殊处理
- **标准av号：** `https://www.bilibili.com/video/av116718907168519` → 同上

处理示例：
```python
url = "https://b23.tv/av116718907168519"
video_info, resource_type = sync(parse_link(url))
if isinstance(video_info, Video):
    v = video_info
elif isinstance(resource_type, str) and resource_type.startswith("av"):
    # resource_type 是 "av数字" 字符串
    avid = int(resource_type.replace("av", ""))
    v = Video(avid=avid)
elif isinstance(resource_type, str):  # BVID字符串
    v = Video(bvid=resource_type)
```

## 1.5 ⚠️ 字幕串台检测与纠错流程

### 场景描述

B站AI字幕系统（`x/player/v2?subtitle=1`）可能返回**完全无关视频**的AI字幕内容。这是B站缓存映射不稳定的系统性问题，不是偶然故障。

当出现以下信号时，**必须怀疑当前字幕可能串台**：
1. 用户基于字幕内容问了一个问题，但问题中的**人物/事件/关键词**在字幕中完全找不到
2. 字幕开头的内容和视频标题/简介明显不符（如标题讲"发财女孩"，字幕开头是"good good li加me"或"今天来聊聊兴趣"）
3. 用户追问细节时，发现字幕内容与视频简介描述的情节不符

### 纠错流程

```
Step 1: 怀疑
  ┌─ 用户的问题涉及字幕中没有的人物/情节？
  ├─ 字幕开头内容和标题/简介对不上？
  └─ → 怀疑AI字幕串台

Step 2: 验证（浏览器打开视频页）
  browser_navigate("https://www.bilibili.com/video/BVxxx")
  → 查看页面上的视频简介（snapshot中的描述文本）
  → 检查简介中的人物/情节是否与已获取的字幕匹配
  → 若不匹配 → 确认字幕串台

Step 3: 获取正确字幕
  通过 Kedou 浏览器提取（推荐，无需SESSDATA）:
  browser_navigate("https://www.kedou.life/caption/subtitle/bilibili")
  → 粘贴URL → 提取 → 读取Pinia store
  → 保存SRT文件

  或通过浏览器DevTools Network面板抓取:
  F12 → filter "subtitle" → 等待视频播放 → 找到请求 → 查看Response

Step 4: 重新总结
  确认正确字幕已获取后，再基于正确内容回答用户的问题
  ❌ 务必不要用串台字幕回答问题
  ✅ 先承认之前的回答是基于错误字幕，再给出正确分析
```

### 关键教训（2026-06-09实测）

| 现象 | 示例 |
|------|------|
| AI字幕返回完全无关的内容 | 标题"靠小本生意发财的女孩"，字幕返回"兴趣与才华"的个人独白视频 |
| 有SESSDATA仍返回空列表 | `subtitles: []` 但 `need_login_subtitle: true` 仍可能返回0条 |
| 有SESSDATA + 非空列表但串台 | 返回536条中文字幕，但内容是另一个UP主的视频 |
| Kedou正确提取 | 同一视频Kedou提取536条，内容与标题简介完全吻合 |

### 总结前必做验证

在为用户做**任何视频总结**之前，如果字幕来源于B站AI字幕API，必须：
1. 查看视频页面简介，确认字幕首条内容与简介话题一致
2. 如果发现不一致，标记为"串台字幕"，走纠错流程
3. 纠错完成后，先告知用户之前是对错误字幕做的分析，再给出正确总结

用户偏好：总结时要"不丢细节"——需要准确识别视频真实内容，做详细分层总结，不是只看标题抛结论。

## 2. 字幕检测 → 分流（三路优先级）

字幕获取按以下优先级执行，高优先级通道成功则跳过低优先级：

### 2.1 通道一：B站官方AI字幕（优先，最快）

**条件：需提供B站登录凭据 SESSDATA（存于用户个人信息）**

完整工作流脚本见 `references/sessdata-api-workflow.md`。

**API端点：** `x/player/v2?aid=X&cid=Y&subtitle=1`（返回 JSON，CDN 可公开解析）

```python
import requests

SESSDATA = "[从用户个人信息读取]"
buvid3 = "[从用户个人信息读取]"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://www.bilibili.com/video/av{aid}?p={p}",
    "Cookie": f"SESSDATA={SESSDATA}; buvid3={buvid3}"
}

resp = requests.get(
    f"https://api.bilibili.com/x/player/v2?aid={aid}&cid={cid}&subtitle=1",
    headers=headers
)
data = resp.json()
subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
has_ai_subtitle = len(subtitles) > 0
if has_ai_subtitle:
    sub_url = subtitles[0].get("subtitle_url", "")
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    # sub_url 示例：//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/...?auth_key=...
```

**⚠️ 重要陷阱：即使有SESSDATA，API仍可能返回空列表。**
API返回 `subtitles: []` 但 `need_login_subtitle: true` 时，不代表重试能解决。这与视频本身是否有AI字幕有关——不是所有视频都有AI字幕。返回0条且need_login_subtitle=true时，直接回退到Kedou或Whisper，不要反复重试。

**成功案例（实测 p=3）：**
- 无 SESSDATA → 返回 `subtitles: []`
- 有 SESSDATA → 返回 `subtitles: [{subtitle_url: "//aisubtitle.hdslb.com/..."}]`
- CDN `aisubtitle.hdslb.com` 可公开解析，直接下载 JSON 字幕（275条）
- 耗时：~1s（API请求）+ ~0.5s（下载JSON）= 最快通道

**⚠️ 内容验证+重试机制（极其重要）：**
下载到的字幕 **必须验证内容真实性**，因为 `x/player/v2?subtitle=1` 返回的 subtitle_url 可能指向**完全无关的视频**。

```python
import requests
import time

SESSDATA = "[从用户个人信息读取]"
h = {"User-Agent": "Mozilla/5.0", "Cookie": f"SESSDATA={SESSDATA}"}

# 提取视频标题关键词用于验证（从pages获取的part字段）
verify_keywords = ["连接池", "阻塞", "多路复用"]  # 根据实际话题设定

for attempt in range(5):  # 🔴 严格5次，不得减少
    time.sleep(3)          # 🔴 严格3秒间隔，不得缩短
    r = requests.get(f"https://api.bilibili.com/x/player/v2?aid={aid}&cid={cid}&subtitle=1", headers=h)
    subs = r.json()["data"]["subtitle"]["subtitles"]
    if not subs or not subs[0].get("subtitle_url"):
        continue  # 空URL → 重试
    url = subs[0]["subtitle_url"]
    if url.startswith("//"): url = "https:" + url
    r2 = requests.get(url)
    body = r2.json().get("body", [])
    if body and any(kw in body[0]["content"] for kw in verify_keywords):
        break  # ✅ 内容正确
    # ❌ 内容串了，重试
else:
    # 5次都错 → 该P记入skipped，触发重调度
    print("AI字幕5次均未命中正确内容，跳过该P")
```

**实测数据：**
| 分P | 尝试次数 | 命中率 | 说明 |
|-----|---------|--------|------|
| p=3 (注册中心) | 1次 | ✅ 100% | 一次命中 |
| p=9 (连接池) | 2-3次 | ✅ ~50% | 有时返回空URL，有时返回其他视频内容 |
| p=20 (可观测性) | 20+次 | ❌ 0% | 彻底损坏，只能Whisper |

**原因分析：** B站AI字幕系统CID→字幕映射不稳定。每次请求API生成新的 `auth_key`，路由到不同缓存节点。同一视频的某些缓存节点有正确数据，有些没有，有些映射到别的视频。

详细验证方法和错误案例见 `references/ai-subtitle-verification.md`。
重试实证数据见 `references/api-retry-empirical-2026-06-09.md`（ServiceMesh 27集实测，含 P26 第6次才命中的案例）。

**关于浏览器 DevTools 方法（用户指定的正确验证方法）：**
1. 用已登录B站的浏览器打开视频页（`https://www.bilibili.com/video/BVxxx?p=N`）
2. F12 → Network → 过滤 `subtitle` 或 `.json`
3. 等待视频加载/播放 → 查看字幕请求的 Response
4. 浏览器实际使用的接口是 `x/v2/subtitle/web/view`（protobuf），与 `x/player/v2` 不同
5. 该 protobuf 接口返回的 CDN URL 指向 `subtitle.bilibili.com`（无法公开解析）
6. 因此 **生产级自动化仍用 `x/player/v2?subtitle=1` + SESSDATA 方案**

### 2.2 字幕 JSON → SRT 转换

```python
import json

def json_to_srt(json_data):
    """B站字幕 JSON (body格式) 转 SRT"""
    body = json_data.get("body", [])
    srt_lines = []
    for i, item in enumerate(body, 1):
        start = item["from"]
        end = item["to"]
        text = item["content"]
        def fmt(sec):
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        srt_lines.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n")
    return "\n".join(srt_lines)
```

### 2.3 通道二：Kedou ASR（备选，无需登录）

当通道一失败（无AI字幕或API返回空）时使用。

详见 kedou-video-parser skill。

**适用条件：** 视频有中文语音但无B站官方AI字幕
**限制：** 每日约20次配额，次日 UTC+8 重置

### 2.4 通道三：本地 Whisper（最后手段，最慢）

当 Kedou 配额耗尽或无法使用时使用。

**条件：** 需B站 SESSDATA 下载音频（否则 yt-dlp 返回 412），详见 4.2 节

**⚠️ Whisper 直接支持 m4s/m4a/mp4 格式，不需要先转 WAV。** Whisper 内部用 ffmpeg 解码，传原始音频流即可。转WAV浪费额外时间和磁盘空间。

**本机 CPU 实际性能（实测更新 2026-06-12）：**
- Whisper base (139M): ~0.8~1.5× 实时速（813s 视频 ≈ 17min，远慢于早期估算的5.9×）
- Whisper small (244M): ~1× 实时速（估算）
- 早期文档中"~5.9× 实时速"的基准是错误的，实际CPU处理速度接近实时甚至更慢
- **仅≤200s短视频适合用base；长视频务必放后台并做好15+分钟等待的准备**

**限制：** 中断后无法续跑

### 2.5 分级调度（汇总）

调度决策统一走 `scripts/allocate.py`，agent 不手动决策。

```bash
# 1. 读取通道状态
python3 scripts/status.py

# 2. 构造调度输入（pending含各P的duration、retry信息）
python3 scripts/allocate.py '<JSON>' > schedule_result.json
```

参见 **第3节**（三路调度总览）和 **`references/scheduler-scenarios.md`**（9个测试场景）。

## 3. 三路调度总览

调度决策**必须**使用 `scripts/allocate.py` 脚本（三路：API/Kedou/Whisper），agent 不得手动分配。

核心调度逻辑见 **4.3 节**（算法核心）和 **`references/scheduler-scenarios.md`**（9个测试场景）。

### 3.1 调度策略摘要

| 条件 | 策略 | 瓶颈预期 |
|------|------|---------|
| API+Kedou 有额度 | 长视频→API/Kedou(固定成本)，短视频→Whisper(可变)，**Whisper不得为瓶颈** | API 或 Kedou |
| API+Kedou 均已耗尽 | 全部走 Whisper | Whisper |

### 3.2 通道时间常数

| 通道 | 单P耗时 | 特性 |
|------|---------|------|
| API (浏览器DevTools) | **40s固定** | 与视频时长无关，串行 |
| Kedou | **35s固定** | 与视频时长无关，串行 |
| Whisper Small | **时长/1**（实测~1×实时） | CPU极慢，慎用 |
| Whisper Base | **时长×1.3** | 实测远慢于早期估算，本机CPU上约实时×0.8~1.5；仅短视频可用，长视频放后台 |
| Whisper Base | **时长×1.3** | 实测远慢于早期估算，本机CPU上约实时×0.8~1.5；仅短视频可用，长视频放后台 |
### 3.3 Whisper CPU 性能实测算（本机无 GPU）\n\n| 模型 | 实时倍率 | 例 | 字覆盖率 |\n|------|---------|-----|---------|\n| Base (139M) | ~0.8~1.5×（实测远慢于早期估算） | 813s视频~17min，740s视频~25-40min | 87% |\n| Small (244M) | **~1×（实测远慢于估算）** | 340s视频300s+未完成 | 93% |\n\n⚠️ **重要更新：** 早期文档中base模型~5.9×实时速的估算是错误的。实际CPU运行时，base模型处理速度约为实时速的0.8~1.5倍（即听13分钟的音，需要13-17分钟转写）。small模型约1×实时速（340s视频300s+未完成，更慢）。**base模型仅推荐用于≤200s短视频；长视频必须放后台（timeout=7200）并做好等待15+分钟的准备。**\n\nWhisper 中断后无法续跑。超过5分钟的视频放后台（`background=true, notify_on_complete=true, timeout=7200`）。

详见 `references/timing-benchmark.md`。

## 4. 三路并行执行

根据调度器输出，三路可同时运行（API、Kedou、Whisper 互不干扰）：

- **API 路径**：浏览器 DevTools → Network 面板抓取字幕 JSON → 下载 SRT（~40s/P，串行）
- **Kedou 路径**：Kedou 浏览器提取（~35s/P，串行，有每日20次配额）
- **Whisper 路径**：yt-dlp/__playinfo__ 下载音频 → 本地转写（时限/6 ~ 时长/2.4，串行）

三条路径均可独立并行。瓶颈 = max(api_total, kedou_total, whisper_total)。

### 4.1 Kedou 浏览器提取（串行，严格顺序）

```python
# 每次处理 kedou_list 中的一个 P
for p in kedou_list:
    url = f"https://www.bilibili.com/video/BV{bvid}?p={p}"
    
    # ⚠️ 步骤 1：每次都导航到字幕提取页（浏览器 session 会超时断开）
    # 不要假设之前的 session 还活着
    browser_navigate("https://www.kedou.life/caption/subtitle/bilibili")
    
    # 步骤 2：填写 URL（注意 ref 编号每次加载可能变化，用 placeholder 定位）
    browser_type("input[placeholder*='请将链接粘贴']", url)  # 或直接用 ref
    
    # 步骤 3：点击"提取"按钮（不是主页的"开始"按钮）
    browser_click("@提取-button-ref")
    
    # 步骤 4：等待解析完成（最长 60s）
    # 通过 Pinia store 检查状态
    # browser_console("window.__NUXT__.pinia.captionStore.subtitleExtractInfo.status")
    # 等待直到 status == "解析完成"
    
    # ⚠️ Pinia store 可能缓存旧 P 的数据，读取前先验证 title 已更新
    # browser_console("window.__NUXT__.pinia.captionStore.subtitleExtractInfo.title")
    # 确认 title 包含当前 P 的编号（如 _4.srt 对 p=4）后再继续
    
    # 步骤 5：读取 SRT 内容
    # 方式 A（推荐，最快）：从 Pinia store 直接读取
    content = browser_console("window.__NUXT__.pinia.captionStore.subtitleExtractInfo.subtitleItemVoList[0].content")
    # 方式 B（备用，可靠性更高）：先点击"查看"，再从 textarea 读
    # browser_click("@查看-ref")
    # content = browser_console("document.querySelector('textarea').value")
    
    # 步骤 6：保存到文件
    # ⚠️ 直接用 write_file 保存完整 content 字符串，不要截断
    # browser_console 返回的 content 是完整 SRT 全文
    # 不要用 heredoc 或手动复制部分内容——write_file 接受完整字符串
    save_to_file(f"/tmp/bilibili-subtitles/P{p:02d}-{title}.srt", content)
    
    # 步骤 7：在进入下一 P 前读取并立即保存，避免浏览器超时丢失数据
```

### 4.2 ⚠️ 本地路径需要 B站 Cookie（重要）

**biliSub 和 yt-dlp 两种本地方案都需要 B站 SESSDATA cookie。** 没有 Cookie 时两种方案都会失败：

| 方案 | 失败方式 | 原因 |
|------|---------|------|
| **biliSub (enhanced_bilisub.py)** | `CredentialNoSessdataException: Credential 类未提供 sessdata 或者为空` | bilibili-api 库需要登录态下载视频流 |
| **yt-dlp** | `HTTP Error 412: Precondition Failed` | B站反爬拦截无 Cookie 的下载请求 |

**获取 SESSDATA 的方法：** 用户在浏览器中登录 B站 → F12 → Application → Cookies → bilibili.com → 复制 SESSDATA 和 buvid3 的值。

### 4.3 本地路径 — 获取 SESSDATA 后

有三种本地方案可选，**优先 yt-dlp + whisper**（biliSub 有已知的 parse_link 多P偏移 bug）。若 yt-dlp 被 412 拦截，改用方案 C。

#### 方案 A（推荐）：yt-dlp 下载音频 + whisper 直接转写

**⚠️ Whisper 直接支持 m4s/m4a/mp4 等音频格式，不需要先转 WAV。** Whisper 内部用 ffmpeg 解码，传原始音频流即可。转WAV浪费额外时间和磁盘空间。

```bash
# 1. 用 SESSDATA 下载音频
yt-dlp \\
  --cookies-from-browser BROWSER \\  # 或 --cookies cookies.txt
  -x --audio-format m4a \\
  -o "/tmp/bilibili-subtitles/{BV号}/{P编号}.m4a" \\
  "https://www.bilibili.com/video/BVxxx?p=N"

# 2. whisper 直接转写（传入 m4a，无需转码）
whisper /tmp/bilibili-subtitles/{BV号}/{P编号}.m4a \\
  --model base \\
  --language zh \\
  --output_format srt \\
  --output_dir /tmp/bilibili-subtitles/{BV号}/
```

#### 方案 B：biliSub (enhanced_bilisub.py)

```bash
cd ~/.hermes/skills/media/bilibili-subtitle-hybrid/biliSub
source ../venv/bin/activate

# 需要先设置 SESSDATA 环境变量或传入 credential 参数
export BILI_SESSDATA="xxx"
export BILI_BUVID3="xxx"

# Phase 1: Base model (all episodes in base_list)
for p in $base_list; do
    python3 enhanced_bilisub.py \
      -i "https://www.bilibili.com/video/BV${BVID}?p=${p}" \
      -o /tmp/bilibili-subtitles \
      --asr-model base --asr-lang zh -f srt
done

# Phase 2: Small model (< 7min videos in small_list)
for p in $small_list; do
    python3 enhanced_bilisub.py \
      -i "https://www.bilibili.com/video/BV${BVID}?p=${p}" \
      -o /tmp/bilibili-subtitles \
      --asr-model small --asr-lang zh -f srt
done
```

#### 方案 C（yt-dlp 412 时替代）：浏览器 __playinfo__ 音频下载

当 yt-dlp 返回 412 Precondition Failed 时，可以通过浏览器获取带完整鉴权的流地址。

**Whisper 直接支持 m4s/m4a/mp4 格式，不需要先转 WAV。** 从 __playinfo__ 下载的 .m4s 文件可以直接传给 whisper：

```javascript
// 1. 在已登录的 B站页面浏览器 console 中执行
const pi = window.__playinfo__;
const audio = pi.data.dash.audio[0];
const fullUrl = audio.baseUrl;  // 包含 e=, deadline=, mid=, buvid=, upsig= 等全部参数
// 备份 URL
const backupUrl = (audio.backupUrl || audio.backup_url || [])[0];
```

```bash
# 2. 用完整 URL 从终端下载（无需额外 cookie）
curl -s -o /tmp/audio.m4s \
  "https://upos-sz-mirrorcos.bilivideo.com/...?e=ig8euxZM2r...&deadline=...&mid=...&upsig=..."
```

**关键点：** 必须使用 `__playinfo__` 中的**完整 URL**（含所有 auth 参数）。仅 baseUrl 的短 URL 会被 CDN 403 拒绝。

#### 方案 D（需视频截图时）：x/player/playurl API 下载视频 + ffmpeg 抽帧

当需要从视频中提取静帧截图（如用于笔记配图）时，使用 `x/player/playurl` API 直接下载视频流，再用 ffmpeg 抽取关键帧。

```python
import requests

SESSDATA = "xxx"
buvid3 = "xxx"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/video/BVxxx",
    "Cookie": f"SESSDATA={SESSDATA}; buvid3={buvid3}"
}

# playurl API 获取视频流
r = requests.get(
    f"https://api.bilibili.com/x/player/playurl?avid={aid}&cid={cid}&qn=32&type=&otype=json&fnver=0&fnval=4048",
    headers=headers
)
video_data = r.json()['data']['dash']['video']
# 选 480p AVC 流 (id=32, codecs=avc1) - 画质够用且文件较小
target = [v for v in video_data if v['id'] == 32 and 'avc1' in v.get('codecs', '')][0]
url = target.get('backupUrl') or target.get('backup_url', [''])[0] or target['baseUrl']

# 备份 URL 可直接用 curl 下载（无需额外 cookie，Referer 足够）
# curl -s -o video.m4s "BACKUP_URL" -H "Referer: https://www.bilibili.com/video/BVxxx"
r2 = requests.get(url, headers=headers, stream=True, timeout=60)
with open('/tmp/video.m4s', 'wb') as f:
    for chunk in r2.iter_content(8192): f.write(chunk)

# ffmpeg 抽帧（时间戳来自 Whisper 字幕分析）
# ffmpeg -ss 00:06:23 -i video.m4s -frames:v 1 -q:v 2 frame_0623.jpg
```

**优势：** 无需打开浏览器；备用 URL 端（upos-sz-*）用 curl 即可下载（加 Referer 头）。21MB 的 480p 视频约 10-30s 下载完成。ffmpeg 解码 h.264 在 CPU 上约 10-30s 抽一张帧。

**命名约定：** `frame_{时间戳MMSS}_{描述}.jpg`（如 `frame_0623_blue_khaki.jpg`）

**关于 B站 CDN 403 的说明：** `x/player/playurl` API 返回的 `baseUrl`（主 CDN）给 curl 直接下会 403，但 `backupUrl`（备用 CDN `upos-sz-*`）通常可下。如果两者都 403，从浏览器 console 用 fetch 获取（浏览器自带鉴权）：`fetch(url).then(r => r.blob()).then(b => console.log('size:', b.size))`。

### 4.4 三路同时启动

```python
# 三路并行：API(浏览器DevTools)、Kedou(浏览器提取)、Whisper(本地转写)
import threading

# API 路径：浏览器 DevTools 逐个抓取
api_thread = threading.Thread(target=run_api_devtools, args=(api_list, bvid))

# Kedou 路径
kedou_thread = threading.Thread(target=run_kedou, args=(kedou_list, bvid))

# Whisper 路径
whisper_thread = threading.Thread(target=run_whisper, args=(base_list, small_list, bvid))

api_thread.start()
kedou_thread.start()
whisper_thread.start()

api_thread.join()
kedou_thread.join()
whisper_thread.join()
```

## 5. 输出约定

- **临时目录：** `/tmp/bilibili-subtitles/{BV号}/`
- **文件命名：** `P{序号:02d}-{标题}.srt`
- **标题处理：** 特殊字符替换为 `_`（`/`, `\\`, `:`, `?`, `"`, `<`, `>`, `|`）

## 6. 视频截图提取（笔记配图用）

当用户要求将视频截图嵌入笔记（如 Obsidian 穿搭笔记中的配色示例图）时，使用方案 D 下载视频流后抽帧：

### 6.1 时间戳定位

根据 Whisper 转录的 SRT/日志确定关键时间戳：
- 视频中具体提到某个 Look 的时间点（如 `03:23.500` → 粉色马甲展示）
- 画面上出现文字标注的时间点（如 `07:44` → 画面写着「大对比·小调和」）

### 6.2 ffmpeg 抽帧

```bash
# 快速抽取（-ss 在 -i 前，基于关键帧，速度快但可能偏差几帧）
ffmpeg -ss 00:06:23 -i video.m4s -frames:v 1 -q:v 2 frame_0623.jpg

# 精确抽取（-ss 在 -i 后，解码到准确帧再抽，速度慢但位置精确）
ffmpeg -i video.m4s -ss 00:06:23 -frames:v 1 -q:v 2 frame_0623_exact.jpg
```

### 6.3 截图命名与存放

```bash
cp frame_0623_blue_khaki.jpg "/home/ubuntu/obsidian-vault/02-Areas/002-生活/_attachments/穿搭色彩搭配-20260612-055623.jpg"
```

命名约定：`{笔记名}-{YYYYMMDD}-{HHMMSS}.jpg`，时间戳为截图对应视频时间。

### 6.4 Obsidian 中嵌入

```markdown
![[穿搭色彩搭配-20260612-055623.jpg]]
```

放在对应文字描述之后，独立一行（不作为列表项）。

### 6.5 视频下载替代路径

若方案 D 的 backupUrl 也 403，可从浏览器 console 用 fetch 下载（浏览器自带 cookie + referer 鉴权）：
```javascript
fetch(videoUrl).then(r => r.blob()).then(b => console.log('size:', b.size))
```

## 7. 完整执行示例

```python
# Step 1: 环境检测
bash scripts/check_env.sh

# Step 2: 获取全集信息
bvid = extract_bvid(url)
pages = get_pages(bvid)  # [{"page":1,"part":"开篇词","duration":527}, ...]

# Step 3: 检测还需提取字幕的P
no_sub_pages = []
for p in pages:
    if not has_subtitle(bvid, p["cid"]):
        no_sub_pages.append({"p": p["page"], "duration": p["duration"]})

# Step 4: 执行三路调度
# 先读取通道状态
status = json.loads(subprocess.run(
    ["python3", "scripts/status.py"], capture_output=True, text=True
).stdout)

schedule_input = {
    "channels": status,
    "running": [],  # 首次调度无running任务
    "pending": [{"p": item["p"], "duration": item["duration"],
                 "status": "pending", "failures": 0}
                for item in no_sub_pages]
}

result = json.loads(subprocess.run(
    ["python3", "scripts/allocate.py", json.dumps(schedule_input)],
    capture_output=True, text=True
).stdout)

# 输出分配方案
api_list = [a["p"] for a in result["assignment"] if a["channel"] == "api"]
kedou_list = [a["p"] for a in result["assignment"] if a["channel"] == "kedou"]
base_list = [a["p"] for a in result["assignment"] if a["channel"] == "base"]
small_list = [a["p"] for a in result["assignment"] if a["channel"] == "small"]

print(f"API: {api_list}, Kedou: {kedou_list}, Base: {base_list}, Small: {small_list}")
print(f"预计瓶颈: {result['report']['bottleneck']}s")

# Step 5: 三路并行执行
run_in_parallel(api_list, kedou_list, base_list, small_list, bvid)

# Step 6: 汇总
# 所有 SRT 在 /tmp/bilibili-subtitles/{BV号}/
print(f"瓶颈: {result['report']['bottleneck']}s — {result['report']['explain']}")
```

## 8. 已知问题

| 问题 | 现象 | 解决 |
|------|------|------|
| **AI字幕内容随机串（B站缓存映射不稳定）** | 每次调用 `x/player/v2?subtitle=1` 返回的 subtitle_url 可能指向其他视频的内容。实测10次：空URL=10%, 错误内容=60%, 正确=30% | **必须验证内容。** 下载后检查 body[0].content 包含该P的关键词，不匹配则重试。单次API请求+验证仅~0.25s |
| **API首次有URL后续全部空（闪烁模式）** | 第1次调用返回 `subtitles: [{subtitle_url: \"//aisubtitle.hdslb.com/...\"}]` 但URL无 `?auth_key=` 参数不可下载。后续5次全部返回 `subtitles: []` | B站映射节点有冷热差异：起始态可能命中一个缓存了过期的stale entry，后续路由到空白节点。遇到此模式直接判定API不可用，走Kedou回退。不需要重试5次后才知道，首次返回无auth_key的空URL即可换通道 |
| **`subtitle.bilibili.com` 无法解析 (NXDOMAIN)** | protobuf 接口 `x/v2/subtitle/web/view` 返回的字幕CDN URL 指向该域名，DNS查不到 | 改用 `x/player/v2?subtitle=1` + SESSDATA 获取 `aisubtitle.hdslb.com` URL（可解析），两个接口返回同份字幕数据 |
| Kedou API 530 | 直接 POST 返回530 | 必须用浏览器操作+读Pinia store |
| **Kedou "解析失败"（新视频未收录）** | Pinia store status="解析失败"，title有值但content为空。不是530，不是配额耗尽 | 视频发布后数小时内Kedou可能尚未收录，ASR无法处理。回退到Whisper本地转写 |
| Pinia store 缓存残旧 | 键入新 URL 后提取，store 仍显示上个 P 的内容（如 title 显示 `_3.srt` 而非 `_4.srt`） | 读取前先检查 title 是否已更新为新 P 编号；若未更新则重试提取或等待几秒 |
| brotli 解压崩溃 | aiohttp 3.14+ 无 _decompress_data | brotli 1.1+ 已修复，防御性补丁见 0.3 |
| biliSub parse_link 多P映射偏移 | 用 ?p=N 参数提交分P URL 时可能映射到错误 P | 用 biliSub 处理多P系列时不要依赖 ?p=N，改用 BV+cid 组合 |
| Whisper 精度 | Base 87%, Small 93% | 关键词可接受，专业术语偶有错 |
| **Whisper 成为调度瓶颈（违反约束）** | 在API/Kedou有可用额度时，调度器分配过多P给Whisper，导致Whisper总时长 > max(api, kedou) | **需遵守调度约束**：除非API和Kedou都已耗尽（API=0 且 Kedou余量不够覆盖全部P），否则Whisper总时长不得超过max(api_total, kedou_total)。`scripts/allocate.py` 已内置此约束检查 | | 输入 URL 点击提取后 Pinia store 的 status/title/content 全部为空，不返回530，不显示 Loading | 检查页面底部 alert 提示「您今日的使用次数已达上限」；确认后次日 UTC+8 重置或改用本地路径 |
| **SRT 保存截断** | browser_console 读取的完整 SRT 在保存时只存了前几十条 | 直接用 write_file 保存 browser_console 返回的完整字符串，不要用 heredoc 或手动复制部分内容 |
| **yt-dlp 被 B站 412 拦截** | 即使有 SESSDATA cookie，`yt-dlp --cookies cookies.txt` 也可能返回 412 | 改用浏览器 `__playinfo__` 方式获取带完整 auth 参数的音频流 URL，或用方案 D（x/player/playurl API 下载视频） |
| 长标题文件名 | 特殊字符导致路径错误 | 正则替换特殊字符为 _ |
| biliSub batch 无输出 | grep 过滤 stdout 导致不显示进度 | 批处理脚本避免 grep 过滤，用 2>&1 输出完整日志 |
| **CPU-only Whisper 极慢** | 无 GPU 时 base 模型约实时×0.8~1.5（813s视频≈17min），small 更慢 | 放后台运行并 notify_on_complete，不要前端阻塞。仅≤200s短视频用base，长视频走 API/Kedou |
| **新视频（发布<24h）三路全失败** | Kedou返回"解析失败"（未收录），API返回空字幕（未处理），只有yt-dlp+Whisper可用 | 新视频的 fallback 路径：yt-dlp下载音频（需SESSDATA）→ Whisper base转写 |
| **Whisper small CPU超时** | small模型实测在CPU上远慢于估算（340s视频300s+未完成） | 即使 ≤400s 视频也优先用base，small仅在精度要求极高且时间充裕时使用 |

## 附录：实测案例汇总（ServiceMesh 27集实战）

以下是本次 27 集字幕提取实战中碰到的所有路径的成功/失败实例。

### 成功案例

#### 案例 S1（推荐路径）：SESSDATA + x/player/v2 → av482622519 p=3
- **条件：** 有 SESSDATA 登录凭据
- **操作：** `curl api.bilibili.com/x/player/v2?aid=482622519&cid=1027675975&subtitle=1 -H "Cookie: SESSDATA=..." `
- **API返回：** `subtitles: [{subtitle_url: "//aisubtitle.hdslb.com/bfs/ai_subtitle/prod/...?auth_key=..."}]`
- **下载：** `https://aisubtitle.hdslb.com/...` → 275条中文SRT ✅
- **耗时：** ~1s（API请求）+ ~0.5s（下载JSON）
- **CDN：** `aisubtitle.hdslb.com` → `aisubtitle.hdslb.com.w.cdngslb.com`（公开可解析）
- **关键发现：** 无 SESSDATA 时该 API 返回空列表；有 SESSDATA 时返回 AI 字幕
- **验证状态：** 第1次命中，内容正确 ✅

#### 案例 S2（推荐路径 + 重试验证）：SESSDATA + x/player/v2 → av482622519 p=9
- **条件：** 有 SESSDATA
- **结果：** 需要重试。第1次返回空URL，第2次命中正确内容（343条，844s）
- **内容验证：** 检查 body[0].content 含"连接池"→ 正确
- **错误案例：** 其他请求返回的内容包含"爹娘"、"音乐"等完全无关话题
- **耗时对比：** API路线 ~3s（含2次重试）vs Whisper base 146s
- **对比Whisper：** 同一视频API 343条 vs Whisper 336条，头尾一致

#### 案例 D：浏览器 DevTools 检测 AI 字幕 → av482622519 p=3
- **正确方法：** 打开B站视频页 → F12 → Network → filter "subtitle" → 等待视频播放 → 找到 `x/v2/subtitle/web/view` 请求 → 查看 Response
- **结果：** protobuf 响应包含 `ai-zh`（AI中文智能字幕）、字幕ID和CDN URL
- **CDN限制：** protobuf 返回 `subtitle.bilibili.com`（NXDOMAIN，无法公开解析）
- **与 S1 对比：** 同一份字幕数据，但 CDN 域名不同。`aisubtitle.hdslb.com` 可公开解析，`subtitle.bilibili.com` 不可
- **结论：** 自动化场景用 S1（API+SESSDATA），手动验证用 D（浏览器 DevTools）

#### ⚠️ 案例 A1~A6（已废弃）：x/player/v2?subtitle=1 API + 重试校验
- **⚠️ 已纠正：** 之前用 `x/player/v2` API 直接 curl 获取 AI 字幕（没有SESSDATA），需要重试3次碰运气——这不是正确方法
- **正确做法：** 带 SESSDATA 调用同一 API，一次成功
- **保留原因：** 记录历史实践，供参考
- **案例 A1：** P18（Ingress/Egress）第3次命中，310条 ✅
- **案例 A2~A6：** P16/P19/P21/P24/P26 各命中，222~267条 ✅

#### 案例 B: Kedou 浏览器提取 → P1-P17（多集）
- **条件：** Kedou 网站可用，配额未耗尽
- **操作：** `browser_navigate("https://www.kedou.life/caption/subtitle/bilibili")` → 粘贴 URL → 点击"提取" → 从 Pinia store 读 SRT
- **结果：** 每 P ~35s，成功提取约 15 集 ✅
- **限制：** 每日约 20 次后配额耗尽

#### 案例 C: `__playinfo__` 音频 + 本地 Whisper base → P20（可观测性）
- **条件：** AI 字幕 API 20次全部串内容，Kedou 配额耗尽
- **操作：** `window.__playinfo__.data.dash.audio[0].baseUrl` → 完整 URL 下载 → `whisper --model base --language zh`
- **结果：** 1036 条 SRT，内容正确 ✅
- **耗时：** CPU base 约 25-40 分钟（后台跑）
- **注意：** Whisper 对技术术语识别有偏差（如 `Istio`→`Instagram`，`Metrics`→`Magic Stress`，`Prometheus`→`ProMios`）

### 失败案例

#### 案例 D1: 自创 CID 请求（无 subtitle=1 参数）
- **操作：** `curl api.bilibili.com/x/player/v2?cid=1027682628`（无 `&subtitle=1`）
- **错误：** 返回 `subtitle_url: ""`（空字符串），以为无字幕
- **原因：** 缺少 `subtitle=1` 参数，B站不返回 AI 字幕 URL
- **解决方案：** 加 `&subtitle=1` 参数

#### 案例 D2: AI 字幕内容随机串 → P18 前2次
- **现象：** 同一 CID 每次请求的 subtitle_url 不同，内容来自无关视频（武侠剧、美食评测、汽车导航）
- **原因：** B站 AI 字幕系统 CID→字幕映射不稳定
- **解决方案：** 严格按 skill 规定：每集最多重试 **5次**（间隔3秒），命中正确内容则保存；5次全错则**跳过该集**，记入跳过列表，继续处理下一集。全部处理完后，汇报哪些集被跳过，并触发重调度
- **重试命中率：** 约 20%~33%（P18 3/5次命中区间，P19 3次命中，P21 2次，P26 4次）

#### 案例 D3: AI 字幕彻底损坏 → P20 20次全失败
- **现象：** 20次重试返回的全是车载导航、健身教程、LOL解说、美食、歌曲歌词等内容
- **原因：** B站对该 CID 的字幕映射已损坏
- **解决方案：** 回退到 `__playinfo__` 音频下载 + 本地 Whisper

#### 案例 D4: Kedou 每日配额耗尽
- **现象：** 提取约 20 次后，Pinia store 的 `status`/`title`/`content` 全部为空，不报错
- **原因：** Kedou 服务端 ASR 每日限额
- **解决方案：** 次日 UTC+8 重置；或改用本地方案

#### 案例 D5: downsub.com Cloudflare 封锁
- **现象：** headless 浏览器卡在 "Performing security verification" 页面
- **原因：** Cloudflare JS 挑战检测到 headless 特征，不颁发令牌
- **解决方案：** 换不需要过 Cloudflare 的站（Kedou）；或用户在自己浏览器操作

#### 案例 D6: yt-dlp 412 Precondition Failed
- **现象：** `yt-dlp --cookies cookies.txt` 返回 HTTP 412
- **原因：** B站 CDN 反爬，检测到非浏览器 User-Agent/Header
- **解决方案：** 禁用 yt-dlp，改用浏览器 `__playinfo__` 获取带完整鉴权的音频 URL

#### 案例 D7: 音频 CDN URL 返回 403/空文件
- **现象：** curl 无参数或仅带 Referer 下载音频 URL 返回 403 或空文件
- **原因：** CDN 需要完整 auth 参数（e, deadline, upsig, mid, buvid 等）
- **解决方案：** 使用 `__playinfo__.data.dash.audio[0].baseUrl` 的完整 URL（含全部参数）

#### 案例 D8: Whisper 无 GPU 极慢
- **现象：** base 模型 740s 视频跑了 300s 还没完（超时）
- **原因：** `torch.cuda.is_available()` = False，纯 CPU 推理
- **解决方案：** 放后台 `background=true, notify_on_complete=true, timeout=7200`；大视频分段处理

#### 案例 D9: 中断运行中的 Whisper 浪费进度
- **现象：** small 模型跑了 4 分钟被 kill 换 base，进度全丢
- **原因：** Whisper 不支持 checkpoint 续跑
- **解决方案：** 除非用户明确说停，否则不要中断正在跑的 Whisper，跑完再评估

#### 案例 D11: API 闪烁模式 — 首次返回URL无auth_key，后续全部空（2026-06-14）
- **现象：** BV1nxJn6yEs4（GraphRAG实践，单集），带SESSDATA调用 API：第1次返回 subtitle URL 但无 `?auth_key=` 参数，直接下载返回空。之后5次重试全部返回 `subtitles: []`
- **原因：** 初始API请求命中了B站缓存节点的stale entry（过期映射记录），URL鉴权参数已过期。后续路由到正常节点，该视频无AI字幕，返回空列表
- **与D2/D3的区别：** D2返回错误内容（串台），D3返回无关内容（彻底损坏），D11返回无auth_key的URL→全空列表
- **识别信号：** 检查 subtitle_url 是否含 `?auth_key=`，无则直接判定API失效，不需下载验证
- **解决方案：** 遇到此模式不需要跑满5次重试，首次返回无auth_key的URL即可判定API不可用，直接走Kedou回退

#### 案例 D10: Kedou "解析失败" — 新视频未收录（2026-06-10）
- **现象：** 视频发布当天（BV1qhE26VEbS，00:27发布），Kedou 3次提取均返回 status="解析失败"，title有值但content为空。不是530错误，不是配额耗尽
- **API验证：** 带SESSDATA调用 `x/player/v2?subtitle=1` 返回 `subtitles: []`，确认视频无AI字幕
- **原因：** 视频太新，Kedou服务端ASR尚未收录处理
- **解决方案：** 回退到Whisper本地转写（`__playinfo__` 下载音频 + whisper --model small）
