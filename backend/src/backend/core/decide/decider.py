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

    if profile.stars >= _MIN_STARS:
        points += 1
        reasons.append(f"星标 {profile.stars} ≥ {_MIN_STARS}，社区认可度不错")
    else:
        gates.append(f"星标仅 {profile.stars}，低于 {_MIN_STARS}，社区太小")

    if profile.activity.commits_30d >= _MIN_ACTIVITY:
        points += 1
        reasons.append(f"近 30 天 {profile.activity.commits_30d} 次提交，维护活跃")
    else:
        gates.append("近 30 天提交过少，可能无人维护")

    if profile.has_readme:
        points += 1
        reasons.append("有 README，入门信息基础具备")
    else:
        gates.append("缺少 README，新手无从下手")

    if profile.gfi.count >= _GFI_MIN:
        points += 1
        reasons.append(f"有 {profile.gfi.count} 个 good-first-issue 可挑")
    else:
        reasons.append("暂无标注 good-first-issue，入场难度偏高")

    if profile.has_contributing:
        reasons.append("有 CONTRIBUTING，贡献流程有规范可循")

    # License check: must not be missing or proprietary-restrictive.
    lic = (profile.license or "").lower()
    if not lic or lic in {"no-license", "other"}:
        gates.append("缺少可识别的开源许可证")
    elif lic not in {"cc0-1.0", "unlicense"} and "proprietary" in lic:
        gates.append("许可证为专有/非自由，不宜贡献")

    if gates and len(gates) >= 2:
        return "avoid", reasons + gates

    if gates:
        return "unclear", reasons + gates

    if points >= 3:
        return "promising", reasons

    return "unclear", reasons + ["综合信号偏弱，建议人工确认后再投入"]
