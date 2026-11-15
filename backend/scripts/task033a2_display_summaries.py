"""033a2: free saved-response replay, then at most two calls per failed section."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import load_settings
from app.display_summaries import (revalidate_saved, redo_failed, load_sections, source_hash,
                                   canonical, save, SYSTEM, EXAMPLES, PARAMETER_NAMES, PROMPT_VERSION)
from app.paid_run import PaidRun, controlled_run, execution_limits, paid_request, provider_task
from app.providers import DeepSeekProvider, thinking_task
from task033a_display_summaries import DATA, EXPERIMENT, usage_cost

REDO_PRICES = {'input':2.,'output':8.,'max_output':4096,'provider':'DeepSeek','currency':'CNY'}


class RedoBudget(PaidRun):
    def begin(self, provider, model, payload):
        if len(self.calls) >= 24: raise RuntimeError('24 call limit reached')
        rates = self.prices.get(model)
        limit = payload.get('max_tokens')
        if provider != 'DeepSeek' or rates != REDO_PRICES or limit not in (2048,4096):
            raise RuntimeError('Unrecognized redo request prices or output limit')
        bound = ((len(json.dumps(payload,ensure_ascii=False).encode())+1024)*rates['input']+limit*rates['output'])/1_000_000
        charged = self.identity['original_upper_yuan'] + sum(c.get('upper_estimate_yuan') if c.get('upper_estimate_yuan') is not None else c['reserved_yuan'] for c in self.calls)
        if charged + bound > 1.: raise RuntimeError('One yuan combined cap reached')
        return super().begin(provider,model,payload)


def request_summary(provider, model, kind, system, user):
    limit = 4096 if kind == 'd' else 2048
    with provider_task('display_summary'), execution_limits({'display_summary':limit}), thinking_task('auxiliary','off'):
        request = provider._request(system,user,True,False,temperature=0)
        # A controlled PaidRun overrides execution_limits; enforce this segment's cap.
        request.data = json.dumps({**json.loads(request.data),'max_tokens':limit}).encode()
        with paid_request('DeepSeek',model,json.loads(request.data)):
            return provider._complete_request(request,False)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',action='store_true',help='Pay only for sections still failing after replay')
    args=parser.parse_args()
    directory=DATA/'display_summaries';path=directory/f'{EXPERIMENT}.json'
    sections=load_sections(DATA/'demo.db',EXPERIMENT)
    data=revalidate_saved(sections,path)
    failed=[r for r in data['records'] if r['status'] != '通过']
    print(json.dumps({'phase':'free_revalidation','records':len(data['records']),
                      'replayed':sum(len(r['attempts']) for r in data['revalidation_audit']),
                      'remaining':[(r['round'],r['type'],r['candidate']) for r in failed]},ensure_ascii=False),flush=True)
    if not args.generate or not failed: return
    settings=load_settings()
    if settings.model != 'deepseek-flash' or not settings.configured: raise RuntimeError('Expected configured DeepSeek flash')
    original_path=directory/f'{EXPERIMENT}.ledger.json'
    original=json.loads(original_path.read_text())
    if original['cost_unknown']: raise RuntimeError('Original billing unknown; cannot bound combined cost')
    identity={'experiment_id':EXPERIMENT,'source_sha256':source_hash(canonical(sections)),
              'original_ledger_sha256':source_hash(original_path.read_text()),
              'original_upper_yuan':sum(c['upper_estimate_yuan'] for c in original['calls'])}
    ledger=directory/f'{EXPERIMENT}.033a2.ledger.json'
    if ledger.exists():
        budget=RedoBudget.load_accounting(ledger,lambda:identity)
        if budget.identity != identity: raise RuntimeError('Source or original accounting changed')
    else:
        budget=RedoBudget(ledger,1.,{settings.model:REDO_PRICES},identity,
                          identity_check=lambda:identity,output_limits={'display_summary':4096})
    save(directory/f'{PROMPT_VERSION}.prompt.json',{'system':SYSTEM,'examples':EXAMPLES,'parameter_names':PARAMETER_NAMES})
    provider=DeepSeekProvider(settings)
    def call(system,user):
        kind='d' if set(json.loads(user)['exact_keys']) == {'merged','predicted','actual','decision'} else 'other'
        result=request_summary(provider,settings.model,kind,system,user)
        print(json.dumps({'call':len(budget.calls),'usage':result.get('usage',{}),'yuan':usage_cost(result.get('usage',{}))},ensure_ascii=False),flush=True)
        return result
    with controlled_run(budget):data=redo_failed(sections,path,call,model=settings.model)
    print(json.dumps({'passed':sum(r['status']=='通过' for r in data['records']),
                      'calls':len(budget.calls),'combined_upper_yuan':identity['original_upper_yuan']+budget.spent},ensure_ascii=False),flush=True)


if __name__ == '__main__': run()
