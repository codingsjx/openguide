"""Extract stated runtime requirements without inventing installation commands."""
from pathlib import PurePosixPath
import re

from backend.core.ask.scope import source_allowed, component_excerpt
from backend.core.generate.evidence import verify_step_evidence
from backend.core.generate.schemas import Evidence, GuideStep


def runtime_steps(sig, component: str | None = None) -> list[GuideStep]:
    output, seen = [], set()
    docs = sorted(sig.doc_files, key=lambda d: (
        PurePosixPath(d.path).name.lower() not in {'readme.md', 'readme.rst', 'readme'},
        d.path.count('/'), d.path))
    for doc in docs:
        if not source_allowed(doc.path, '', component, 'setup'):
            continue
        excerpt = component_excerpt(doc.text, doc.path, doc.text, component)
        if excerpt is None:
            continue
        text = excerpt[0]
        quotes = []
        name = PurePosixPath(doc.path).name.lower()
        if name in {'.python-version', '.node-version', '.nvmrc', '.tool-versions'}:
            quotes = [line.strip() for line in text.splitlines()
                if re.fullmatch(r'(?:python\s+|nodejs\s+|v)?\d[\w.+ -]{0,70}', line.strip())]
        else:
            for line in text.splitlines():
                if len(line) > 800:
                    continue
                if re.search(r'\brequires-python\s*=|\bpython_requires\s*=', line):
                    quotes.append(line.strip())
                elif (re.search(r'\b(?:Python|Node(?:\.js)?)\s+(?:v?\d)', line, re.I)
                      and re.search(r'requir|support|install|\buse\b|需|要求|先|使用|支持', line, re.I)):
                    quotes.append(line.strip())
            if name == 'package.json':
                # A contiguous real engines block, not a dependency named node.
                quotes.extend(m[0] for m in re.finditer(r'"engines"\s*:\s*\{[^{}]{1,500}\}', text))
        if not quotes:
            continue
        quote = quotes[0]
        if quote in seen:
            continue
        step = GuideStep(step_id=0, stage='A', stage_label='环境搭建',
            title=f'核对 {doc.path} 中的运行时与工具要求',
            expected='先按原文核对运行时版本及所需工具，再进行该组件的依赖安装。安装方法未在本步骤执行；已有环境也要核对版本。',
            evidence=Evidence(source=doc.path, quote=quote))
        step.evidence = verify_step_evidence(step, sig)
        if step.evidence.verification != 'quote_verified':
            continue
        output.append(step)
        seen.add(quote)
        if len(output) == 4:
            break
    return output
