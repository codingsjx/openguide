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

from backend.core.decide.decider import decide
from backend.core.generate.evidence import available_sources, resolve_evidence_source
from backend.core.generate.llm import LLMClient, LLMUnavailable
from backend.core.generate.prompts import build_stage_messages, step_from_llm_json
from backend.core.generate.schemas import Evidence, Guide, GuideStep
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
) -> Guide:
    profile = build_profile(sig)
    suitability, reasons = decide(profile)
    repo_url = f"https://github.com/{profile.owner}/{profile.repo}"
    guide = Guide(
        repo_url=repo_url,
        owner=profile.owner,
        repo=profile.repo,
        unsuitable=(suitability == "avoid"),
        reasons=reasons,
    )
    if suitability == "avoid":
        return guide  # 不适合则只给理由，不硬生成（帮新手避坑）

    index = index or _build_index(sig)
    steps: list[GuideStep] = []
    step_id = 1

    if use_llm:
        try:
            client = LLMClient()
            if client.available():
                steps = _generate_with_llm(sig, index, client, start_id=step_id)
            else:
                steps = _generate_heuristic(sig, index, start_id=step_id)
        except LLMUnavailable:
            steps = _generate_heuristic(sig, index, start_id=step_id)
    else:
        steps = _generate_heuristic(sig, index, start_id=step_id)

    guide.steps = _verify_and_relabel(sig, steps)
    return guide


def _build_index(sig: RawSignals) -> RepoIndex:
    idx = RepoIndex(sig.meta.owner, sig.meta.repo)
    idx.index(sig)
    return idx


def _retrieve_for_stage(index: RepoIndex, stage: str, query: str) -> list[dict]:
    kind = _STAGE_PERSPECTIVES.get(stage, "setup")
    res = index.search(query, kind=kind, top_k=4)
    return [{"source": h.perspective, "text": h.text} for h in res.hits]


def _generate_with_llm(sig, index, client, start_id: int) -> list[GuideStep]:
    """Stage-by-stage LLM generation, one request per stage."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        messages = build_stage_messages(stage, snippets)
        try:
            obj = client.chat_json(messages, temperature=0.2, max_tokens=1800)
        except LLMUnavailable:
            return out + _generate_heuristic(sig, index, start_id=sid)
        items = obj.get("steps") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            items = [obj]
        for it in items:
            st = step_from_llm_json(stage, it if isinstance(it, dict) else {}, sid)
            if st is None:
                continue
            st.step_id = sid
            sid += 1
            out.append(st)
    return out


_STAGE_QUERIES = {
    "A": "how to install dependencies and get the project running locally",
    "B": "how to run the test suite",
    "C": "good first issue for a new contributor to pick up",
    "D": "contribution workflow fork clone branch commit pull request",
}


def _generate_heuristic(sig: RawSignals, index: RepoIndex, start_id: int) -> list[GuideStep]:
    """Deterministic fallback: build steps from retrieved snippets by keyword."""
    out: list[GuideStep] = []
    sid = start_id
    for stage, q in _STAGE_QUERIES.items():
        snippets = _retrieve_for_stage(index, stage, q)
        text = " ".join(s["text"] for s in snippets).lower()
        step = _heuristic_one(sig, stage, snippets, text)
        if step:
            step.step_id = sid
            sid += 1
            out.append(step)
    return out


_TITLES = {
    "A": "本地搭建并跑起来",
    "B": "运行测试基线",
    "C": "挑一个 good-first-issue",
    "D": "提交首个 PR",
}


def _heuristic_one(sig, stage: str, snippets: list[dict], text: str) -> GuideStep | None:
    """Deterministic fallback: honest steps + a real command if one is found.

    Scans line-by-line for shell commands (anchored, case-sensitive) so prose
    like "Python 3.10+" is not mistaken for a command. Evidence is attributed
    only when the snippet maps to a real source; otherwise kind=missing
    (无证据不宣称).
    """
    import re

    cmds: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        stripped = re.sub(r"^[$>]\s*", "", line).strip()
        # Match command prefixes as they actually appear in docs.
        if re.match(r"^(pip|python|python3|npm|npx|yarn|pnpm|cargo|make|git|docker|go)\b", stripped):
            cleaned = stripped.split("```")[0].strip()
            if cleaned and len(cleaned) < 140:
                cmds.append(cleaned)
        if len(cmds) >= 2:
            break
    seen: set[str] = set()
    cmds = [c for c in cmds if not (c in seen or seen.add(c))]

    expected = (
        f"运行 {cmds[0]} 并确认成功（无报错）" if cmds else "见仓库原文确认成功标志"
    )
    return GuideStep(
        step_id=0,
        stage=stage,  # type: ignore[arg-type]
        stage_label=_STAGE_LABELS[stage],
        title=_TITLES[stage],
        command=cmds[0] if cmds else None,
        expected=expected,
        fail_hints=["如卡住，把报错贴给 OpenGuide 的‘报错了’追问"],
        # Heuristic fallback deliberately marks evidence missing unless the
        # snippet source resolves to a real file (handled by verification).
        evidence=Evidence(kind="missing", source="", quote=""),
    )


def _verify_and_relabel(sig: RawSignals, steps: list[GuideStep]) -> list[GuideStep]:
    """Post-check every evidence against the repo; downgrade unverifiable ones."""
    avail = available_sources(sig)
    issue_nums = {i.get("number") for i in sig.issues if i.get("pull_request") is None}
    out: list[GuideStep] = []
    for st in steps:
        ev = st.evidence
        if ev.kind == "missing":
            out.append(st)
            continue
        if ev.kind == "issue":
            if ev.source.lstrip("#").isdigit() and int(ev.source.lstrip("#")) in issue_nums:
                out.append(st)
                continue
            st.evidence = Evidence(kind="missing", source="", quote="")
            out.append(st)
            continue
        # file: check source path exists in what we fetched.
        norm = ev.source.split("#", 1)[0].lower().strip("/")
        blob = __import__("re").search(r"blob/[^/]+/(.+)", ev.source.lower())
        if blob:
            norm = blob.group(1).split("#", 1)[0]
        if norm in avail or any(norm.startswith(p + "/") for p in avail):
            out.append(st)
            continue
        st.evidence = Evidence(kind="missing", source="", quote="")
        out.append(st)
    return out
