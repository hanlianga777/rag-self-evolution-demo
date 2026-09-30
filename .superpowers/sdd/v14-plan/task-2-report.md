# Task 2 — Golden V2 planner, validator, pool integration

## Implementation

- `backend/app/golden_v2.py` is the shared deterministic implementation. Reuses installed sklearn `KMeans`, current persisted FAISS vectors, L2 normalization, squared Euclidean distance, `random_state=42`, `n_init=10`, `max_iter=100`. No requirements changes or embedding regeneration. Estimated K is `max(2,min(n//40,isqrt(n)+1))` clamped to `[1,n]`; zero corpus explicitly rejects. Empty K-means labels disappear; small clusters merge in fixed label order into nearest valid centroid (or nearest remaining centroid when all small), recomputing the centroid each merge. Final ordering follows smallest stable chunk ID.
- Topic capacities first use largest remainder over the **whole profile**. Positive/Ablation/Negative then receive largest-remainder allocations within remaining topic capacities. This avoids concentrating all three groups on identical tie winners: equal 20 topics / Mini20 receives 20 Anchor topics, while only12 topics receive answerable evidence. Gaps separately disclose no Anchor slots and no answerable evidence slots.
- Actual explicit key/value materials are prioritized Aggregation → shared-entity Bridge → Fact → Ordinary. A centralized overall specialty cap Mini2/Medium4/Full8 is additionally bounded by half answerable slots. Unknown structure is Ordinary and audited; no model labels or fabricated evidence. Historical usage counts, actual reuse, topic centers, source IDs, quotas, merge audit, and fallback are frozen. Unused material is preferred within topic before reused material.
- Unified `validate_golden_candidate(candidate, corpus, coverage_plan=None, validation_context=None)` is called by AI generation, Import Preview/Confirm, Pool Preview/Create, revision draft/apply validation and direct question edits. Evidence is normalized per individual entry; document/page/product/version restrictions and normalized original-text positions are retained. Explicit question metadata entities are checked against selected evidence scope. Fact connective paraphrases can pass while unsupported added claims fail. Unknown Bridge relationship requires review; two chunks alone never establish Bridge. Aggregation validates each scope item and completeness.
- Negative nearest-center assignment uses the existing local embedding model with `local_files_only=True`; it never creates Golden Evidence. Failure to load local embeddings yields a visible warning and unmatched pool slots, rather than guessed topic assignment. Large distance warns of low confidence. Ordinary slots have no special structural requirement and can accept independently validated special candidates; specialty slots enforce the matching type and declared Aggregation/Bridge scope.
- Pool selection is evaluated against an independent, persisted current plan. Sorted augmenting-path matching produces a stable maximum assignment regardless of selection order. Creation checks all profile counts, candidate validity, and every slot, and rechecks question contents under the write transaction. It creates fresh candidate IDs with pending Probe/QC/Human Review and keeps originals unchanged.
- JSON storage is reused, with only additive `coverage_plan_previews(id,plan_json,created_at)` and idempotent migration marker `golden-v2-preview-v1`. Existing legacy question discriminator is retained for quality/revision compatibility; `raw.planner_version` and frozen plan identify V2. Existing nullable construction fields remain null in the Legacy adapter, never guessed from question text or rewritten in frozen snapshots.

## Exact API contract for the UI task

All POSTs use the existing trusted Origin dependency.

### POST `/api/governance/coverage-preview`

Request: `{"profile":"mini"}` (`mini|medium|full`; default mini). No Provider/Judge/QC. Response200 is the Plan object:

- `plan_id`, `planner_version` (`golden-planner-v2.1`), `status:"preview"`, `created_at`
- `profile:{name,positive_count,ablation_count,negative_count,expected_count}`
- `corpus_fingerprint`, `chunk_fingerprint`, `embedding_identity`, `embedding_fingerprint`
- `parameters:{target_cluster_size,min_cluster_size,seed,n_init,max_iter,distance}`, `seed`, `initial_k`, `final_k`, `merge_mapping:[{from,to,size}]`
- `clusters:[{cluster_id,size,center,chunk_ids,representative_chunk_ids,label,products,anchor_quota,quotas:{positive,ablation,negative}}]`
- `slots:[{slot,slot_id,test_category,evaluation_group,construction_type,structured_type,topic_cluster,related_clusters,material_chunk_ids,evidence_chunk_ids,coverage_anchor_chunk_ids,document_id,product,section_path,ablation_attribute,source_positive_slot,requirements:{product,bridge,aggregation_items},sampling_priority,reused,status:"planned",attempts:0,selected_reason,negative_subtype?,expected_behavior?}]`
- `chunk_clusters:{chunk_id:cluster_id}`, `usage_counts:{chunk_id:historical_count}`, `reuse_statistics:{reused_slots,unique_chunks}`
- `construction_audit:{special_limit,planned:{type:count},fallback}`
- `coverage:{anchor_topics:[cluster_id],evidence_topics:[cluster_id]}`
- `gaps:[{topic_cluster,reason:"no_anchor_slots"|"no_answerable_evidence_slots",size}]`

Error422 `detail` is a readable string. Identical inputs including historical usage return the stored same preview and timestamp. A newly created preview does not invalidate prior approved objects.

### POST `/api/governance/generation-runs/from-pool/preview`

Request: `{"profile":"mini","question_ids":["BUS-..."],"plan_id":"PLAN-..."}`. `plan_id` optional: server first builds the current plan using all corpus material, independently of selected questions. Response200, including unsuccessful matching:

```
{
  "valid": false,
  "plan_id": "PLAN-...",
  "matching": {"Q01":"BUS-..."},
  "gaps": [{"slot_id":"Q02","topic_cluster":"T002","evaluation_group":"positive","construction_type":"Ordinary","available_candidates":0,"deficit":1}],
  "counts": {"positive":8,"ablation":4,"negative":8},
  "quota_valid": true,
  "validations": {"BUS-...": "Validation object below"},
  "unmatched_question_ids": ["BUS-..."],
  "coverage_plan": "full Plan object above"
}
```

Counts only contain observed groups; the frontend should default absent counts to zero. No selected candidates are cloned by preview. Invalid/missing/stale plan produces422 with readable `detail`.

### POST `/api/governance/generation-runs/from-pool`

Same request. Success201 returns the existing GenerationRun shape, including new candidate `question_ids`, `profile`, `artifacts.coverage_plan` (slot array), `artifacts.question_plan`, and `artifacts.hard_validation.frozen_plan` (full immutable Plan). Also `hard_validation.pool_matching`, `source_question_ids`, and original `corpus_fingerprint`. Run status `completed` means selection assembly finished; `progress.stage:"quality_not_run"`, all candidate Probe/QC/Review states are pending. UI must not equate this status with approved Golden.

Mismatch422: `detail` is a JSON object with `message:"候选池未满足当前 Coverage Plan"` plus the full matching preview fields above; missing plan/candidate or unavailable index may have a string detail.

### Existing generation/import/revision endpoints

- `/api/governance/generate`: `{"profile":"mini","plan_id":"PLAN-..."}`; optional plan ID always resolved server-side, current vectors checked, plan frozen before worker dispatch. Response202 remains `{run_id,status:"queued",profile}`. `/generate-mini` follows the same current-plan route.
- `/api/governance/imports?filename=cases.csv&confirm=false|true`: existing bytes payload and existing columns remain supported. Each `rows[]` now adds `validation`; `valid_rows[]` contains the normalized candidate and compact validation audit. Current mini preview supplies automatic topic attribution during import; final chosen profile plan is independently validated at pool assembly. A valid import is a candidate, not approval or a proof that it fills a final plan slot.
- Run `artifacts.hard_validation.frozen_plan` is authoritative. `artifacts.coverage_plan` remains the compatibility slot array; actual attempts/errors are in `artifacts.slot_audit`, failures in `artifacts.failed_slots`, progress in `operation_progress`. Immutable plan slot status remains `planned`; never animate that frozen field as fake live progress.
- Question responses additionally expose `construction_type` (nullable), `construction_provenance:"persisted"|"legacy_structured_type"|"not_collected"`, `planner_version` (nullable). Newly cloned/generated raw records include `plan_id`, `planner_version`, `evaluation_group`, construction/coverage metadata, original provenance. Legacy null means 未采集.
- Key question edits invalidate prior Probe/QC/Review and append audit. V2 revision validation retains the original frozen slot. If a revised Negative cannot be embedded locally, it cannot silently pass frozen coverage.

### Validation object

```
{
 "valid": true,
 "blocking_errors": [],
 "warnings": [],
 "normalized_candidate": {"...candidate fields":"...", "evaluation_group":"positive", "construction_type":"Fact", "source_chunk_ids":["C1"], "evidence_locations":[], "coverage_match":{}},
 "evidence_locations": [{"chunk_id":"C1","document_id":"D","page_start":1,"page_end":null,"char_start":0,"char_end":12,"quote":"...","normalization":"NFKC_alphanumeric_lowercase_v1"}],
 "construction_checks": {"type":"Fact","status":"passed","nodes":["C1"]},
 "coverage_match": {"status":"matched","related_clusters":["T001"],"eligible_slot_ids":["Q01"],"anchor":null},
 "validator_version":"golden-validator-v2.1"
}
```

Construction may add `items:[{item,supported,included}]` or `relations`, `necessary`; failures add `reason` and `status:"failed"|"needs_review"`. Without a plan coverage status is `not_requested`; otherwise `matched|gap`. Negative anchor is `{topic_cluster,method:"local_embedding_nearest_center",distance,is_evidence:false}`. Warnings never claim semantic proof; no match blocks pool creation even if the standalone candidate is structurally valid.

## Verification

Command: `python3 scripts/test_v14_offline.py` (root-owned outbound-TCP-blocking/disposable-DB runner; not included in this commit). Final exact rerun: **257 tests passed in 32.658s**, log `/tmp/gv2-commit-tests.log`. `python3 -m py_compile` touched Python modules and `git diff --check` passed.

Added `backend/tests/test_v14_golden_v2.py` exercises GV01..12 and VP01..06,15..17/DS01..03 through real functions and isolated stores: boundaries, stable merge/repeat, every profile,20topic anchor-vs-evidence accounting, usage prioritization, honest structure fallback and quota, concentrated-pool rejection, augmenting displacement, new clones/reset approval, negative-only anchor, multicluster evidence, stale corpus, full frozen AI generation19/20 and two attempts, user refill retaining19 IDs, edit invalidation, key-fact paraphrase vs fabricated claims, wrong corpus/page/entity, spurious Bridge, incomplete aggregation, colloquial Ablation, two-document evidence normalization idempotence, migration reruns, unchanged legacy snapshots/Production, API payload/gap contract with Provider forbidden. Existing partial-generation/revision/QC tests continue to exercise established finite budgets. Existing Phase1 pool tests now pass explicit fixture vectors/local question embeddings, avoiding accidental real FAISS usage.

## Limits and preserved boundaries

- No real Provider, real Golden generation, real approvals/releases, index rebuilds, dependency installation, production mutation, or push performed. Integration tests are synthetic fixtures/Stub, not real model readiness evidence.
- This deterministic validator does not prove arbitrary natural-language semantics. Explicit key/value and relation checks have a deliberate conservative boundary; unsupported or ambiguous specialized claims require revision/review. Probe/QC semantic checks remain subsequent stages (Task3).
- Existing bounded generation semantics remain: two attempts per slot per generation pass; explicit regenerate-failed preserves passing slots and existing maximum three improving refill rounds. No automatic user-independent regeneration was added; QC budgets remain separate.
- Low-level legacy persistence helpers retain compatibility for legacy fixture/historical workflows; all public generation and pool routes create/resolve a V2 plan before creating a new current run. Historical frozen JSON is not backfilled with invented plans.
- Corpus/index identity is checked when accepting a preview and corpus chunk identity before asynchronous generation/refill. Raw full-text and broader corpus activation atomicity are Task4.
