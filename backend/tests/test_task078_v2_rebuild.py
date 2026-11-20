"""078：重建接口固定用 parent-child-v2，并复用旧索引里的 MinerU 结果。"""
import io, json, zipfile
from pathlib import Path
from app.knowledge_pipeline import ACTIVE_CHUNK_VERSION, CachedMinerUParser


def _zip(blocks):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('x/content_list.json', json.dumps(blocks))
    return buf.getvalue()


def test_active_chunk_version_is_v2():
    assert ACTIVE_CHUNK_VERSION == 'parent-child-v2'


def test_cached_parser_reuses_saved_archive(tmp_path):
    (tmp_path / 'KNOW-1').mkdir()
    (tmp_path / 'KNOW-1' / 'DOC-A-mineru.zip').write_bytes(_zip([{'type': 'text', 'text': '正文', 'page_idx': 0}]))
    called = []
    parser = CachedMinerUParser(tmp_path, lambda: called.append(1))
    blocks, archive = parser.parse(Path('a.pdf'), 'DOC-A')
    assert blocks[0]['text'] == '正文' and archive.startswith(b'PK') and parser.hits == ['DOC-A'] and not called


def test_cached_parser_falls_back_when_missing(tmp_path):
    class Fake:
        def parse(self, path, document_id): return [{'type': 'text', 'text': 'new', 'page_idx': 0}], b'PK'
    parser = CachedMinerUParser(tmp_path, Fake)
    blocks, _ = parser.parse(Path('b.pdf'), 'DOC-B')
    assert blocks[0]['text'] == 'new' and parser.misses == ['DOC-B']


def _html(rows):
    return '<table>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</table>'


def test_v2_tables_repeat_generic_headers_like_v1():
    from app.knowledge_pipeline import _v2_block_text
    text = _v2_block_text({'type': 'table', 'table_body': _html([['维护活动', '定期地i', '每12个月'], ['检查信息标签', '', 'x']])})
    assert text == '维护活动=检查信息标签；定期地i=；每12个月=x'
    # 两列"参数 | 值"且首行就是数据的表，不把首行当表头
    assert _v2_block_text({'type': 'table', 'table_body': _html([['重量', '50 kg'], ['电压', '24 V']])}) == '重量 | 50 kg\n电压 | 24 V'


def test_v2_strips_page_flow_markers_glued_to_headings():
    from app.knowledge_pipeline import _v2_block_text
    assert _v2_block_text({'type': 'text', 'text': '1.1 关于 IRB 1200续前页'}) == '1.1 关于 IRB 1200'
    assert _v2_block_text({'type': 'text', 'text': '正文说明续前页内容不变'}) == '正文说明续前页内容不变'


def test_v2_strips_page_flow_markers_in_table_captions_and_footnotes():
    from app.knowledge_pipeline import _v2_block_text
    block = {'type': 'table', 'table_caption': ['4.2.2 维护计划续前页'], 'table_footnote': ['i 说明文字', '下一页继续'],
             'table_body': _html([['维护活动', '每12个月'], ['检查信息标签', 'x']])}
    assert _v2_block_text(block) == '4.2.2 维护计划\n维护活动=检查信息标签；每12个月=x\ni 说明文字'


def test_numbered_sections_keep_titles_and_short_parents():
    from app.knowledge_pipeline import parent_child_v2

    def heading(value, page=0, kind='text'):
        return {'type': kind, 'text_level': 1, 'text': value, 'page_idx': page}

    def body(value, page=0):
        return {'type': 'text', 'text': value, 'page_idx': page}

    blocks = [
        heading('目录'), heading('5 维修 70'), heading('5.4 摆动部和底座 90'),
        heading('5.4.1 更换底座 …… 90'), heading('5.4.2 检查底座 98'),
        heading('5.4.3 安装盖板 100'), heading('5.4.4 检查电缆 101'),
        heading('5.4.1 更换底座', 1), body('请参阅 5.4.2。', 1),
        heading('从下臂上分离电缆束', 1), body('先核对型号。', 1),
        heading('5.4.1 更换底座续前页', 2, 'header'), body('此页是同一章。', 2),
        heading('表 3', 2), heading('xx2300001370', 2, 'image'),
        heading('5.4.2 检查底座', 3), body('核对标签。', 3),
        heading('5.4.3 安装盖板', 4), body('归档。', 4),
        heading('5.4.4 检查电缆', 5), body('记录。', 5),
        heading('5.4.1 更换底座', 6), body('这是独立出现的同名小节。', 6),
    ]
    parents, children, _ = parent_child_v2({'id': 'DOC-TEST', 'name': '手册.pdf'}, blocks, len)
    titles = ['5.4.1 更换底座', '5.4.2 检查底座', '5.4.3 安装盖板', '5.4.4 检查电缆', '5.4.1 更换底座']
    assert [p['chapter'] for p in parents] == titles
    assert all(p['token_count'] < 400 for p in parents)
    assert [c['chunk_text'].splitlines()[0] for c in children] == titles
    for parent, title in zip(parents, titles):
        assert all(item not in parent['chunk_text'].splitlines() for item in set(titles) - {title})
    assert '此页是同一章。' in parents[0]['chunk_text']
    assert '从下臂上分离电缆束' in parents[0]['chunk_text']
    assert 'xx2300001370' not in parents[0]['chunk_text']


def test_denoise_removes_picture_ids_and_only_converts_simple_latex():
    from app.knowledge_pipeline import _v2_block_text
    text = r'xx1400000590' + '\n' + r'编号 xx1400000590；$580 \text{ ml}^{\text{i}}$；$DTC^{ij}$；$H_2O_2$；$-25^{\circ}C$；$\frac{a}{b}$'
    assert _v2_block_text({'type': 'text', 'text': text}) == r'编号 xx1400000590；580 ml；DTC；H2O2；-25°C；$\frac{a}{b}$'
