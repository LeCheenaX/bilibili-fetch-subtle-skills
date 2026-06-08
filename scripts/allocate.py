#!/usr/bin/env python3
"""
混合调度分配器 — B站视频字幕混合获取。

输入：JSON [[P序号, 时长秒], ...]  [可选 max_kedou]
输出：JSON {kedou: [P序号...], base: [P序号...], small: [P序号...]}

算法核心：
  对所有可能的 k（Kedou 数量，从 max_kedown 到 0）搜索最优分配。
  Kedou 拿最长的 P（发挥固定 20s 的优势），剩余 P 在 Base/Small 间优化分配。
  目标：|cloud - local| 最小，优先 cloud > local。

速度基准（实测，CPU推理）：
  - Kedou:  固定 20s/P
  - Base:   duration / 7
  - Small:  duration / 2.4
"""

import sys
import json

KEDOU_TIME = 20.0
BASE_FACTOR = 7.0
SMALL_FACTOR = 2.4

# Small 模型只用于 < 7 分钟的视频
SMALL_MAX_DURATION = 420  # 7分钟 = 420秒

# Small 比 Base 每单位 duration 多花的额外时间比
# 1/2.4 - 1/7 ≈ 0.2738 s per duration second
SMALL_EXTRA_RATIO = 1.0 / SMALL_FACTOR - 1.0 / BASE_FACTOR


def allocate(pages, max_kedou=10):
    """
    pages: [(p_number, duration_seconds), ...]
    max_kedou: 最多分配几个 P 给 Kedou

    Returns: {kedou: [p...], base: [p...], small: [p...]}
    """
    if not pages:
        return {"kedou": [], "base": [], "small": []}

    total_n = len(pages)

    # N ≤ 4 → 全走 Kedou（P少不值得本地跑）
    if total_n <= 4:
        return {"kedou": sorted(p for p, _ in pages), "base": [], "small": []}

    # 按时长降序
    sorted_pages = sorted(pages, key=lambda x: x[1], reverse=True)

    best = {
        "result": None,
        "cloud_time": 0,
        "local_time": 0,
        "score": float('inf'),
        "cloud_gt_local": False,
    }

    def evaluate(k):
        """搜索 k 个 P 给 Kedou，剩余在 Base/Small 间优化分配，返回 (result_dict, score)"""
        kedou_ps = sorted_pages[:k]
        local_ps = sorted_pages[k:]

        cloud_time = k * KEDOU_TIME

        if not local_ps:
            # 全部给了 Kedou（只在 N ≤ max_kedou 时可能）
            return {
                "kedou": sorted(p for p, _ in kedou_ps),
                "base": [],
                "small": []
            }, cloud_time, 0.0

        # -- 过滤：Small 只用于 < 420s 的视频 --
        small_eligible = [(p, d) for p, d in local_ps if d < SMALL_MAX_DURATION]
        base_only = [(p, d) for p, d in local_ps if d >= SMALL_MAX_DURATION]

        base_only_set = {p for p, _ in base_only}
        base_only_dur = sum(d for _, d in base_only)

        # -- 计算基准时间 --
        eligible_dur = sum(d for _, d in small_eligible)
        total_dur = base_only_dur + eligible_dur
        all_base_time = total_dur / BASE_FACTOR  # 所有 Ps 都用 Base
        # 只计算 eligible Ps 全用 Small 的情况
        all_eligible_small_time = base_only_dur / BASE_FACTOR + eligible_dur / SMALL_FACTOR

        # 在 Base 和 Small 间分配，目标是让 local_time 尽量接近 cloud_time
        # 方法：从 "全部 Base" 出发，选 eligible P 升到 Small 来增加 local_time

        def _build_result(base_set, small_set):
            """构建包含 base_only 的完整结果"""
            full_base = set(base_set) | base_only_set
            return {
                "kedou": sorted(p for p, _ in kedou_ps),
                "base": sorted(full_base),
                "small": sorted(small_set)
            }

        def _local_time_from(base_set, small_set, extra_acc):
            """根据分配计算 local_time"""
            return (sum(d for p, d in local_ps if p in base_set | base_only_set) / BASE_FACTOR
                    + sum(d for p, d in local_ps if p in small_set) / SMALL_FACTOR)

        # ---- 情况 1: cloud 比全 Base 还小 → 全 Base + 强制 1 个 eligible Small ----
        if cloud_time <= all_base_time:
            base_set = {p for p, _ in small_eligible}
            small_set = set()

            # 选最短的 eligible P 升 Small（损失最小）
            if small_eligible:
                shortest = min(small_eligible, key=lambda x: x[1])
                base_set.discard(shortest[0])
                small_set.add(shortest[0])

            local_time = _local_time_from(base_set, small_set, 0)

            return _build_result(base_set, small_set), cloud_time, local_time

        # ---- 情况 2: cloud 在全 Base 和全 eligible-Small 之间 → 精细搜索 ----
        if cloud_time <= all_eligible_small_time:
            needed_extra = cloud_time - all_base_time

            # small_eligible 按时长升序（短 P 优先升 Small）
            sorted_eligible = sorted(small_eligible, key=lambda x: x[1])

            base_set = {p for p, _ in small_eligible}
            small_set = set()
            accumulated_extra = 0.0

            for idx, dur in sorted_eligible:
                extra = dur * SMALL_EXTRA_RATIO
                if accumulated_extra + extra <= needed_extra * 1.15:
                    base_set.discard(idx)
                    small_set.add(idx)
                    accumulated_extra += extra

            # 如果没有任何 P 升到 Small（所有 eligible 都太短？），强制升最短的
            if not small_set and sorted_eligible:
                shortest = sorted_eligible[0]
                base_set.discard(shortest[0])
                small_set.add(shortest[0])
                accumulated_extra = shortest[1] * SMALL_EXTRA_RATIO

            local_time = _local_time_from(base_set, small_set, accumulated_extra)

            return _build_result(base_set, small_set), cloud_time, local_time

        # ---- 情况 3: cloud 大于全 eligible-Small → 所有 eligible 用 Small ----
        return _build_result(set(), {p for p, _ in small_eligible}), cloud_time, all_eligible_small_time

    # 对所有可能的 k 搜索（Kedou 数量）
    # 上限：P数较多时受限于 max_kedou；P数较少时全给 Kedou
    k_max = min(max_kedou, total_n)
    # 但至少留 1 个给本地做质量兜底（除非本地只有 ≤4P，全给 Kedou）
    k_max = k_max if total_n <= 4 else min(k_max, total_n - 1)
    for k in range(k_max, -1, -1):
        result, ct, lt = evaluate(k)
        score = abs(ct - lt)
        cgt = ct > lt

        better = False
        if cgt and not best["cloud_gt_local"]:
            better = True  # 首次达成 cloud > local
        elif cgt == best["cloud_gt_local"]:
            if score < best["score"]:
                better = True  # 同状态但分数更好
            elif score == best["score"] and cgt and not best["cloud_gt_local"]:
                better = True  # 同分但 cloud > local 优先

        if better:
            best["result"] = result
            best["cloud_time"] = ct
            best["local_time"] = lt
            best["score"] = score
            best["cloud_gt_local"] = cgt

    if best["result"] is None:
        return {"kedou": [], "base": sorted(p for p, _ in sorted_pages), "small": []}

    return best["result"]


def estimate_report(pages, result):
    """生成预估耗时报告"""
    dmap = {p: d for p, d in pages}

    ct = len(result["kedou"]) * KEDOU_TIME

    bt = sum(dmap[p] for p in result["base"]) / BASE_FACTOR if result["base"] else 0
    st = sum(dmap[p] for p in result["small"]) / SMALL_FACTOR if result["small"] else 0
    lt = bt + st

    lines = []
    lines.append(f"Cloud: Kedou x{len(result['kedou'])} → {ct:.0f}s")
    if result["base"]:
        base_parts = ", ".join(str(p) for p in result["base"][:6])
        if len(result["base"]) > 6:
            base_parts += f"...(+{len(result['base'])-6})"
        lines.append(f"  Base [{base_parts}]: {bt:.0f}s")
    if result["small"]:
        small_parts = ", ".join(str(p) for p in result["small"])
        lines.append(f"  Small [{small_parts}]: {st:.0f}s")
    lines.append(f"Local 合计: {lt:.0f}s  (Base={bt:.0f}s + Small={st:.0f}s)")
    lines.append(f"|Cloud - Local| = {abs(ct-lt):.0f}s")
    lines.append(f"总瓶颈耗时: {max(ct, lt):.0f}s")
    lines.append("✅ Cloud > Local" if ct > lt else "⚠️  Cloud < Local")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/allocate.py '<pages_json>' [max_kedou]")
        print("示例: python3 scripts/allocate.py '[[1,527],[2,749],[3,523]]' 10")
        print("pages_json: [[P序号, 时长秒], ...]")
        sys.exit(1)

    pages = json.loads(sys.argv[1])
    max_kedou = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    result = allocate(pages, max_kedou)

    # JSON 输出
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 报告
    print()
    print(estimate_report(pages, result))


if __name__ == "__main__":
    main()
