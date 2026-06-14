#!/usr/bin/env python3
"""
三路调度分配器 — B站视频字幕混合获取。

输入：JSON 格式的调度请求
输出：分配表 + 各通道预计耗时

核心策略：长视频→API/Kedou（固定成本），短视频→Whisper（可变成本）
目标：最小化 max(api_total, kedou_total, whisper_total)

通道特性：
  - API:     40s/P固定，与视频时长无关
  - Kedou:   35s/P固定，与视频时长无关
  - Small:   duration/2.4，仅做 ≤400s 的视频
  - Base:    duration/6，仅做 >400s 的视频
  - API/Kedou 互不干扰独立运行，Whisper内Small和Base共享CPU串行
"""

import sys
import json

# ========== 时间常数 ==========
API_TIME = 40.0        # s/P, 浏览器DevTools全路径
KEDOU_TIME = 35.0      # s/P, Kedou云端处理
SMALL_SPEED = 2.4      # 实时倍率, 仅≤400s
BASE_SPEED = 6.0       # 实时倍率, 仅>400s
SMALL_MAX_DUR = 400    # Small最大视频时长(秒)


def estimate_whisper_time(duration):
    """估算单个P走Whisper路线的耗时"""
    if duration <= SMALL_MAX_DUR:
        return duration / SMALL_SPEED  # Small模型
    else:
        return duration / BASE_SPEED   # Base模型


def channel_cost(duration, channel):
    """单个P在指定通道的耗时"""
    if channel == 'api':
        return API_TIME
    elif channel == 'kedou':
        return KEDOU_TIME
    elif channel == 'base':
        return duration / BASE_SPEED
    elif channel == 'small':
        if duration > SMALL_MAX_DUR:
            return float('inf')
        return duration / SMALL_SPEED
    return float('inf')


def allocate(data):
    channels = data.get('channels', {})
    running = data.get('running', [])
    pending = data.get('pending', [])

    api_avail = channels.get('api', {}).get('available', 0)
    kedou_remain = channels.get('kedou', {}).get('remaining', 0)
    base_exist = channels.get('whisper_base', {}).get('exists', 0)
    small_exist = channels.get('whisper_small', {}).get('exists', 0)

    # ---- 计算当前各通道的忙碌时间 ----
    def busy_time(ch):
        total = 0.0
        for t in running:
            if t.get('channel') == ch:
                if ch == 'api':
                    eta = API_TIME
                elif ch == 'kedou':
                    eta = KEDOU_TIME
                elif ch == 'base':
                    eta = t['duration'] / BASE_SPEED
                elif ch == 'small':
                    eta = t['duration'] / SMALL_SPEED
                else:
                    eta = 0
                remaining = max(0, eta - t.get('elapsed', 0))
                total += remaining
        return total

    api_busy = busy_time('api')
    kedou_busy = busy_time('kedou')
    # Whisper Base + Small 共享CPU，合并为一条队列
    whisper_running = [t for t in running if t.get('channel') in ('base', 'small')]
    whisper_busy = sum(
        max(0, (t['duration'] / (BASE_SPEED if t['channel'] == 'base' else SMALL_SPEED))
            - t.get('elapsed', 0))
        for t in whisper_running
    )

    # ---- 待分配P按时长降序排列 ----
    sorted_pending = sorted(pending, key=lambda x: x['duration'], reverse=True)
    n = len(sorted_pending)

    # ---- 暴力搜索最优(api_count, kedou_count)组合 ----
    # 对于小规模(n <= 20)，遍历所有可行分配
    best_result = None
    best_max = float('inf')

    max_api_use = n if api_avail else 0  # API通道串行，可用则全部分配
    max_kedou_use = min(kedou_remain, n)

    for api_c in range(0, max_api_use + 1):
        for kedou_c in range(0, max_kedou_use + 1):
            if api_c + kedou_c > n:
                continue

            # 最长的api_c个→API，次长的kedou_c个→Kedou，剩余的→Whisper
            api_ps = sorted_pending[:api_c]
            kedou_ps = sorted_pending[api_c:api_c + kedou_c]
            whisper_ps = sorted_pending[api_c + kedou_c:]

            # 检查Whisper是否需要模型
            whisper_needed = len(whisper_ps) > 0
            if whisper_needed:
                has_small_needed = any(p['duration'] <= SMALL_MAX_DUR for p in whisper_ps)
                has_base_needed = any(p['duration'] > SMALL_MAX_DUR for p in whisper_ps)
                if has_small_needed and not small_exist:
                    continue  # 需要Small但不可用
                if has_base_needed and not base_exist:
                    continue  # 需要Base但不可用

            # 计算各通道总耗时
            api_total = api_busy + api_c * API_TIME
            kedou_total = kedou_busy + kedou_c * KEDOU_TIME
            whisper_total = whisper_busy + sum(estimate_whisper_time(p['duration']) for p in whisper_ps)

            # ---- 约束：除非API和Kedou都已耗尽，否则Whisper不得为瓶颈 ----
            # "已耗尽"：API不可用(0) 且 Kedou余量不够覆盖所有待分配视频
            api_exhausted = not api_avail
            kedou_exhausted = kedou_remain < n
            both_exhausted = api_exhausted and kedou_exhausted

            fixed_max = max(api_total, kedou_total)
            if not both_exhausted and whisper_total > fixed_max:
                continue  # 违反约束：Whisper不可成为瓶颈

            current_max = max(api_total, kedou_total, whisper_total)

            if current_max < best_max:
                best_max = current_max
                best_result = (api_c, kedou_c, api_ps, kedou_ps, whisper_ps)

    if best_result is None:
        # 无可行方案
        return {
            "assignment": [{"p": p['p'], "channel": "none"} for p in sorted_pending],
            "report": {
                "api": {"count": 0, "est_time": 0},
                "kedou": {"count": 0, "est_time": 0},
                "whisper": {"count": 0, "est_time": 0, "detail": "无可用通道"},
                "bottleneck": float('inf'),
                "explain": "❌ 无可用通道组合"
            }
        }

    api_c, kedou_c, api_ps, kedou_ps, whisper_ps = best_result

    # ---- 构建分配表 ----
    assignment = []
    for p in api_ps:
        assignment.append({'p': p['p'], 'channel': 'api'})
    for p in kedou_ps:
        assignment.append({'p': p['p'], 'channel': 'kedou'})
    for p in whisper_ps:
        ch = 'small' if p['duration'] <= SMALL_MAX_DUR else 'base'
        assignment.append({'p': p['p'], 'channel': ch})

    # ---- 统计与报告 ----
    api_count = sum(1 for a in assignment if a['channel'] == 'api')
    kedou_count = sum(1 for a in assignment if a['channel'] == 'kedou')
    base_count = sum(1 for a in assignment if a['channel'] == 'base')
    small_count = sum(1 for a in assignment if a['channel'] == 'small')

    api_est = api_busy + api_count * API_TIME
    kedou_est = kedou_busy + kedou_count * KEDOU_TIME
    whisper_est = whisper_busy
    for a in assignment:
        if a['channel'] in ('base', 'small'):
            dur = next(p['duration'] for p in pending + running if p.get('p') == a['p'])
            whisper_est += estimate_whisper_time(dur)

    bottleneck = max(api_est, kedou_est, whisper_est)

    whisper_detail_parts = []
    if base_count > 0:
        whisper_detail_parts.append(f"Base={base_count}")
    if small_count > 0:
        whisper_detail_parts.append(f"Small={small_count}")
    whisper_detail = ", ".join(whisper_detail_parts) if whisper_detail_parts else "无"

    # 瓶颈说明
    bottleneck_ch = []
    if api_est >= bottleneck - 0.01:
        bottleneck_ch.append(f"API({api_est:.0f}s)")
    if kedou_est >= bottleneck - 0.01:
        bottleneck_ch.append(f"Kedou({kedou_est:.0f}s)")
    if whisper_est >= bottleneck - 0.01:
        bottleneck_ch.append(f"Whisper({whisper_est:.0f}s)")

    # 策略说明
    parts = []
    if api_count > 0:
        parts.append(f"API {api_count}个(最长的{api_c}个P, {api_est:.0f}s)")
    if kedou_count > 0:
        parts.append(f"Kedou {kedou_count}个, {kedou_est:.0f}s")
    if base_count > 0:
        parts.append(f"Base {base_count}个, 合计{sum(estimate_whisper_time(p['duration']) for p in whisper_ps if p['duration'] > SMALL_MAX_DUR):.0f}s")
    if small_count > 0:
        small_ps = [p for p in whisper_ps if p['duration'] <= SMALL_MAX_DUR]
        parts.append(f"Small {small_count}个, 合计{sum(estimate_whisper_time(p['duration']) for p in small_ps):.0f}s")
    explain = " → ".join(parts) if parts else (f"全部Whisper({whisper_detail})" if whisper_ps else "无待分配")

    explain += f" | 瓶颈={'/'.join(bottleneck_ch)}"

    return {
        "assignment": sorted(assignment, key=lambda x: x['p']),
        "report": {
            "api": {"count": api_count, "est_time": round(api_est, 1)},
            "kedou": {"count": kedou_count, "est_time": round(kedou_est, 1)},
            "whisper": {
                "count": base_count + small_count,
                "est_time": round(whisper_est, 1),
                "detail": whisper_detail
            },
            "bottleneck": round(bottleneck, 1),
            "explain": explain
        }
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/allocate.py '<调度请求JSON>'")
        sys.exit(1)
    data = json.loads(sys.argv[1])
    result = allocate(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
