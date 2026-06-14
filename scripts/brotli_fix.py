"""
brotli + aiohttp 兼容性补丁 — 在调用 biliSub 前 import 即可。

在 aiohttp 3.14+ 中，HttpParser._decompress_data 已不存在，
brotli 1.1+ 已修复了与 aiohttp 的兼容性问题。
此补丁对不同版本做防御性处理。
"""
import aiohttp.http_parser

# aiohttp < 3.14: 需要修补 _decompress_data
if hasattr(aiohttp.http_parser.HttpParser, '_decompress_data'):
    orig_decompress = aiohttp.http_parser.HttpParser._decompress_data
    def _patched_decompress(self, data):
        try:
            return orig_decompress(self, data)
        except (TypeError, Exception):
            return b""
    aiohttp.http_parser.HttpParser._decompress_data = _patched_decompress
else:
    # aiohttp >= 3.14: 解压在 client 层处理，无需修补
    pass
