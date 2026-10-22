"""Offline syntax recovery never manufactures a completed semantic review."""
import json
import unittest
from types import SimpleNamespace
from app.ai_service import AiService
from app.providers import ProviderInvalidResponse
import test_evidence_resolver_v5 as fixtures
from app.evidence_resolver import resolve_case


class DiagnosticResponseParsingTests(unittest.TestCase):
    def response(self):
        fixture=fixtures.ResolverTests();q,case,chunks,hit,identity=fixture.example()
        captured=[]
        resolve_case(case,q,chunks,identity,semantic=lambda p:captured.append(p) or {})
        response=fixture.semantic(captured[0]);response['requirements_complete']=False
        return {k:response[k] for k in ('requirements_complete','facts','check_roles')},(q,case,chunks,identity)

    def parse(self,raw):
        service=object.__new__(AiService);service.force_mock=False
        service.provider=SimpleNamespace(settings=SimpleNamespace(model='offline-fixture'),complete=lambda *a,**kw:raw)
        try:return service.resolve_diagnostic({'offline':True})
        except ProviderInvalidResponse as error:self.fail(str(error))

    def test_one_missing_fact_object_closer_restores_only_syntax_and_stays_blocked(self):
        response,(q,case,chunks,identity)=self.response()
        response['requirements_complete_reason']='offline fixture: review remains incomplete'
        raw=json.dumps(response,ensure_ascii=False)
        pos=raw.index('], "check_roles"')
        self.assertEqual(raw[pos-1],'}');broken=raw[:pos-1]+raw[pos:]
        parsed=self.parse(broken)
        self.assertEqual({k:parsed[k] for k in response},response)
        self.assertEqual(parsed['_raw_response'],broken)
        self.assertEqual(parsed['_json_recovery']['inserted'],'}')
        self.assertEqual(parsed['_json_recovery']['offset'],pos-1)
        result=resolve_case(case,q,chunks,identity,semantic=lambda _:parsed)
        self.assertEqual(result['blockers'],['semantic_requirements_not_complete'])
        self.assertEqual(result['findings'],[])

    def test_valid_json_preserves_false_and_brackets_inside_quotes(self):
        response,_=self.response();response['facts'][0]['stages']['answer']['reason']='literal }], "check_roles": must remain text'
        raw=json.dumps(response,ensure_ascii=False);parsed=self.parse(raw)
        self.assertEqual({k:parsed[k] for k in response},response)
        self.assertIsNone(parsed['_json_recovery'])

    def test_truncation_missing_comma_duplicate_key_and_multiple_missing_braces_rejected(self):
        response,_=self.response();raw=json.dumps(response,ensure_ascii=False);pos=raw.index('], "check_roles"')
        invalid=[raw[:-1],raw.replace(', "check_roles"', ' "check_roles"'),raw[:pos-2]+raw[pos:],raw.replace('"requirements_complete": false','"requirements_complete": true, "requirements_complete": false')]
        for text in invalid:
            service=object.__new__(AiService);service.force_mock=False
            service.provider=SimpleNamespace(settings=SimpleNamespace(model='offline-fixture'),complete=lambda *a,**kw:text)
            with self.subTest(text=text[-65:]),self.assertRaises(ProviderInvalidResponse):service.resolve_diagnostic({})

    def test_paraphrased_reference_uses_distinct_real_source_quote_without_weakening_cover(self):
        fixture=fixtures.ResolverTests();q,case,chunks,hit,identity=fixture.example()
        reference='保养之前先隔离电池供电。'
        q['reference_answer']=reference;case['reference_answer']=reference
        def semantic(payload):
            response=fixture.semantic(payload)
            fact=response['facts'][0]
            fact['reference_support']=[{'source_id':'norm-new','quote':chunks[0]['chunk_text']}]
            return response
        result=resolve_case(case,q,chunks,identity,semantic=semantic)
        self.assertEqual(result['status'],'resolved',result['blockers'])
        self.assertEqual(result['findings'][0][0],'Retrieval')
        def omitted(payload):
            response=semantic(payload);response['facts'][0]['golden_quote']=reference[:-5]
            return response
        rejected=resolve_case(case,q,chunks,identity,semantic=omitted)
        self.assertIn('frozen_reference_or_failed_checks_not_fully_reviewed',rejected['blockers'])
        self.assertEqual(rejected['findings'],[])
