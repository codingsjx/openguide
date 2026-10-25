"""Conservative component/purpose filtering over actual repository documents."""
import re
from backend.core.generate.command_context import STAGE_COMMAND_PATTERNS


def component_mentions(text: str) -> set[str]:
    result = set()
    if '前后端' in text: return {'backend','frontend'}
    if re.search(r'后端|服务端|(?<![a-z0-9_])back[- ]?end(?![a-z0-9_])', text, re.I): result.add('backend')
    if re.search(r'前端|客户端|(?<![a-z0-9_])front[- ]?end(?![a-z0-9_])', text, re.I): result.add('frontend')
    return result


def question_component(question: str, history: list[str], context_used: bool) -> str | None:
    labels = component_mentions(question)
    if not labels and context_used:
        labels = next((component_mentions(q) for q in reversed(history) if component_mentions(q)), set())
    return next(iter(labels)) if len(labels) == 1 else None


def path_component(path: str) -> str | None:
    for part in path.lower().replace('\\','/').split('/'):
        if part in {'backend','server','api'}: return 'backend'
        if part in {'frontend','client','web'}: return 'frontend'
    return None


def source_allowed(path: str, query: str, component: str | None, intent: str) -> bool:
    low = path.lower()
    belongs = path_component(path)
    if component and belongs and belongs != component: return False
    if intent in {'setup','test'}:
        parts = low.split('/')[:-1]
        if any(p in {'benchmark','benchmarks'} for p in parts) and not re.search(r'benchmark|评测|消融|基准',query,re.I): return False
        if any(p in {'examples','fixtures','samples'} for p in parts) and not re.search(r'example|fixture|sample|示例|样例',query,re.I): return False
        if low.startswith('.github/workflows/') and not re.search(r'\bCI\b|workflow|持续集成|流水线',query,re.I): return False
    return True


def component_excerpt(full: str, path: str, text: str, component: str | None, intent: str | None = None):
    """Return a real contiguous section and its bounds; never synthesize text."""
    if not component or path_component(path) == component:
        return text, None
    headings, fence, offset = [], None, 0
    for line in full.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})',line)
        if match:
            if fence is None: fence=match[1]
            elif match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line[match.end():].strip(): fence=None
        elif fence is None:
            heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+)',line)
            if heading: headings.append((offset,len(heading[1]),component_mentions(heading[2])))
        offset += len(line)
    ranges=[]
    for i,(start,level,labels) in enumerate(headings):
        if labels != {component}: continue
        end=next((s for s,l,_ in headings[i+1:] if l<=level),len(full))
        ranges.append((start,end))
    clean='\n'.join(line for line in text.splitlines() if not re.match(r'^===== .+ =====\s*$',line.strip())).strip()
    pos=full.find(clean)
    stage={'setup':'A','test':'B'}.get(intent)
    def relevant(value):
        return stage is None or any(re.match(STAGE_COMMAND_PATTERNS[stage],line.strip()) for line in value.splitlines())
    containing=next(((s,e) for s,e in ranges if pos>=0 and s<=pos<e),None)
    if containing and (relevant(full[containing[0]:containing[1]]) or not relevant(clean)):
        start,end=containing
        return full[start:min(end,start+1600)], (start,end)
    # A shared testing chapter can sit outside headings named backend/frontend.
    # Preserve the retrieved operation instead of replacing it with the first
    # component's installation chapter elsewhere in the document.
    for block in re.finditer(r'(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$',full):
        if pos>=0 and block.start()<pos+len(clean) and block.end()>pos and component_mentions(block[0])=={component} and relevant(block[0]):
            return block[0],block.span()
    other = 'frontend' if component=='backend' else 'backend'
    other_ranges=[(s,next((end for end,level,_ in headings[i+1:] if level<=l),len(full)))
                  for i,(s,l,labels) in enumerate(headings) if labels=={other}]
    if (pos>=0 and any(s<=pos<e for s,e in other_ranges) and component not in component_mentions(clean)) or component_mentions(clean)=={other}:
        return None
    return text, None
