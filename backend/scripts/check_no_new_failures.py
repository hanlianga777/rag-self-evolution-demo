"""Compare a full backend pytest JUnit report with the 189b failure registry."""

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import re
from xml.etree import ElementTree

REGISTRY = Path(__file__).resolve().parents[2] / '指挥' / '报告' / '189.md'
MODULE = re.compile(r'^\[`(test_\w+)\.py`\].*（(\d+) 条）$')
ENTRY = re.compile(r'`([^\x60]+)`(?:\]\([^)]*\))?(?:（(\d+) 条）)?')


def registered_failures(path):
    appendix = path.read_text().split('### 附录 · 后端全套失败登记', 1)[1]
    allowed = Counter()
    module = None
    expected = 0
    for line in appendix.splitlines():
        if heading := MODULE.match(line):
            module = heading[1]
            expected += int(heading[2])
        elif module and line.startswith('- '):
            # Explanations may quote field names. Only pytest identities end in test_…
            for name, count in ENTRY.findall(line):
                if name.split('::')[-1].startswith('test_'):
                    allowed[(module, name)] += int(count or 1)
    if expected != 224 or sum(allowed.values()) != expected:
        raise ValueError(f'189b 失败登记应有 224 条，读取到 {sum(allowed.values())} 条')
    return allowed


def junit_failures(path):
    root = ElementTree.parse(path).getroot()
    summary = list(root.iter('testsuite'))
    if not summary or not any(int(suite.get('tests', 0)) for suite in summary):
        raise ValueError('JUnit 报告没有已执行用例')
    failed = Counter()
    for case in root.iter('testcase'):
        count = len(case.findall('failure')) + len(case.findall('error'))
        if count:
            parts = case.get('classname', '').split('.')
            module_index = next((i for i, part in enumerate(parts) if part.startswith('test_')), None)
            module = parts[module_index] if module_index is not None else '.'.join(parts)
            name = '::'.join([*(parts[module_index + 1:] if module_index is not None else []), case.attrib['name']])
            failed[(module, name)] += count
    return failed


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('junit_xml', type=Path, help='Full-suite report from pytest --junitxml')
    args = parser.parse_args()
    allowed = registered_failures(REGISTRY)
    actual = junit_failures(args.junit_xml)
    added = actual - allowed
    print(f'189b 登记 {sum(allowed.values())}，本轮失败或错误 {sum(actual.values())}，'
          f'重合 {sum((allowed & actual).values())}，新增 {sum(added.values())}')
    for (module, name), count in sorted(added.items()):
        print(f'{module}.py::{name} ({count})')
    return bool(added)


if __name__ == '__main__':
    raise SystemExit(main())
