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
