"""One-time 033a extraction. Checkpoints and paid records stay outside Git."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import load_settings
from app.display_summaries import generate, load_sections, source_hash, save, SYSTEM, EXAMPLES, PARAMETER_NAMES, PROMPT_VERSION
from app.paid_run import PaidRun, controlled_run, execution_limits, paid_request, provider_task
from app.providers import DeepSeekProvider, thinking_task

EXPERIMENT = 'EXP-20261114175011989842'
DATA = Path(__file__).resolve().parents[1]/'data'
OUTPUT_LIMIT = 2048
# Official CNY peak rates bound cost even if a later resume changes time period.
# https://api-docs.deepseek.com/zh-cn/quick_start/pricing/ (verified 2026-11-15)
PEAK_PRICES = {'input':2., 'output':8., 'max_output':OUTPUT_LIMIT, 'provider':'DeepSeek','currency':'CNY'}


class SummaryBudget(PaidRun):
    def begin(self, provider, model, payload):
        if len(self.calls) >= 40: raise RuntimeError('40 call limit reached')
        if self.stopped: raise RuntimeError('Paid run stopped')
        rates = self.prices.get(model)
        if provider != 'DeepSeek' or rates != PEAK_PRICES or payload.get('max_tokens') != OUTPUT_LIMIT:
            raise RuntimeError('Unrecognized summary request prices or output limit')
        bound = ((len(json.dumps(payload,ensure_ascii=False).encode())+1024)*rates['input']+OUTPUT_LIMIT*rates['output'])/1_000_000
        charged = sum(c.get('upper_estimate_yuan') if c.get('upper_estimate_yuan') is not None else c['reserved_yuan'] for c in self.calls)
        if charged + bound > 1.: raise RuntimeError('One yuan cap reached')
        return super().begin(provider,model,payload)


def usage_cost(usage):
    """Exact tokens and hit counters, official time-dependent CNY list prices."""
    prompt=usage.get('prompt_tokens'); completion=usage.get('completion_tokens')
    if any(type(n) is not int or n < 0 for n in (prompt,completion)): return None
    hit=usage.get('prompt_cache_hit_tokens'); miss=usage.get('prompt_cache_miss_tokens')
    if type(hit) is not int or type(miss) is not int or hit+miss != prompt: return None
    time=datetime.fromisoformat(usage['call_started_at']).astimezone(timezone.utc)
    # Only use the known weekend/off-window case; weekday peaks conservatively priced.
    peak=time.weekday()<5 and (1<=time.hour<4 or 6<=time.hour<10)
    return (hit*(.04 if peak else .02)+miss*(2 if peak else 1)+completion*(8 if peak else 4))/1_000_000


def run():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generate',action='store_true');args=parser.parse_args()
    sections=load_sections(DATA/'demo.db',EXPERIMENT)
    print(json.dumps({'sections':len(sections),'characters':[(s['round'],s['type'],s['candidate'],len(s['source'])) for s in sections]},ensure_ascii=False),flush=True)
    if not args.generate: return
    settings=load_settings()
    if settings.model != 'deepseek-flash' or not settings.configured: raise RuntimeError('Expected configured DeepSeek flash')
    directory=DATA/'display_summaries';directory.mkdir(exist_ok=True)
    save(directory/f'{PROMPT_VERSION}.prompt.json', {'system':SYSTEM,'examples':EXAMPLES,'parameter_names':PARAMETER_NAMES})
    path=directory/f'{EXPERIMENT}.json';ledger=directory/f'{EXPERIMENT}.ledger.json'
    identity={'experiment_id':EXPERIMENT,'source_sha256':source_hash(json.dumps(sections,ensure_ascii=False,sort_keys=True))}
    if ledger.exists():
        run=SummaryBudget.load_accounting(ledger,lambda:identity)
        if run.identity != identity: raise RuntimeError('Source changed; paid resume refused')
        if run.stopped == 'ProviderInvalidResponse' and all(c['status']=='ok' for c in run.calls):
            run.stopped=None;run.save()
    else:
        run=SummaryBudget(ledger,1.,{settings.model:PEAK_PRICES},identity,identity_check=lambda:identity,output_limits={'display_summary':OUTPUT_LIMIT})
    provider=DeepSeekProvider(settings)
    def call(system,user):
        with provider_task('display_summary'), execution_limits({'display_summary':OUTPUT_LIMIT}), thinking_task('auxiliary','off'):
            request=provider._request(system,user,True,False,temperature=0)
            # Reuse the existing transport with a single RPC, bypass its three-try wrapper.
            with paid_request('DeepSeek',settings.model,json.loads(request.data)):
                result=provider._complete_request(request,False)
        print(json.dumps({'call':len(run.calls),'input':result['input_tokens'],'output':result['output_tokens'],'yuan':usage_cost(result['usage'])},ensure_ascii=False),flush=True)
        return result
    with controlled_run(run): generate(sections,path,call,model=settings.model)
    rows=json.loads(path.read_text())['records']
    print(json.dumps({'records':len(rows),'passed':sum(r['status']=='通过' for r in rows),'calls':len(run.calls),'peak_upper_yuan':run.spent,'actual_list_yuan':sum(usage_cost(c['usage']) or 0 for c in run.calls)},ensure_ascii=False),flush=True)

if __name__ == '__main__': run()
