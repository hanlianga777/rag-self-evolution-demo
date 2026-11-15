"""Deterministic request and ranking boundaries; no live Provider calls."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.config import Settings, load_settings
from app.policy import DEFAULT_PIPELINE_CONFIG, ALLOWED_SEARCH_SPACE
from app.providers import DeepSeekProvider, judge_thinking, thinking_task, thinking_config
from app.retrieval import LocalRetriever, VectorRetriever


class StableRequests(unittest.TestCase):
    def test_defaults_and_judge_off(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('')
            settings = load_settings({}, env)
            self.assertEqual(settings.baseline_thinking, 'off')
            self.assertEqual(settings.judge_thinking, 'off')
            self.assertEqual(load_settings({'JUDGE_THINKING':'off'}, env).judge_thinking, 'off')
        with judge_thinking('off'):
            self.assertEqual(thinking_config('judge'), {'task':'judge', 'thinking':{'type':'disabled'}})

    def test_generation_and_query_calls_force_off_and_zero_despite_old_override(self):
        provider = DeepSeekProvider(Settings('fixture', 'https://example.invalid', 'deepseek-flash'))
        for task in ('baseline','candidate','generation','answer','query_rewrite','multi_query','hyde','query_decompose','query','auxiliary'):
            with self.subTest(task=task), thinking_task(task, 'max'):
                payload = json.loads(provider._request('system', 'user', False, False, .9).data)
                self.assertEqual(payload['thinking'], {'type':'disabled'})
                self.assertEqual(payload['temperature'], 0)
                self.assertNotIn('reasoning_effort', payload)
                self.assertNotIn('seed', payload)  # DeepSeek API has no documented seed.
        with judge_thinking('off'), thinking_task('judge'):
            payload = json.loads(provider._request('system', 'user', True, False, .9).data)
            self.assertEqual(payload['temperature'], 0)

    def test_off_baseline_never_requires_thinking_efficiency_compensation(self):
        from app.optimization import validate_round_contract, build_agent_prompt
        candidates = [{'id':label, 'config_diff':diff} for label,diff in zip('ABC', ({'top_k':6},{'candidate_k':24},{'prompt_strategy':'Tiered'}))]
        validate_round_contract(candidates, DEFAULT_PIPELINE_CONFIG, [], completed=6)
        system, prompt = build_agent_prompt([], DEFAULT_PIPELINE_CONFIG, [], [], list('ABC'), evaluation_budget={'used':6})
        self.assertFalse(prompt['round_contract']['efficiency_optimization'])
        self.assertNotIn('generation_thinking', prompt['allowed_parameter_values'])
        self.assertNotIn('Max降到High', system)

    def test_agent_cannot_tune_generation_thinking(self):
        self.assertEqual(DEFAULT_PIPELINE_CONFIG['generation_thinking'], 'off')
        self.assertEqual(ALLOWED_SEARCH_SPACE['generation_thinking'], ('off',))


class StableRanking(unittest.TestCase):
    def test_local_ties_ignore_document_input_order(self):
        documents = [{'name':name, 'samples':['相同内容']} for name in ('乙','甲')]
        left = LocalRetriever(documents).search('相同内容')
        right = LocalRetriever(list(reversed(documents))).search('相同内容')
        self.assertEqual(left, right)

    def test_bm25_sum_is_hash_order_independent(self):
        # A stable term sequence matters because floating point addition is not associative.
        chunks = [{'chunk_id':str(i), 'chunk_text':'甲乙丙丁戊己庚辛壬癸'[:i%10+1]} for i in range(20)]
        retriever = VectorRetriever(SimpleNamespace(chunks=lambda: chunks))
        with patch('app.retrieval._terms', side_effect=lambda s: list('甲乙丙丁戊己庚辛壬癸') if s == 'question' else set(s)):
            first = retriever._bm25('question')
        with patch('app.retrieval._terms', side_effect=lambda s: list(reversed('甲乙丙丁戊己庚辛壬癸')) if s == 'question' else set(s)):
            second = retriever._bm25('question')
        self.assertEqual(first, second)
