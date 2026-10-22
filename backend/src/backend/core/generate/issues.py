"""Issue entry points from collected GitHub data, independent of model prose."""
from __future__ import annotations

from urllib.parse import urlencode
from typing import Literal
import re

from pydantic import BaseModel, Field


class IssueCandidate(BaseModel):
    number: int
    title: str
    url: str
    labels: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    origin: Literal['labelled', 'untriaged'] = "labelled"


class IssueDiscovery(BaseModel):
    status: Literal['candidates', 'untriaged', 'empty', 'unavailable', 'blocked']
    reason: str
    sampled_at: str = ""
    sampled_count: int = 0
    blocked_count: int = 0
    candidates: list[IssueCandidate] = Field(default_factory=list)
    search_links: list[dict[str, str]] = Field(default_factory=list)


def discover_issues(sig) -> IssueDiscovery:
    repo_url = f"https://github.com/{sig.meta.owner}/{sig.meta.repo}"
    links = [{"label": label, "url": repo_url + "/issues?" + urlencode({"q": query})} for label, query in (
        ("good first issue", 'is:issue is:open label:"good first issue"'),
        ("help wanted", 'is:issue is:open label:"help wanted"'),
        ("全部开放 issue", 'is:issue is:open'),
    )]
    labelled = [i for i in sig.issues if isinstance(i, dict) and i.get("pull_request") is None]
    pool = labelled + [i for i in sig.issue_samples if isinstance(i, dict) and i.get("pull_request") is None]
    candidates, blocked, seen = [], 0, set()
    for issue in pool:
        number = issue.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0 or number in seen:
            continue
        seen.add(number)
        if issue.get("state") != "open" or issue.get("locked") or issue.get("assignees") or issue.get("assignee"):
            blocked += 1
            continue
        origin = "labelled" if issue in labelled else "untriaged"
        checks = ["打开最新讨论，检查是否已有对应 PR、任务是否仍需处理，并遵循维护者参与规则。"]
        if "locked" not in issue or "assignees" not in issue:
            checks.append("未取得完整锁定/负责人字段，必须在原 issue 核对。")
        if origin == "untriaged":
            checks.append("这是普通开放 issue 的浏览样本，尚未确认适合新手；先评估复现难度和任务范围。")
        if re.search(r'https://github\.com/[^\s]+/(?:pull/\d+|compare/)', str(issue.get('body') or '')):
            checks.append("正文含 PR 或代码比较链接，可能已有相关实现；先核对现有方案及讨论，避免重复提交。")
        labels = [x if isinstance(x, str) else x.get("name", "") for x in issue.get("labels", []) if isinstance(x, (dict, str))]
        title = issue.get("title")
        candidates.append(IssueCandidate(number=number, title=title[:500] if isinstance(title, str) else f"Issue #{number}",
            url=f"{repo_url}/issues/{number}", labels=[l for l in labels if isinstance(l, str)][:12], checks=checks, origin=origin))
    has_labelled = any(c.origin == "labelled" for c in candidates)
    unavailable = any(key in sig.unavailable_signals for key in ('issues', 'issue_samples'))
    if candidates:
        status = "candidates" if has_labelled else "untriaged"
        reason = "以下是标签检索得到的待核对候选；标签不能证明任务适合你。" if has_labelled else "未取得可用的标签候选；以下普通开放 issue 仅供浏览，不作为新手推荐。"
        if unavailable:
            reason += "标签采集不完整，不能据此判断仓库没有其他任务。"
    elif unavailable:
        status, reason = "unavailable", "任务采集未完整成功；不能据此判断没有任务。可稍后重试，或通过下方 GitHub 检索入口人工核对。"
    elif blocked:
        status, reason = "blocked", "本次采样中的任务已有人负责、已锁定或未确认开放，暂不提供可直接选择的候选；请查看下方最新检索结果。"
    else:
        status, reason = "empty", "本次标签检索和有限开放 issue 采样没有取得可用候选，不代表仓库没有任务。可查看最新检索结果，或从贡献规范中选择并说明一个小范围任务。"
    return IssueDiscovery(status=status, reason=reason, sampled_at=sig.issues_collected_at,
        sampled_count=len(seen), blocked_count=blocked, candidates=candidates[:3], search_links=links)
