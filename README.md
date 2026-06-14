# Bilibili Fetch Subtle Skills

B站视频字幕混合获取工具 — 自动检测官方字幕，无字幕时按 P 数分级调度，通过 Kedou 云端 + Whisper 本地并行提取，输出 SRT 文件。

> 本项目为 [Hermes Agent](https://hermes-agent.nousresearch.com) 的 Agent Skill，也可独立作为脚本使用。

---

## 功能特性

- **官方字幕优先** — 自动检测 B 站 API 是否有官方字幕，有则直接下载
- **三级调度策略** — 根据分 P 数量自动选择最优方案
- **云端 + 本地并行** — 双路同时执行，瓶颈时间取 max(cloud, local)
- **Whisper 本地 ASR** — 支持 Base（快速）和 Small（高精度）两档模型
- **自适应分配算法** — 通过贪心搜索最优 K 值，尽可能实现 Cloud > Local

## 决策流程

```
输入 B站 URL
 ├─ 环境检测 → 缺模型？询问后下载
 ├─ 有官方字幕？→ 直接下载 SRT
 ├─ 无字幕且 P ≤ 4 → 纯 Kedou（量小不值得启动本地）
 └─ 无字幕且 P > 4 → 混合调度
      ├─ Kedou 拿最长的 P（固定 ~20s/P，默认 ≤10 次/批）
      └─ 本地并行
           ├─ Base（无时长限制，速度优于精度）
           └─ Small（仅用于 < 420s 视频，精度优于速度）
```

### 基准速度（实测，CPU 推理）

| 通道 | 每 P 耗时 | 字覆盖率 | 说明 |
|------|-----------|----------|------|
| **Kedou** | ~20s（固定） | ~97%+ | 与视频时长无关，单批次 ≤10 次 |
| **Whisper Base** | duration ÷ 7 | ~87% | 无时长限制 |
| **Whisper Small** | duration ÷ 2.4 | ~93% | 仅用于 < 7min (420s) 视频 |

### 分配算法

核心脚本：`scripts/allocate.py`

```bash
python3 scripts/allocate.py '[[P序号, 时长秒], ...]' [max_kedou]
```

对所有可能的 Kedou 分配数 k（从 max_kedou 向下搜索），选择使 `|cloud_time - local_time|` 最小、且优先 `cloud > local` 的方案。

**示例：** 27P 课程（max_kedou=10）

```
Cloud:  Kedou x10 → 200s
Local:  Base x16 → 574s + Small x1 → 33s = 607s
|Cloud - Local| = 407s
瓶颈: 607s  (⚠️  Cloud < Local — 受限于 max_kedou)
```

**示例：** 27P 课程（max_kedou=16）

```
Cloud:  Kedou x16 → 320s
Local:  Base x9 → 240s + Small x2 → 71s = 311s
|Cloud - Local| = 9s  瓶颈: 320s  ✅ Cloud > Local
```

## 安装与使用

### 环境要求

- Python 3.8+
- ffmpeg
- Whisper 模型（Base ~139MB / Small ~461MB）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/LeCheenaX/bilibili-fetch-subtle-skills.git
cd bilibili-fetch-subtle-skills

# 2. 运行环境初始化（安装依赖 + 克隆 biliSub 项目）
bash scripts/setup_env.sh

# 3. 下载 Whisper 模型（按需）
bash scripts/setup_env.sh --download-base    # 下载 Base 模型 (139MB)
bash scripts/setup_env.sh --download-small   # 下载 Small 模型 (461MB)
bash scripts/setup_env.sh --download-all     # 下载全部模型

# 4. 检测环境
bash scripts/check_env.sh
```

### 运行字幕提取

```bash
# 场景一：单 P 或小批量（P ≤ 4）
# → 自动走 Kedou 云端，无需配置模型

# 场景二：多 P 课程
# 1. 先获取分 P 信息
python3 -c "
from bilibili_api import sync
from bilibili_api.video import Video
v = Video(bvid='BV1mT411e7Am')
pages = sync(v.get_pages())
for p in pages:
    print(f\"P{p['page']}: {p['part']} — {p['duration']}s\")
"

# 2. 运行 allocate.py 分配
python3 scripts/allocate.py '[[1,527],[2,680],...]' 10

# 3. 根据分配结果执行
# Kedou 路径：通过浏览器访问 kedou.life 逐 P 提取
# Whisper 路径：使用 biliSub 项目
```

### 在 Hermes Agent 中使用

加载 skill 后，Agent 会自动处理以下流程：

> "帮我爬取这个B站系列的字幕 [URL]"

Agent 执行：环境检测 → 获取全集信息 → 官方字幕检测 → 调度分配 → 双路并行 → 输出 SRT。

## 文件结构

```
bilibili-fetch-subtle-skills/
├── SKILL.md                 # Hermes Agent Skill 文档（完整流程）
├── README.md                # 本文件
├── .gitignore
├── scripts/
│   ├── allocate.py          # 混合调度分配器
│   ├── check_env.sh         # 环境检测脚本
│   └── setup_env.sh         # 环境安装脚本
└── models/                  # Whisper 模型目录（按需下载）
    ├── base.pt              # ~139MB
    └── small.pt             # ~461MB
```

## 致谢

- **[Kedou Life](https://kedou.life/caption/subtitle/bilibili)** — 在线视频字幕提取服务。本项目使用 Kedou 的 Web 前端服务进行云端字幕提取（通过浏览器自动化操作其公开页面，非 API 调用）。
- **[lvusyy/biliSub](https://github.com/lvusyy/biliSub)** — B 站视频字幕下载 + Whisper ASR 工具。本项目在该项目基础上进行了分 P 参数解析修复和 brotli 兼容性修补。
- **[OpenAI Whisper](https://github.com/openai/whisper)** — 通用语音识别模型，用于本地 ASR。
- **[bilibili-api-python](https://github.com/Nemo2011/bilibili-api)** — B 站 API Python 封装。

## 许可证

MIT License
