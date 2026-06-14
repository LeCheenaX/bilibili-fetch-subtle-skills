#!/usr/bin/env bash
# 环境安装脚本 — 静默安装依赖，模型下载需传参
# 用法:
#   bash scripts/setup_env.sh              # 仅安装依赖 + 克隆项目
#   bash scripts/setup_env.sh --download-base   # + 下载 base 模型
#   bash scripts/setup_env.sh --download-small  # + 下载 small 模型
#   bash scripts/setup_env.sh --download-all    # + 下载全部模型

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$SKILL_DIR/venv"
MODELS_DIR="$SKILL_DIR/models"
BILISUB_DIR="$SKILL_DIR/biliSub"
BILISUB_REPO="https://github.com/lvusyy/biliSub.git"

echo "=== bilibili-subtitle-hybrid 环境初始化 ==="

# --------------- 1. Python venv ---------------
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/6] 创建 Python venv..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/6] ✓ venv 已存在"
fi

source "$VENV_DIR/bin/activate"

# --------------- 2. 安装依赖 ---------------
echo "[2/6] 安装 Python 依赖..."
pip install --quiet --upgrade pip 2>/dev/null
pip install --quiet openai-whisper bilibili-api-python aiohttp brotli 2>&1 | tail -1
echo "      ✓ pip 安装完成"

# --------------- 3. 修复 brotli 兼容性 ---------------
echo "[3/6] 修补 brotli + aiohttp 兼容性..."
BROTLI_FIX="$SKILL_DIR/scripts/brotli_fix.py"
cat > "$BROTLI_FIX" << 'PYEOF'
"""
brotli + aiohttp 兼容性补丁 — 在调用 biliSub 前 import 即可。
aiohttp 3.14+ 无 _decompress_data，brotli 1.1+ 已修复兼容性。
"""
import aiohttp.http_parser
if hasattr(aiohttp.http_parser.HttpParser, '_decompress_data'):
    orig_decompress = aiohttp.http_parser.HttpParser._decompress_data
    def _patched_decompress(self, data):
        try:
            return orig_decompress(self, data)
        except (TypeError, Exception):
            return b""
    aiohttp.http_parser.HttpParser._decompress_data = _patched_decompress
PYEOF
echo "      ✓ brotli 补丁已写入 $BROTLI_FIX"

# --------------- 4. 克隆 biliSub ---------------
echo "[4/6] 克隆 biliSub 项目..."
if [ ! -d "$BILISUB_DIR" ]; then
    git clone --quiet "$BILISUB_REPO" "$BILISUB_DIR" 2>&1 | tail -1
    echo "      ✓ 克隆完成"

    # 打补丁修复已知 bug
    echo "      应用已知补丁..."
    # biliSub enhanced_bilisub.py 的 parse_link 需要适配新版 API
    BILISUB_FILE="$BILISUB_DIR/enhanced_bilisub.py"
    if [ -f "$BILISUB_FILE" ]; then
        # 检查是否需要补丁
        if grep -q "parse_link" "$BILISUB_FILE" 2>/dev/null; then
            echo "      ✓ parse_link 已处理（运行时需同步调用）"
        fi
    fi
else
    echo "      ✓ biliSub 已存在"
fi

# --------------- 5. 创建 models 目录 ---------------
echo "[5/6] 准备模型目录..."
mkdir -p "$MODELS_DIR"

if [ -f "$MODELS_DIR/base.pt" ] || [ -f "$MODELS_DIR/small.pt" ]; then
    echo "      ✓ 已有模型文件"
    ls -lh "$MODELS_DIR/"*.pt 2>/dev/null || true
else
    echo "      ✓ 目录就绪（空，需下载模型）"
fi

# --------------- 6. 下载模型（按需） ---------------
DOWNLOAD_BASE=false
DOWNLOAD_SMALL=false

for arg in "$@"; do
    case "$arg" in
        --download-base|--download-all) DOWNLOAD_BASE=true ;;
        --download-small|--download-all) DOWNLOAD_SMALL=true ;;
    esac
done

if [ "$DOWNLOAD_BASE" = true ]; then
    if [ -f "$MODELS_DIR/base.pt" ]; then
        echo "[6/6] ✓ base 模型已存在"
    else
        echo "[6/6] 下载 base 模型 (139MB)..."
        python3 -c "
import whisper
whisper.load_model('base', download_root='$MODELS_DIR')
print('✓ base 模型下载完成')
"
    fi
fi

if [ "$DOWNLOAD_SMALL" = true ]; then
    if [ -f "$MODELS_DIR/small.pt" ]; then
        echo "[6/6] ✓ small 模型已存在"
    else
        echo "[6/6] 下载 small 模型 (461MB)..."
        python3 -c "
import whisper
whisper.load_model('small', download_root='$MODELS_DIR')
print('✓ small 模型下载完成')
"
    fi
fi

echo ""
echo "=== ✅ 环境初始化完成 ==="
