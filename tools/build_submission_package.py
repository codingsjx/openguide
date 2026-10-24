"""Package an explicit, credential-free candidate; never upload it anywhere."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build():
    selected = [ROOT / path for path in [
        'LICENSE', 'docs/submission.md', 'docs/submission_brief.md',
        'docs/evaluation_report.md', 'docs/release_closure_20261024.md',
        'docs/privacy_and_license.md', 'docs/third_party_disclosure.md',
        'docs/ai_assistance_disclosure.md', 'docs/video_script.md',
        'output/pdf/OpenGuide-作品说明.pdf',
        'output/video/OpenGuide-页面验收回放.mp4',
        'output/video/OpenGuide-页面验收回放.json',
        'output/video/OpenGuide-页面验收回放-预览.png',
    ]]
    missing=[path.relative_to(ROOT).as_posix() for path in selected if not path.is_file()]
    if missing:
        raise RuntimeError('Required candidate material is missing: ' + ', '.join(missing))
    selected += sorted((ROOT/'output/qa/release-20261024').glob('*'))
    selected = [p for p in selected if p.is_file()]
    secret = re.compile(r'sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')
    entries = []
    for path in selected:
        if not path.resolve().is_relative_to(ROOT) or path.name == '.env':
            raise ValueError('Refusing a file outside the explicit workspace')
        data = path.read_bytes()
        if path.suffix.lower() in {'.md', '.json', '.txt'} and secret.search(data.decode('utf-8-sig')):
            raise ValueError('Possible credential in candidate; no bundle written')
        entries.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'date': '2026-10-24', 'status': 'candidate_pending_team_review', 'files': entries,
        'not_included': ['credentials', 'raw model prompts/responses', 'raw installation/test logs', 'personal learning notes'],
        'pending': ['independent human review', 'human outcomes', 'stable model generation', 'team rights and final submission review']}
    target = ROOT/'output/submission-candidate-20261024.zip'
    start = ('OpenGuide 参赛材料候选包，2026-10-24\n\n'
        '请先阅读 docs/release_closure_20261024.md，再核对报告、资源清单和数据范围。\n'
        'PDF 为 7 页当前工作稿；视频约 4 分钟，明确标为截图回放、无配音、非实时完整录屏。\n'
        '模型对照未取得可计分结果，真实产品请求最终全部规则回退；不能写成模型效果提升。\n'
        '真人试用、独立人工复核、团队对代码/AI 辅助内容/授权及最终材料的实际审核仍需完成。\n'
        '代码与复现入口：https://github.com/codingsjx/openguide\n'
        '本工具只生成本机候选包，没有登录或提交赛事平台。\n')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr('请先阅读.txt', start)
        archive.writestr('candidate-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in selected:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for entry in entries:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']
    manifest.update(bundle_bytes=target.stat().st_size, bundle_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    target.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'bundle': str(target), 'bytes': target.stat().st_size, 'files': len(entries), 'crc_and_hashes_verified': True}, ensure_ascii=False))


if __name__ == '__main__':
    build()
