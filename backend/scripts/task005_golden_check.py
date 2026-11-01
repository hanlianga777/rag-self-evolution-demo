#!/usr/bin/env python3
"""Repeatable, read-only CSV inspection against a local parsed manual index.

C3/C4 use explainable literal vocabulary, not a semantic judge. C7 retrieves
candidates only. No database, network, embedding model or third-party dependency.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import re
import unicodedata

PASS, FAIL, NA = '通过', '不通过', '不适用'
EVIDENCE_MARK = re.compile(r'【证据\s*(\d+)】')
QUALIFIER = re.compile(r'不以此替代|未(?:明确|说明|写明|载明|交代)|不宣称|不(?:得)?(?:把|将)?[^。；;\n]{0,30}(?:扩大为|扩展为|扩用|泛化为)|不能替代|不擅自|不外推')
# Stable domain vocabulary, shared by every row. Missing literal words are listed
# for manual review; synonyms are never silently treated as verified evidence.
OBJECTS = ('一般设置 设定时区 时区 快速模式 警告灯 设置 菜单 按钮 开关 急停 安全开关 '
           '安全扫描器 激光扫描器 扫描器 后部 前部 对接站 电源插头 电池插头 插头 插座 '
           '电池 电源 遥控器 充电器 充电 电量 电压 电流 温度 电芯 电池仓 电池包 '
           '电池锁 扳机 摇杆 按键 刷头 清洁刷 刷辊 毛刷 清水箱 污水箱 水箱 水位 '
           '吸水扒 吸水梁 吸尘 气泵 清洁剂 酒精 火灾 爆炸 触电 电击 湿手 '
           '自动清洁 手动模式 自动模式 清洁模式 任务 地图 路线 区域 位置 位置码 '
           '坡度 速度 电机 风扇 滤网 过滤器 盖板 软管 高压 保险丝 轮子 '
           '漏水 倾倒 装载 运输 维护 保养 密码 主管 用户 权限 蓝牙 配对 电池管理系统 '
           '熔断器 充电接口 接口 指示灯 LED HDMI USB 保险杠 碰撞 悬崖 传感器 '
           '手套 防护装备 清洁对象 代码 制动器 制动测试 制动 红色 杠杆 机器人 售后 '
           '清洁报告 重伤 死亡 伤害 危险 警告 小心 财产损失').split()
ACTIONS = ('按下 点击 选择 设置 打开 关闭 关机 开机 启动 停止 拔出 拔下 断开 连接 '
           '取下 装上 安装 拆卸 更换 清洁 清洗 冲洗 擦拭 检查 充电 放电 断电 按住 松开 '
           '推动 拉动 转动 短接 绕过 屏蔽 禁止 严禁 不得 允许 等待 进入 退出 '
           '激活 停用 调整 抬起 放下 移动 补充 排空 注入 重启 解锁 锁定').split()
GENERIC = {'按钮', '按键', '设置', '菜单', '清洁', '检查', '连接', '接口', '位置', '模式'}


def normalize(text):
    """NFKC, case-fold, remove whitespace/punctuation (not arbitrary symbols)."""
    text = unicodedata.normalize('NFKC', str(text)).casefold()
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def parse_requirements(text):
    """Extract mandatory atoms from original tagged or revised numbered text."""
    if '【必答' in text:
        parts = re.split(r'(?=【)', text)
        tagged = []
        for part in parts:
            if re.match(r'【必答(?:原子)?】', part):
                body = re.sub(r'^【[^】]+】\s*', '', part).strip()
                identifier = re.match(r'^([A-Za-z0-9_.-]+)[：:]\s*', body)
                atom_id = identifier.group(1) if identifier else ''
                body = body[identifier.end():] if identifier else body
                if body:
                    tagged.append((atom_id, body, part.startswith('【必答原子】')))
        return [body for atom_id, body, is_leaf in tagged
                if is_leaf or not atom_id or not any(other.startswith(atom_id+'.') for other, _, leaf in tagged if leaf)]
    return [re.sub(r'^\s*(?:\d+[.、．）)]|[-•])\s*', '', line).strip()
            for line in text.splitlines() if line.strip() and not line.lstrip().startswith('【')]


def parse_evidence(text):
    matches = list(EVIDENCE_MARK.finditer(text))
    if not matches:
        return [('1', text.strip())] if text.strip() else []
    return [(m.group(1), text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip())
            for i, m in enumerate(matches)]


def lexical_terms(text):
    normalized = normalize(text)
    numbers = re.findall(r'\d+(?:[.,]\d+)?\s*(?:%|℃|°c|km/h|mm|cm|kg|mah|ah|mv|v|a|w|秒|分钟|小时|米|度)?',
                         unicodedata.normalize('NFKC', text).casefold())
    quoted = re.findall(r'[“「『"]([^”」』"\n]{2,30})[”」』"]', text)
    objects = [word for word in OBJECTS if normalize(word) in normalized]
    # Keep the more specific component (e.g. 电池插头) instead of all substrings.
    objects = [word for word in objects if not any(word != other and word in other for other in objects)]
    actions = [word for word in ACTIONS if word in normalized]
    return {'数字单位': list(dict.fromkeys(normalize(t) for t in numbers)),
            '引号词': quoted, '部件主题': objects, '动作词': actions}


def flat_terms(terms):
    return list(dict.fromkeys(t for group in terms.values() for t in group))


def support_fragments(point, evidence):
    """Literal shared phrases; remove generic filler before accepting a phrase."""
    point = normalize(point)
    evidence = normalize(evidence)
    found = []
    for run in re.findall(r'[\u4e00-\u9fff]+', point):
        for size in range(min(len(run), 16), 3, -1):
            for offset in range(len(run)-size+1):
                phrase = run[offset:offset+size]
                if phrase not in evidence or any(phrase in existing for existing in found):
                    continue
                content = phrase
                for generic in sorted(GENERIC | {'设备', '手册', '说明书', '按照', '根据', '进行', '需要', '可以'}, key=len, reverse=True):
                    content = content.replace(generic, '')
                if len(content) >= 2:
                    found.append(phrase)
    found.extend(term for term in re.findall(r'[a-z]{2,}[a-z0-9]*', point)
                 if term in evidence and term not in {'cm', 'mm', 'km', 'kg', 'mah', 'ah', 'mv', 'kw'})
    return found


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class GoldenChecker:
    def __init__(self, index_dir):
        index_dir = Path(index_dir)
        def read(name):
            return json.loads((index_dir / name).read_text(encoding='utf-8'))
        self.children = read('chunks.json')
        self.parents = read('parents.json')
        documents = read('documents.json')
        self.documents = {d['id']: d['name'] for d in documents}
        self.model_tokens = set()
        for document in documents:
            self.model_tokens.update(re.findall(r'[a-z0-9]+', str(document.get('product', '')).casefold()))
        self.pages = read('full_text.json')['pages']
        self.normal_children = [(c, normalize(c.get('text', c.get('chunk_text', '')))) for c in self.children]
        self.normal_parents = [(c, normalize(c.get('text', c.get('chunk_text', '')))) for c in self.parents]
        # full_text carries real page numbers. Block-order text is an additional
        # exact-text source where page aggregation extraction differs.
        self.streams = []
        for doc_id in self.documents:
            pages = sorted([p for p in self.pages if p['document_id'] == doc_id], key=lambda p: p['page'])
            self.streams.append(self.page_stream(doc_id, pages, 'full_text'))
            block_file = index_dir / (doc_id + '-blocks.json')
            if block_file.exists():
                blocks = json.loads(block_file.read_text(encoding='utf-8'))
                self.streams.append(self.page_stream(doc_id, blocks, 'blocks'))

    def page_stream(self, doc_id, records, source):
        text, spans = '', []
        for record in records:
            part = normalize(record.get('text', ''))
            if part:
                spans.append((len(text), len(text)+len(part), int(record['page'])))
                text += part
        return {'document_id': doc_id, 'source': source, 'text': text, 'spans': spans}

    def source_matches(self, evidence):
        needle = normalize(evidence)
        if not needle:
            return []
        found = []
        for stream in self.streams:
            start = stream['text'].find(needle)
            while start >= 0:
                end = start + len(needle)
                pages = sorted({p for a, b, p in stream['spans'] if a < end and b > start})
                item = {'文档': self.documents[stream['document_id']], '页': pages, '来源': stream['source'], '归一化位置': start}
                if not any(m['文档'] == item['文档'] and m['页'] == pages for m in found):
                    found.append(item)
                start = stream['text'].find(needle, start+1)
        return found

    def chunk_matches(self, evidence, entries):
        needle = normalize(evidence)
        return [{'块': c['chunk_id'], '文档': c.get('document_name', self.documents.get(c['document_id'], '')), '归一化位置': text.find(needle)}
                for c, text in entries if needle and needle in text]

    def page_claim(self, text):
        match = re.search(r'第\s*([\d\s、,，\-–至到]+)\s*页', text)
        if not match:
            return text, []
        page_text = match.group(1)
        range_match = re.fullmatch(r'\s*(\d+)\s*[-–至到]\s*(\d+)\s*', page_text)
        pages = list(range(int(range_match[1]), int(range_match[2])+1)) if range_match else [int(n) for n in re.findall(r'\d+', page_text)]
        document = text[:match.start()].strip(' \n，,：:')
        return document, sorted(set(pages))

    def retrieve(self, question):
        # BM25 over child passages, using business words rather than product-name
        # cover matches. Actual page locations still come from raw parsed text.
        def tokens(text):
            parts = re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', unicodedata.normalize('NFKC', text).casefold())
            base = [token for part in parts for token in ([part] if not re.match(r'[\u4e00-\u9fff]', part) else [part[i:i+2] for i in range(max(1, len(part)-1))])]
            return base + ['@'+unit for unit in ('秒', '分钟', '小时') if unit in text]
        query_text = unicodedata.normalize('NFKC', question).casefold()
        for generic in ('客户', '操作员', '说明书', '手册', '资料', '现有', '官方', '具体', '确认', '标准', '有没有', '能不能', '是否', '请问', '现在', '这个', '根据', '给出'):
            query_text = query_text.replace(generic, ' ')
        query = set(tokens(query_text)) - self.model_tokens
        if re.search(r'多久|多长时间|时长|时间', query_text):
            query.update({'@秒', '@分钟', '@小时'})
        action_terms = {action for action in ACTIONS if action in query_text and action not in GENERIC and len(action) >= 2}
        # Latin identifiers in document names are metadata, not useful query
        # evidence. Remove only literal isolated model tokens, never 电池/充电器.
        name_tokens = {token for name in self.documents.values() for token in re.findall(r'[a-z0-9]+', name.casefold())}
        query -= name_tokens | {'pdf', 'kira', 'b2'}
        entries = [(chunk, Counter(tokens(chunk.get('text', chunk.get('chunk_text', ''))))) for chunk in self.children
                   if chunk.get('text', chunk.get('chunk_text', '')).strip()]
        total = len(entries)
        average = sum(sum(count.values()) for _, count in entries) / max(total, 1)
        df = Counter(t for _, count in entries for t in query if t in count)
        scored = []
        for chunk, counts in entries:
            length = sum(counts.values())
            matched = sorted(query & counts.keys())
            score = sum(math.log(1+(total-df[t]+0.5)/(df[t]+0.5))*counts[t]*2.2 /
                        (counts[t]+1.2*(0.25+0.75*length/max(average, 1))) * (3 if t in action_terms else 1) for t in matched)
            scored.append({'块': chunk['chunk_id'], '文档': self.documents[chunk['document_id']],
                           '分数': round(score, 5), '命中词': matched,
                           '原文': chunk.get('text', chunk.get('chunk_text', ''))})
        top = sorted(scored, key=lambda p: -p['分数'])[:3]
        for hit in top:
            hit['实际位置'] = self.source_matches(hit['原文'])
        return top

    def check(self, row):
        required = parse_requirements(row.get('必答要点', ''))
        evidence = parse_evidence(row.get('标准证据原文（逐字）', ''))
        claims = dict(parse_evidence(row.get('证据所在文档和页码', '')))
        positive = row.get('题型') in ('正向', '消融')
        result = {k: row.get(k, '') for k in ('题号', '题型', '负向子类', '问题')}
        top_count = len(re.findall('【必答】', row.get('必答要点', ''))) if '【必答' in row.get('必答要点', '') else len(required)
        result.update({'必答条数': top_count, '必答顶层条数': top_count, '必答原子数': len(required), '条件条数': len(re.findall('【条件】', row.get('必答要点', ''))), '证据段数': len(evidence)})
        for i in range(1, 9):
            result['C'+str(i)] = NA
            result['C'+str(i)+'_详情'] = ''
        locations, children, pages = [], [], []
        for number, text in evidence:
            matches = self.source_matches(text)
            locations.append({'证据': number, '命中': matches, '原文': text})
            child = self.chunk_matches(text, self.normal_children)
            parent = self.chunk_matches(text, self.normal_parents)
            children.append({'证据': number, '子块命中': child, '母块命中': parent,
                             '说明': '单个子块完整包含' if child else '仅母块完整包含，跨子块或仅存在母块' if parent else '无完整子块/母块命中；可能跨块或文字不符'})
            document, claimed_pages = self.page_claim(claims.get(number, ''))
            consistent = any(m['文档'] == document and m['页'] == claimed_pages for m in matches)
            pages.append({'证据': number, '标注文档': document, '标注页': claimed_pages, '实际位置': matches, '一致': consistent})
        if evidence:
            for code, data, passed in [('C1', locations, all(d['命中'] for d in locations)), ('C2', children, all(d['子块命中'] for d in children)), ('C8', pages, all(d['一致'] for d in pages))]:
                result[code] = PASS if passed else FAIL
                result[code+'_详情'] = dump(data)
        elif positive:
            for code in ('C1', 'C2', 'C8'):
                result[code], result[code+'_详情'] = FAIL, '正向/消融题未提供标准证据'
        if positive:
            all_evidence = normalize('\n'.join(text for _, text in evidence))
            diagnostics, support = [], []
            for i, point in enumerate(required, 1):
                terms = lexical_terms(point)
                missing = [term for term in flat_terms(terms) if normalize(term) not in all_evidence]
                literal = bool(normalize(point)) and normalize(point) in all_evidence
                diagnostics.append({'要点': i, '内容': point, '全文逐字命中': literal, '关键词': terms, '缺少': missing, '无关键词待人工核验': not flat_terms(terms) and not literal})
            for number, text in evidence:
                normalized = normalize(text)
                matching = []
                for i, point in enumerate(required, 1):
                    terms = lexical_terms(point)
                    anchors = terms['数字单位'] + terms['引号词'] + [t for t in terms['部件主题'] if t not in GENERIC]
                    actions = [t for t in terms['动作词'] if t not in GENERIC]
                    # Specific literal subjects/numbers are support candidates; action
                    # paraphrases are left to the stricter C3 missing-word report.
                    # Generic action/button overlap alone never establishes support.
                    literal = bool(normalize(point)) and normalize(point) in normalized
                    fragments = support_fragments(point, text)
                    specific = [t for t in terms['部件主题'] if t not in GENERIC and len(normalize(t)) >= 3 and normalize(t) in normalized]
                    missing = [t for t in anchors if normalize(t) not in normalized]
                    thematic = [t for t in terms['部件主题'] + terms['引号词']
                                if t not in GENERIC and not re.fullmatch(r'[\d.]+', normalize(t)) and normalize(t) in normalized]
                    if literal or fragments or specific or (thematic and not missing):
                        matching.append({'要点': i, '全文逐字命中': literal, '匹配方式': '全文' if literal else '关键词部分支撑', '共同连续片段': fragments, '命中关键词': [a for a in anchors if normalize(a) in normalized], '命中动作': [a for a in actions if normalize(a) in normalized]})
                support.append({'证据': number, '支撑要点': matching})
            result['C3'] = PASS if required and all(not d['缺少'] and not d['无关键词待人工核验'] for d in diagnostics) else FAIL
            result['C3_详情'] = dump(diagnostics)
            result['C4'] = PASS if evidence and all(d['支撑要点'] for d in support) else FAIL
            result['C4_详情'] = dump(support)
            # A single atom cannot by itself establish that a multipart question
            # only asks one thing. Flag visibly for human inspection.
            multi = bool(re.search(r'以及|分别|同时|另外|此外|还[要需]|[？?].+[？?]|[；;]', row.get('问题', '')))
            count_ok = 2 <= top_count <= 3 or (top_count == 1 and not multi)
            result['C5'] = PASS if count_ok else FAIL
            result['C5_详情'] = f'必答顶层{top_count}条/原子{len(required)}条；问题多事项标记={multi}（单条题需人工确认问题只问一件事）'
        risky = []
        # Conditional atoms in the original mandatory field are still requirements
        # for C6; bonus items are not mandatory. New bonus/prohibition columns are
        # not counted as must-answer atoms.
        conditions = re.findall(r'【条件】(.*?)(?=【|\Z)', row.get('必答要点', ''), re.S)
        for i, point in enumerate(required + conditions, 1):
            qualifier = QUALIFIER.findall(point)
            length = len(normalize(point))
            if qualifier or length > 40:
                risky.append({'要点': i, '内容': point, '限定语': qualifier, '归一化字数': length})
        result['C6'], result['C6_详情'] = (FAIL if risky else PASS), dump(risky)
        insufficient = row.get('负向子类') in ('证据不足', 'insufficient_evidence') or 'insufficient_evidence' in row.get('必答要点', '')
        if insufficient:
            hits = self.retrieve(row.get('问题', ''))
            result['C7'] = PASS if len(hits) == 3 else FAIL
            result['C7_详情'] = dump({'说明': '仅本地BM25候选，不自动判断有无答案，需人工逐段核验', 'top3': hits})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--index-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'data/index')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    checker = GoldenChecker(args.index_dir)
    with args.csv.open(encoding='utf-8-sig', newline='') as handle:
        results = [checker.check(row) for row in csv.DictReader(handle)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]) if results else ['题号'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(results)
    print(dump({'题数': len(results), '检查': {f'C{i}': dict(Counter(r[f'C{i}'] for r in results)) for i in range(1, 9)}, '付费调用': 0}))


if __name__ == '__main__':
    main()
