---
name: bilibili-subtitle-hybrid
description: B站视频字幕混合获取 — 环境检测→官方字幕→分级调度，P≤4纯Kedou，P>4混合调度，Small仅用于<7min视频
---

# B站视频字幕混合获取方案 (BiliSub-Hybrid)

## 触发条件

用户要求爬取/下载/获取以下任意内容的字幕/文本时：
- B站视频（单个、多分P、合集/系列）
- BV号或B站URL（含 `bilibili.com/video/BV`）
- "爬字幕"、"下载字幕"、"提取字幕"、"获取文本内容"

## 0. 环境检测

当前 skill 目录结构：
```
~/.hermes/skills/media/bilibili-subtitle-hybrid/
├── SKILL.md
├── scripts/
│   ├── setup_env.sh        # 环境初始化（首次运行）
│   ├── allocate.py         # 混合调度分配器
│   └── check_env.sh        # 环境检测脚本
├── models/
│   ├── base.pt             # Whisper base 模型 (139MB)
│   └── small.pt            # Whisper small 模型 (461MB)
├── venv/                   # Python 虚拟环境
└── biliSub/                # 克隆的字幕项目
    └── enhanced_bilisub.py
```

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
| base 模型 | **询问用户** → 下载 (139MB) | skill目录/models/ |
| small 模型 | **询问用户** → 下载 (461MB) | skill目录/models/ |
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

### 0.3 brotli 修复（单次，首次 setup 自动打补丁）

brotli 1.1+ 与 aiohttp 3.14+ 不兼容，需打补丁：

```python
import aiohttp.http_parser
orig_decompress = aiohttp.http_parser.HttpParser._decompress_data
def patched_decompress(self, data):
    try:
        return orig_decompress(self, data)
    except (TypeError, Exception):
        return b""
aiohttp.http_parser.HttpParser._decompress_data = patched_decompress
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
```

**关键字段：** `page`（P序号）、`part`（标题）、`cid`（分P ID）、`duration`（秒）

## 2. 官方字幕检测 → 分流

### 2.1 检测是否有官方字幕

```python
import requests

resp = requests.get(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}",
                    headers={"User-Agent": "Mozilla/5.0"})
data = resp.json()
subtitle_list = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
has_subtitle = len(subtitle_list) > 0
```

### 2.2 如果有官方字幕 → 直接下载 SRT

```python
if has_subtitle:
    sub_url = subtitle_list[0]["subtitle_url"]
    if not sub_url.startswith("http"):
        sub_url = "https:" + sub_url
    srt_resp = requests.get(sub_url)
    # B站返回 JSON 格式字幕，需转为 SRT
    sub_data = srt_resp.json()["body"]
    # 转换 JSON → SRT (逐条带时间戳)
```

### 2.3 如果无官方字幕 → 分级调度

```python
total_p = len(pages)
if total_p <= 4:
    # 全程 Kedou（P少不值得跑本地）
    # 调用 Kedou 技能逐个提取
else:
    # 执行混合调度
```

## 3. 混合调度算法

### 3.1 基准时间表（实测，CPU推理）

| 通道 | 每P耗时 | 说明 |
|------|---------|------|
| **Kedou** | ~20s（固定） | 与视频时长无关，单批次≤10次 |
| **Whisper Base** | duration / 7 | 速度快，字覆盖率~87%，无时长限制 |
| **Whisper Small** | duration / 2.4 | 精度高(字覆盖率~93%)，**仅用于 <7min(420s) 视频** |

### 3.2 分配算法

使用 `scripts/allocate.py`：

```bash
cd ~/.hermes/skills/media/bilibili-subtitle-hybrid
python3 scripts/allocate.py '[[1,527],[3,523],[4,501],...]' 10
```

**输入：** JSON 格式 `[[P序号, 时长秒], ...]`
**输出：** 三个列表 + 预估耗时报告

**算法核心：**

```
1. 若 N ≤ 4 → 全走 Kedou，跳过算法
2. 按 duration 降序排列所有 P
3. 遍历 k（Kedou 数量）从 max_kedou 向下搜索：
   - 最长 k 个 P 给 Kedou，剩余给本地
   - 本地在 Base（最快）和 Small（< 7min 视频可用）间优化分配
   - 目标：min(|cloud - local|)，优先 cloud > local
4. 选最优 k 输出三路列表 + 预估耗时
```

## 4. 双路并行执行

### 4.1 Cloud 路径（Kedou）

使用 **kedou-video-parser** skill 的浏览器自动化流程，对分配好的 P 逐个提取：

```python
# 伪代码 — 每次处理 kedou_list 中的一个 P
for p in kedou_list:
    url = f"https://www.bilibili.com/video/BV{bvid}?p={p}"
    
    # 步骤 1：导航到 Kedou 页面
    browser_navigate("https://www.kedou.life/caption/subtitle/bilibili")
    
    # 步骤 2：填写 URL
    browser_type("@input-ref", url)
    
    # 步骤 3：点击提取
    browser_click("@extract-button-ref")
    
    # 步骤 4：等待解析完成（检查页面 store）
    # 通过 Pinia store 获取 subtitleExtractInfo.status
    # 等待直到 status == "解析完成"
    # 最长等待 60s
    
    # 步骤 5：读取 SRT 内容
    # subtitleItemVoList[0].content → SRT 文本
    
    # 步骤 6：保存到文件
    save_to_file(f"/tmp/bilibili-subtitles/P{p:02d}-{title}.srt", content)
    
    time.sleep(3)  # 请求间隔
```

### 4.2 Local 路径（Whisper Base → Small）

Base 和 Small 串行处理（先 Base 全部跑完，再 Small 全部跑完）：

```bash
cd ~/.hermes/skills/media/bilibili-subtitle-hybrid/biliSub
source ../venv/bin/activate

# 阶段 1：Base（所有 base_list 中的 P）
for p in $base_list; do
    python3 enhanced_bilisub.py \
      -i "https://www.bilibili.com/video/BV${BVID}?p=${p}" \
      -o /tmp/bilibili-subtitles \
      --asr-model base --asr-lang zh -f srt
done

# 阶段 2：Small（所有 small_list 中的 P）
for p in $small_list; do
    python3 enhanced_bilisub.py \
      -i "https://www.bilibili.com/video/BV${BVID}?p=${p}" \
      -o /tmp/bilibili-subtitles \
      --asr-model small --asr-lang zh -f srt
done
```

### 4.3 Cloud 与 Local 同时启动

```python
# 伪代码 - 同时启动两个路径
import threading

cloud_thread = threading.Thread(target=run_kedou, args=(kedou_list, bvid))
local_thread = threading.Thread(target=run_whisper, args=(base_list, small_list, bvid))

cloud_thread.start()
local_thread.start()

cloud_thread.join()
local_thread.join()
```

## 5. 输出约定

- **临时目录：** `/tmp/bilibili-subtitles/{BV号}/`
- **文件命名：** `P{序号:02d}-{标题}.srt`
- **标题处理：** 特殊字符替换为 `_`（`/`, `\`, `:`, `?`, `"`, `<`, `>`, `|`）

## 6. 完整执行示例

```python
# Step 1: 环境检测
bash scripts/check_env.sh

# Step 2: 获取全集信息
bvid = extract_bvid(url)
pages = get_pages(bvid)  # [{"page":1,"part":"开篇词","duration":527}, ...]

# Step 3: 分流
no_sub_pages = []
for p in pages:
    if not has_subtitle(bvid, p["cid"]):
        no_sub_pages.append((p["page"], p["duration"]))

# Step 4: 分配
if len(no_sub_pages) <= 4:
    # 全走 Kedou
    kedou_list = [p for p, _ in no_sub_pages]
    base_list, small_list = [], []
else:
    # 执行分配
    result = allocate(no_sub_pages, max_kedou=10)
    kedou_list = result["kedou"]
    base_list = result["base"]
    small_list = result["small"]

# Step 5: 并行执行
run_in_parallel(kedou_list, base_list, small_list, bvid)

# Step 6: 汇总
# 所有 SRT 在 /tmp/bilibili-subtitles/{BV号}/
```

## 7. 已知问题

| 问题 | 现象 | 解决 |
|------|------|------|
| Kedou API 530 | 直接 POST 返回530 | 必须用浏览器操作+读Pinia store |
| brotli 解压崩溃 | aiohttp 3.14 + brotli 1.1 | 打猴子补丁（setup_env.sh 自动处理）|
| biliSub parse_link | 返回 tuple 而非 dict | sync(parse_link(url))[0] 获取 Video 对象 |
| Whisper 精度 | Base 87%, Small 93% | 关键词可接受，专业术语偶有错 |
| 长标题文件名 | 特殊字符导致路径错误 | 正则替换 `[\\/:*?"<>|]` → `_` |
