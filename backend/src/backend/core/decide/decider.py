"""Decision tree: is this repo suitable for a beginner contributor?

Pure rules over a Profile. Kept model-free so it is unit-testable and
explicable in the demo ("why does OpenGuide recommend this repo?").
"""

from __future__ import annotations

from backend.core.profile.schema import Profile

# Reasonable floor for "is this project worth a beginner's time".
_MIN_STARS = 10
_MIN_ACTIVITY = 3  # commits in 30d
_MAX_RECENT = 365  # days since last push before we call it dormant
_GFI_MIN = 1


def decide(profile: Profile) -> tuple[str, list[str]]:
    """Return (suitability, reasons). Suitability in {promising, unclear, avoid}."""
    reasons: list[str] = []
    points = 0
    gates = []  # blocking reasons -> avoid
    unavailable = set(profile.unavailable_signals)

    if "stars" in unavailable:
        reasons.append("社区规模未取得，暂不参与适用性判断")
    elif profile.stars >= _MIN_STARS:
        points += 1
        reasons.append(f"星标 {profile.stars} ≥ {_MIN_STARS}，社区认可度不错")
    else:
        reasons.append(f"星标 {profile.stars} 较少；社区规模不能单独判断贡献价值")

    if "activity" in unavailable:
        reasons.append("近期活跃度未取得，暂不参与适用性判断")
    elif profile.activity.commits_30d >= _MIN_ACTIVITY:
        points += 1
        reasons.append(f"近 30 天 {profile.activity.commits_30d} 次提交，维护活跃")
    else:
        reasons.append(f"采集到近 30 天 {profile.activity.commits_30d} 次提交；仅凭提交数量无法判断是否有人维护，请核对 issue 回复与发布记录")

    if "root" in unavailable:
        reasons.append("入口文档信息不完整，需确认 README")
    elif profile.has_readme:
        points += 1
        reasons.append("有 README，入门信息基础具备")
    else:
        gates.append("缺少 README，新手无从下手")

    if "issues" in unavailable:
        reasons.append("新手任务数据不完整，不能判断当前任务数量")
    elif profile.gfi.count >= _GFI_MIN:
        points += 1
        reasons.append(f"有 {profile.gfi.count} 个候选开放任务，仍需核对难度和认领状态")
    else:
        reasons.append("本次未发现候选新手任务，需进一步查看社区贡献入口")

    if profile.has_contributing:
        reasons.append("有 CONTRIBUTING，贡献流程有规范可循")

    # License check: must not be missing or proprietary-restrictive.
    lic = (profile.license or "").lower()
    if "license" in unavailable:
        reasons.append("许可证信息未取得，须核对上游授权")
    elif not lic or lic in {"no-license", "other"}:
        gates.append("缺少可识别的开源许可证")
    elif lic not in {"cc0-1.0", "unlicense"} and "proprietary" in lic:
        gates.append("许可证为专有/非自由，不宜贡献")

    if gates and len(gates) >= 2:
        return "avoid", reasons + gates

    if unavailable:
        return "unclear", reasons + gates + ["部分资料尚未取得，本次不作确定的新手适用性推荐"]

    if gates:
        return "unclear", reasons + gates

    if points >= 3 and profile.activity.commits_30d >= _MIN_ACTIVITY:
        return "promising", reasons

    return "unclear", reasons + ["综合信号偏弱，建议人工确认后再投入"]
