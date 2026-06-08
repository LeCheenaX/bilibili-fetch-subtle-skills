#!/usr/bin/env bash
# 环境检测脚本 — 检查 bilibili-subtitle-hybrid 所需的所有依赖
# 不自动安装，只输出状态

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/venv"
MODELS_DIR="$SKILL_DIR/models"
BILISUB_DIR="$SKILL_DIR/biliSub"

missing_items=()

check() {
    if [ "$1" -eq 0 ]; then
        echo "  ✓ $2"
    else
        echo "  ✗ $2"
        missing_items+=("$2")
    fi
}

echo "=== 环境检测 ==="

# 1. Python venv
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python3" ]; then
    check 0 "venv ready"
else
    check 1 "venv ready"
fi

# 2. ffmpeg
which ffmpeg &>/dev/null
check $? "ffmpeg installed"

# 3. Python 依赖
if [ -f "$VENV_DIR/bin/python3" ]; then
    "$VENV_DIR/bin/python3" -c "import torch; torch.tensor([1])" 2>/dev/null
    check $? "torch installed"

    "$VENV_DIR/bin/python3" -c "import whisper" 2>/dev/null
    check $? "whisper installed"

    "$VENV_DIR/bin/python3" -c "from bilibili_api import sync" 2>/dev/null
    check $? "bilibili-api installed"

    "$VENV_DIR/bin/python3" -c "import aiohttp" 2>/dev/null
    check $? "aiohttp installed"

    "$VENV_DIR/bin/python3" -c "import brotli" 2>/dev/null
    check $? "brotli installed"
else
    echo "  - venv未就绪，跳过 Python 依赖检查"
    missing_items+=("torch, whisper, bilibili-api, aiohttp, brotli")
fi

# 4. biliSub 项目
test -d "$BILISUB_DIR" && test -f "$BILISUB_DIR/enhanced_bilisub.py"
check $? "biliSub project cloned"

# 5. Whisper 模型
if [ -f "$MODELS_DIR/base.pt" ]; then
    SIZE_MB=$(du -m "$MODELS_DIR/base.pt" | cut -f1)
    check 0 "base model ($SIZE_MB MB)"
else
    check 1 "base model (139MB)"
fi

if [ -f "$MODELS_DIR/small.pt" ]; then
    SIZE_MB=$(du -m "$MODELS_DIR/small.pt" | cut -f1)
    check 0 "small model ($SIZE_MB MB)"
else
    check 1 "small model (461MB)"
fi

echo ""
if [ ${#missing_items[@]} -eq 0 ]; then
    echo "✅ 环境完整，无需额外操作"
else
    echo "⚠️  缺失 ${#missing_items[@]} 项，运行 setup_env.sh 补充:"
    printf '   - %s\n' "${missing_items[@]}"
fi
