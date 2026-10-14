"""Offline prompt contract checks, not model-behavior acceptance."""
import unittest
from app.ai_service import generation_context, GENERATION_BOUNDARY

class SourceContextTests(unittest.TestCase):
    def test_source_identity_and_verbatim_content_survive_without_inferred_version(self):
        import json
        text='请勿自行换件。\n保留完整原文'
        entry={'chunk_id':'C1','parent_chunk_id':'P1','document_id':'D1','document':'设备手册','product':'B2','vendor':'宇树','section_path':'开机','page_start':3,'page_end':4,'content':text}
        value=generation_context([entry]);saved=json.loads(value.splitlines()[0])['sources']['S1']
        self.assertIn(text,value)
        self.assertIn('[C1 | S1 | 开机 | 页3–4]',value)
        self.assertEqual(saved['product'],'B2')
        self.assertNotIn('version',saved)
        entry['version']='V2.1'
        self.assertEqual(json.loads(generation_context([entry]).splitlines()[0])['sources']['S1']['version'],'V2.1')

    def test_boundary_explicitly_covers_operations_and_source_scope(self):
        for value in ['型号','版本','换件','测量','上电','测试','拒答','官方','保守']:
            self.assertIn(value,GENERATION_BOUNDARY)

    def test_actual_generation_request_uses_metadata_and_operation_boundary(self):
        from types import SimpleNamespace
        from app.ai_service import AiService
        class Provider:
            settings=SimpleNamespace(configured=True,model='offline-fixture')
            def complete_with_metrics(self,system,user,**kwargs):
                self.request=(system,user)
                return {'content':'离线占位，不是模型结果','ttft_ms':0,'input_tokens':0,'output_tokens':0,'usage':{}}
        provider=Provider();service=AiService(object(),object(),provider,False)
        entries=[{'chunk_id':'C1','document':'设备说明','product':'B2','section':'操作','page_start':1,'parent_page_start':1,'parent_page_end':2,'content':'仅适用于B2。'}]
        service.retriever=SimpleNamespace(retrieve=lambda *args,**kwargs:entries)
        service.answer('普通技术问题')
        self.assertIn(GENERATION_BOUNDARY,provider.request[0])
        self.assertIn('"product":"B2"',provider.request[1])
        self.assertIn('页1–2',provider.request[1])
        self.assertIn('仅适用于B2。',provider.request[1])

    def test_shared_document_identity_is_sent_once_and_body_is_not_json_escaped(self):
        entries=[{'chunk_id':str(i),'document_id':'D1','document':'很长的同一份设备手册.pdf','product':'B2','content':'第一行\n第二行'} for i in range(4)]
        value=generation_context(entries)
        self.assertEqual(value.count('很长的同一份设备手册.pdf'),1)
        self.assertEqual(value.count('第一行\n第二行'),4)
