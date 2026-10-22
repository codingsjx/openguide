"""Guide-generation pipeline (module 3).

Flow: enrich repo signals -> build perspective index -> for each stage A..D
retrieve the evidence snippets relevant to that stage -> ask the LLM to fill
GuideStep JSON -> post-verify every step's evidence against the repo (无证据
不宣称) -> return a Guide.

Two execution modes:
- `llm=True` (default): call the configured LLM via prompts.py.
- `llm=False` / no key: fall back to a *deterministic heuristic generator*
  (rules + retrieved snippets) so the API + demo work offline and CI can
  exercise the pipeline without a key. Benchmark L2 can score this too, making
  the "without an LLM key" path honest rather than skipped.
"""

from __future__ import annotations

import re

from backend.core.decide.decider import decide
from backend.core.generate.evidence import verify_step_evidence
from backend.core.generate.llm import LLMClient, LLMUnavailable
from backend.core.generate.make_recipe import expand_make_recipe
from backend.core.generate.workflow import prepare_workflow
from backend.core.generate.heuristic import generate_stage
from backend.core.generate.prompts import build_stage_messages, step_from_llm_json
from backend.core.generate.schemas import Evidence, Guide, GuideStep
from backend.core.generate.issues import discover_issues
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex
from backend.core.profile.builder import build_profile

_STAGE_LABELS = {"A": "环境搭建", "B": "测试基线", "C": "挑选 issue", "D": "首次 PR 路径"}

# Which perspectives each stage should retrieve from.
_STAGE_PERSPECTIVES = {
    "A": "setup",
    "B": "test",
    "C": "issue",
    "D": "contribute",
}


def build_guide(
    sig: RawSignals,
    index: RepoIndex | None = None,
    use_llm: bool = True,
    strict_llm: bool = False,
    verify_evidence: bool = True,
    llm_client: LLMClient | None = None,
    check_suitability: bool = True,
) -> Guide:
    profile = build_profile(sig)
    suitability, reasons = decide(profile)
    if not check_suitability:
        suitability, reasons = "unclear", ["实验跳过适用性门槛，不代表推荐贡献此仓库"]
    repo_url = f"https://github.com/{profile.owner}/{profile.repo}"
    guide = Guide(
        repo_url=repo_url,
        owner=profile.owner,
        repo=profile.repo,
        default_branch=profile.default_branch,
        unsuitable=(suitability == "avoid"),
        reasons=reasons,
        warnings=list(sig.collection_warnings),
        issue_discovery=discover_issues(sig),
        requested_mode='ai' if use_llm else 'rules',
    )
    if sig.symlink_paths:
        guide.warnings.append(f"仓库含 {len(sig.symlink_paths)} 个符号链接；Windows 克隆后请确认链接未变成普通文本文件，否则可能导致路径或证书测试失败")
    if suitability == "avoid":
        return guide  # 不适合则只给理由，不硬生成（帮新手避坑）

    index = index or _build_index(sig)
    steps: list[GuideStep] = []
    step_id = 1

    if use_llm:
        try:
            client = llm_client or LLMClient()
            if client.available():
                steps = _generate_with_llm(sig, index, client, start_id=step_id,
                    allow_fallback=not strict_llm, stage_modes=guide.stage_modes, warnings=guide.warnings,
                    fallback_reasons=guide.stage_fallbacks)
                model_stages = sum(mode == 'llm' for mode in guide.stage_modes.values())
                guide.generation_mode = 'llm' if model_stages == 4 else 'mixed' if model_stages else 'heuristic'
            else:
                if strict_llm:
                    raise LLMUnavailable("真实模型评测禁止无 Key 回退")
                steps = _generate_heuristic(sig, index, start_id=step_id)
                guide.stage_modes = {stage: 'heuristic' for stage in _STAGE_QUERIES}
                guide.stage_fallbacks = {stage: 'not_configured' for stage in _STAGE_QUERIES}
        except LLMUnavailable as exc:
            if strict_llm:
                raise
            steps = _generate_heuristic(sig, index, start_id=step_id)
            guide.stage_modes = {stage: 'heuristic' for stage in _STAGE_QUERIES}
            guide.stage_fallbacks = {stage: _fallback_reason(exc) for stage in _STAGE_QUERIES}
            guide.warnings.append("模型不可用，本次使用规则生成")
    else:
        steps = _generate_heuristic(sig, index, start_id=step_id)
        guide.stage_modes = {stage: 'heuristic' for stage in _STAGE_QUERIES}

    if not verify_evidence:
        guide.steps = steps
        return guide
    guide.steps = audit_steps(sig, index, steps)
    if not strict_llm:
        # Auditing can move a model's clone step out of D and deduplicate it.
        # Restore an honest entry point instead of leaving that stage empty.
        fallback_stages = [stage for stage in _STAGE_QUERIES
            if not any(s.stage == stage and s.evidence.kind != 'missing' for s in guide.steps)]
        replaced = False
        if fallback_stages:
            for stage in fallback_stages:
                snippets = _retrieve_for_stage(index, stage, _STAGE_QUERIES[stage])
                rules = audit_steps(sig, index, generate_stage(sig, stage, snippets, _STAGE_CMD_PATTERNS[stage]))
                if stage != 'C' and any(s.stage == stage for s in guide.steps) and not any(s.evidence.kind != 'missing' for s in rules):
                    continue
                guide.steps = [s for s in guide.steps if s.stage != stage] + rules
                if guide.stage_modes.get(stage) == 'llm':
                    guide.stage_fallbacks[stage] = 'evidence_unverified'
                guide.stage_modes[stage] = 'heuristic'
                replaced = True
                guide.warnings.append(f'{_STAGE_LABELS[stage]}阶段未保留可核验依据，已补充仓库原文规则入口或待确认项。')
        if replaced:
            guide.steps = audit_steps(sig, index, guide.steps)
            model_stages = sum(mode == 'llm' for mode in guide.stage_modes.values())
            guide.generation_mode = 'mixed' if model_stages else 'heuristic'
    if guide.generation_mode == "llm" and any(s.command_derivation for s in guide.steps):
        guide.generation_mode = "mixed"
        guide.warnings.append("部分 make 命令已按仓库原文展开，展开过程可查看；尚未执行")
    return guide


def audit_steps(sig: RawSignals, index: RepoIndex, steps: list[GuideStep]) -> list[GuideStep]:
    """Shared audit for product and paired before/after experiments."""
    steps = prepare_workflow(sig, [expand_make_recipe(step, sig) for step in steps])
    steps = _verify_and_relabel(sig, steps)
    # Second pass: try to find a real source for still-missing steps by
    # re-searching the index with the step's own title/command.
    steps = _backfill_evidence(sig, index, steps)
    for st in steps:
        source_path = st.evidence.source.split('#', 1)[0].lower()
        if st.command and st.stage == 'A' and source_path.startswith('.github/workflows/') and re.search(r'typecheck|publish|release|coverage|lint', source_path):
            st.command = None
            st.execution_record = None
            st.title = '核对专项 CI 安装示例（待确认是否适用）'
            st.expected = '该来源属于专项 CI，尚不能作为普通开发环境的必需安装步骤；请核对仓库开发说明。'
        if st.command and not re.match(_STAGE_CMD_PATTERNS[st.stage], st.command):
            st.evidence = Evidence(kind="missing", reason="命令动作不属于当前阶段")
        if st.command and st.evidence.verification != "command_verified":
            st.command = None
            st.execution_record = None
            st.expected = "请先在仓库文档中确认操作方法"
            st.fail_hints.append("命令未通过原文核验，已隐藏；可打开仓库文档或向维护者提问")
    steps = prepare_workflow(sig, steps)
    for step in steps:
        if step.stage != "C" or step.evidence.kind != "issue":
            continue
        issue = next((i for i in sig.issues if f"#{i.get('number')}" == step.evidence.source), None)
        if issue is None:
            continue
        blockers = []
        if issue.get("state") != "open":
            blockers.append("状态未确认开放")
        if issue.get("locked") is True:
            blockers.append("讨论已锁定")
        if issue.get("assignees") or issue.get("assignee"):
            blockers.append("已有负责人")
        unknown = [key for key in ("state", "locked", "assignees") if key not in issue]
        step.title = f"核对 issue #{issue['number']}（{'；'.join(blockers) if blockers else '待确认候选'}）"
        step.expected = "核对最新讨论、关联 PR 和维护者认领规则后，再决定是否参与；本步骤不代表已认领或已完成贡献。"
        step.context_notes.append("issue 标签不能证明适合新手；采集状态可能已变化，关联 PR 与最新讨论尚未核验。")
        if blockers:
            step.context_notes.append("当前快照存在阻碍：" + "；".join(blockers) + "。请先核对，不建议直接认领。")
        if unknown:
            step.context_notes.append("未取得字段：" + ", ".join(unknown) + "，不能据此判断无人负责或讨论未锁定。")
        step.success_checks = ["已打开原始 issue，核对负责人、最新讨论及关联 PR，并确认维护者允许参与。"]
    return steps


def _build_index(sig: RawSignals) -> RepoIndex:
    idx = RepoIndex(sig.meta.owner, sig.meta.repo)
    idx.index(sig)
    return idx


def _retrieve_for_stage(index: RepoIndex, stage: str, query: str) -> list[dict]:
    kind = _STAGE_PERSPECTIVES.get(stage, "setup")
    res = index.search(query, kind=kind, top_k=20)
    def rank(hit):
        commands = [re.sub(r"^(?:\$|>)\s*", "", line.strip()) for line in hit.text.splitlines()]
        relevant = any(re.match(_STAGE_CMD_PATTERNS[stage], line) for line in commands)
        development = stage == "A" and any("-e " in line or "requirements-dev" in line or "uv sync" in line for line in commands)
        baseline = stage == "B" and any(re.match(_STAGE_CMD_PATTERNS[stage], line) and not re.search(r"\b(?:stress|random|coverage|browser)\b|--numprocesses", line) for line in commands)
        return (development, baseline, relevant, hit.score)
    hits = sorted(res.hits, key=rank, reverse=True)
    reserved = []
    if stage == "A":
        # Preserve complementary prerequisites within the same context budget:
        # installation-heavy files must not crowd out clone/runtime evidence.
        slots = [
            ("git clone source repository", lambda text: any(re.match(r"^git clone\b", re.sub(r"^[$>]\s*", "", line.strip())) for line in text.splitlines())),
            ("development install dependencies requirements-dev editable uv sync npm ci", lambda text: any(re.match(_STAGE_CMD_PATTERNS['A'], re.sub(r"^[$>]\s*", "", line.strip())) and 'git clone' not in line for line in text.splitlines())),
            ("requires-python python version node engines", lambda text: any(token in text.lower() for token in ("requires-python", "python-version", '"engines"', "node-version"))),
        ]
        for slot_query, accepts in slots:
            candidates = index.search(slot_query, kind=kind, top_k=20).hits
            candidates = sorted(candidates, key=lambda h: (
                (h.meta or {}).get('source','').lower() in {'readme.md','readme.rst','readme'} if 'git clone' in slot_query else False,
                rank(h)), reverse=True)
            match = next((h for h in candidates if (h.meta or {}).get('source') and accepts(h.text)), None)
            if match and not any(h.text == match.text and h.meta == match.meta for h in reserved):
                reserved.append(match)
        hits = reserved + [h for h in hits if not any(h.text == r.text and h.meta == r.meta for r in reserved)]
    # Diversity: a long generic file must not occupy every context slot.
    selected, source_counts = [], {}
    for hit in hits:
        source = (hit.meta or {}).get("source", "")
        if source_counts.get(source, 0) >= 2 and not any(hit is item for item in reserved):
            continue
        selected.append(hit)
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) == 4:
            break
    out: list[dict] = []
    for h in selected:
        # Prefer the chunk's real repo source (file path or issue ref) over the
        # perspective code; fall back to perspective only as a last resort.
        src = (h.meta or {}).get("source") or h.perspective
        kind_meta = (h.meta or {}).get("kind") or "file"
        out.append({"source": src, "text": h.text, "meta_kind": kind_meta})
    return out


def _fallback_reason(exc: LLMUnavailable) -> str:
    """Return a safe code; provider errors/URLs are never exposed as metadata."""
    import httpx
    cause = exc.__cause__
    if isinstance(cause, httpx.TimeoutException):
        return 'model_timeout'
    if isinstance(cause, httpx.HTTPStatusError):
        if cause.response.status_code in (401, 403):
            return 'model_auth_failed'
        if cause.response.status_code == 429:
            return 'model_rate_limited'
    if str(exc).startswith(('LLM 返回', 'LLM 响应', 'LLM 必须')) or '未输出有效步骤' in str(exc):
        return 'invalid_output'
    return 'model_error'


def _generate_with_llm(sig, index, client, start_id: int, *, allow_fallback=False, stage_modes=None, warnings=None, fallback_reasons=None) -> list[GuideStep]:
    """Stage-by-stage LLM generation, one request per stage."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        messages = build_stage_messages(stage, snippets)
        try:
            obj = client.chat_json(messages, temperature=0.2, max_tokens=1800)
            items = obj.get('steps') if isinstance(obj, dict) else None
            if not isinstance(items, list):
                items = [obj]
            stage_steps = []
            for item in items:
                step = step_from_llm_json(stage, item if isinstance(item, dict) else {}, sid + len(stage_steps))
                if step is not None:
                    stage_steps.append(step)
            if not stage_steps:
                raise LLMUnavailable(f'Stage {stage} 未输出有效步骤')
            mode = 'llm'
        except LLMUnavailable as exc:
            if not allow_fallback:
                raise
            stage_steps = generate_stage(sig, stage, snippets, _STAGE_CMD_PATTERNS[stage])
            mode = 'heuristic'
            if fallback_reasons is not None:
                fallback_reasons[stage] = _fallback_reason(exc)
            if warnings is not None:
                warnings.append(f'{_STAGE_LABELS[stage]}阶段模型未完成，已仅对该阶段使用规则；其他阶段继续生成。')
        if stage_modes is not None:
            stage_modes[stage] = mode
        for step in stage_steps:
            step.step_id = sid
            sid += 1
            out.append(step)
    return out


_STAGE_QUERIES = {
    "A": "development environment editable install dependencies pip uv sync requirements-dev setup venv",
    "B": "run test suite pytest tox nox unittest npm test make test cargo test go test",
    "C": "good first issue for a new contributor to pick up",
    "D": "contribution workflow fork clone branch commit pull request",
}


def _generate_heuristic(sig: RawSignals, index: RepoIndex, start_id: int) -> list[GuideStep]:
    """Deterministic fallback: build steps from retrieved snippets by keyword."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        for step in generate_stage(sig, stage, snippets, _STAGE_CMD_PATTERNS[stage]):
            step.step_id = sid
            sid += 1
            out.append(step)
    return out


# Stage -> command families that actually belong to that stage. The heuristic
# generator used to take the *first* command it found in the retrieved text, so
# a single README containing both `pip install ...` and `pytest` made stages
# A/B/D all emit the same install command (B should run tests, D should be
# git/PR). We now only accept a command whose family matches the stage, and
# fall back to no command rather than mis-attributing one (无证据不宣称).
_STAGE_CMD_PATTERNS = {
    "A": r"^(git clone|pip(?:3)? install|uv (?:sync|venv|pip install)|poetry (?:install|sync)|conda (?:create|env create|install)|python(?:3)? -m (?:pip install|venv)|virtualenv|npm (?:ci|install)|pnpm install|yarn(?: install)?$|cargo build|go mod (?:download|tidy)|bundle install|gem install|composer install)\b",
    "B": r"^(pytest|tox|nox|python -m pytest|python -m unittest|npm (test|run test)|pnpm (test|run test)|yarn (test|run test)|cargo test|go test|make (test|check)|bundle exec rspec)\b",
    "C": r"^(gh issue|git (log|branch))\b",
    "D": r"^(git (checkout|switch|add|commit|push|clone|remote|branch)|gh (pr|repo|fork))\b",
}


def _verify_and_relabel(sig: RawSignals, steps: list[GuideStep]) -> list[GuideStep]:
    """Post-check every evidence against the repo; downgrade unverifiable ones.

    Perspective codes (v1..v4) and other non-repo identifiers are not accepted
    as evidence sources — only real file paths / issue refs we fetched pass.
    """
    out: list[GuideStep] = []
    for st in steps:
        ev = st.evidence
        if ev.kind == "missing":
            out.append(st)
            continue
        # Reject perspective-code sources outright.
        if ev.source in {"v1", "v2", "v3", "v4"}:
            st.evidence = Evidence(kind="missing", source="", quote="")
            out.append(st)
            continue
        resolved = verify_step_evidence(st, sig)
        if resolved.kind == ev.kind:
            st.evidence = resolved
        else:
            st.evidence = resolved
        out.append(st)
    return out


def _backfill_evidence(sig, index: RepoIndex, steps: list[GuideStep]) -> list[GuideStep]:
    """For missing-evidence steps, search within the *stage-relevant*
    perspective(s) and attach a real repo source if one is retrievable.

    Precision over recall: the search is scoped to the perspective that stage
    is generated from (A/B -> v3 可执行路径, C -> v4 issue 槽位, D -> v1 约定),
    so a backfilled source is the file/issue that actually backs that kind of
    step — not whatever ranks highest in the whole index. Honest rule: if no
    real source surfaces, keep missing (无证据不宣称).
    """
    if not index:
        return steps
    # stage -> perspectives to scope the backfill search to.
    stage_perspectives = {"A": "setup", "B": "test", "C": "issue", "D": "contribute"}
    out: list[GuideStep] = []
    for st in steps:
        if st.evidence.kind != "missing":
            out.append(st)
            continue
        # Build a retrieval query from title + command.
        query = " ".join(filter(None, [st.title, st.command or "", st.expected]))
        if st.stage == "C" or "issue" in (st.title or "").lower():
            query += " good first issue first contribution"
        query = query.replace("-", " ").strip()
        if not query:
            out.append(st)
            continue
        kind = stage_perspectives.get(st.stage, "setup")
        try:
            res = index.search(query, kind=kind, top_k=4)
        except Exception:  # noqa: BLE001 - never let backfill crash generation
            out.append(st)
            continue
        found = None
        for h in res.hits:
            meta = h.meta or {}
            src = meta.get("source") or ""
            mkind = meta.get("kind") or "file"
            # Only real file/issue sources count; perspective codes are not.
            if mkind in ("file", "issue") and src and not src.startswith("v"):
                candidate = st.model_copy(deep=True)
                candidate.evidence = Evidence(kind=mkind, source=src, quote=st.evidence.quote)
                checked = verify_step_evidence(candidate, sig)
                # An arbitrary related source is insufficient for prose-only steps.
                if checked.kind != "missing" and (st.command or checked.quote or (st.stage == "C" and checked.kind == "issue")):
                    found = checked
                    break
        if found:
            st.evidence = found
        out.append(st)
    return out
