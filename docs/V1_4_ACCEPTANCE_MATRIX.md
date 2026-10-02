# V1.4 离线验收映射

唯一规范为 [SPEC V1.4](RAG_SELF_EVOLUTION_SPEC.md)，本文件仅记录测试证据，不制定第二套规则。实施版本 `d14e953` / `2d3bdb2` / `5ef7f7b`；完整状态见 [实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)。测试使用隔离 SQLite/临时 Corpus/Stub；浏览器渲染实际隔离 API 响应。真实 Provider、Golden 与 Production 没有重跑，WebKit 缺失未验证。各阶段阻断问题已修复并经复审通过，最终整体审查中。

## 19 个页面需求检查点

| SPEC | Implementation/evidence |
|---|---|
|15.1|OverviewPage derived next-step, compact Stage and Golden/Baseline/Agent/Production summaries; source/current identity displayed. All four overview screenshots; app-navigation and identity tests. Business/technical architecture upload entries preserved, missing image honestly absent.|
|15.2|KnowledgePage document→parse/OCR→chunk→embedding→index; real metadata/status, document/Chunk Drawer and source fields; missing PDF URL does not create iframe. Shared centered deletion confirm, atomic existing update. All sizes knowledge + document-drawer keyboard/focus checks. No real add/delete performed.|
|15.3|SettingsPage two process strips and six stages; actual frozen config/search-space authority, Evaluation separated from runtime; fulltext supported/status/coverage distinct. Async fetch cancellation. All sizes settings; pipeline-contract tests.|
|15.4|GovernancePage six stages, current/pool only; history button→Drawer; result precedes audit. Counts from actual run. Four-size current/pool screenshots, fixed-workspaces test. Legacy no invented completedV2.|
|15.5|Dynamic N/K/slots/construction/counts + Coverage Drawer and gaps/audit. Question Drawer exposes answer/evidence/material/attempts and existing revision controls. Shared unsaved-edit discard confirmation; retrieved content visible. Four-size coverage/question Drawers, revision/workflow tests.|
|15.6|Snapshot history Drawer readonly with frozen provenance/Profile/Corpus/run/planner details. Browsing preserves current objects; no history tab. Four-size snapshot Drawers; legacy-storage/HTTP snapshot preservation assertions.|
|15.7|Pool source/group/construction unified Select filters; profile and coverage selection progress, concrete blocking reason; existing create-new-run. Import Drawer download/preview/error/confirm and source metadata preserved. Four-size import Drawer/Select keyboard+outside/Esc; import backend and governance-ui tests.|
|15.8|EvaluationPage stage/compact gate hero/failed gates first, identity and config next; Overall comparison-only; diagnostics secondary. All sizes baseline screenshots; ui-polish/report tests.|
|15.9|Gate table X/Y/Z, frozen actual thresholds/group/performance, shallow red failures, sticky internal scroll. No added frontend判定. Four-size Hard Gate + Gate Drawer; v13_gate_details backend tests.|
|15.10|BadCase compact rows/main failure metric/tags, keyboard rowEnter with preventDefault avoids closing newly opened Drawer. Drawer answer/expected/evidence/judge/config/timing and separate Candidate/Final observations. Four-size BadCase and Drawers; v14-ui VP07/09 null-vs-empty assertion.|
|15.11|EvolutionPage dynamic nonzero root causes, current Baseline source/failed gate reminder. Machine known diagnosis remains separate before Agent. Cases/evidence Drawer and readable report fields. Four-size diagnostic screenshots; current identity tests.|
|15.12|Round/budget/actual Agent output and three plan summaries; no old-success fallback for absent/failed experiment. Shared current identity key/remount, cancellation protection. Four-size Optimization Agent screenshots; ID08 stale report test.|
|15.13|Dynamic Search Space button→wide Drawer, current Baseline values/rule types/allowed values/dependencies; existing validator range untouched. Four-size searchspace-drawer focus/width assertions; optimization contract tests.|
|15.14|Equal ABC desktop cards, differences only, aligned report footer; report Drawer Why/Risk/TargetCases/config/gates/regression/cases. D separate full validation/decision and real failed-D winner retention. Four-size ABC/D + candidate Drawer; actual HTTP D rules.|
|15.15|Compact candidate execution/qualification states and evidence-backed recommendation; qualification-first bounded comparison, metric column sticky; Baseline regression N/A, unknown costs explicit reason. Four-size Sandbox screenshots; backend qualification/Regression tests.|
|15.16|VersionsPage compact Sandbox/Gate2/Gate3 and release state; actual Production changes only, collapsed unchanged fields. Reports Drawer and centered release/rollback confirm; refresh after success; failure remains visible with reason. Four-size release Drawer/rollback cancel; v14-ui RL03/05 failure modal test.|
|15.17|AssistantPage compact version/session header, persistent local sessions, suggestion click, inline seconds/stop/retry, separate evidence/timing/usage/cost. Runtime displays frozen answer version when collected. All sizes QA screenshots; inline-runtime and trust-ux tests. No global QA operation console.|
|15.18|ExperimentPage compact baseline-v-production identity; select immediately fills editable question; frozen per-request versions/question/comparisonID. Desktop50/50 equal-height body-scroll/metric-footer; mobile stack. Four-size immediate-question/footer checks and native1280 delayed-response rejection; frontend single-side failure and identity tests. No added Judge.|
|15.19|VerificationPage Monitoring tab ProductionSignals→HumanReview→Trigger→Agent. QA source Drawer, actual human assessment and explicit confirm/Agent actions; missing safety signal—. Four-size Monitoring+Drawer; full HTTP pendingContext/Round1/idempotency proof.|

Global: eight H1 labels match navigation, old hashes preserved; shared refresh on navigation/operation completion and bounded identity-coherence retry. Shared Drawer/Dialog/Select rather than native confirms. Detail Enter/click, focus enters/traps/returns, Escape, viewport width checked at every size. Existing internal scroll/sticky tables, text expansion and scroll locking reused. Browser checks are interaction assertions, not screenshot count alone.

## 54 个 Test ID 与具名断言

Paths below are relative to `backend/tests/`, except F=`frontend/src/v14-ui-contract.test.tsx`; B=`scripts/test_v14_browser.py`. Names are unittest methods, with filename supplying actual executable location. Shared method references are accompanied by distinct assertions rather than treating a filename as coverage.

| ID | Actual test name | Concrete assertion / limits |
|---|---|---|
|ID-01|test_v14_identity.py::test_current_identity_excludes_latest_sandbox_and_old_experiment|All current APIs resolve newerB1/noExperiment, oldE0 remains historical, Productionbaseline-v1 unchanged.|
|ID-02|same method|Newer completed Sandbox explicitly seeded; every resolver still chooses formalB1.|
|ID-03|test_v14_identity.py::test_confirm_is_transactional_idempotent_and_round_zero_starts_round_one; test_v14_api_lifecycle.py::test_complete_v2_http_lifecycle_d_regression_keeps_winner_monitoring_round_one|PendingRound0 empty context becomes Round1ABC with identical contextID via actualAgentHTTP.|
|ID-04|test_v14_identity.py::test_confirm_is_transactional_idempotent_and_round_zero_starts_round_one|Next generation raises 全部完成Sandbox while first candidates unevaluated.|
|ID-05|same identity method; HTTP lifecycle|Concurrent Confirm one context/one approval; repeatedHTTPConfirm sameID.|
|ID-06|test_v14_identity.py::test_failed_first_round_reuses_context_and_unknown_experiment_is_readable; test_provider_failure_and_stale_baseline_result_leave_no_candidates; test_storage_failure_rolls_back_entire_candidate_batch|Malformed/2candidate/provider/stale/storage failures leave no halfABC; retry samecontext.|
|ID-07|test_v14_identity.py::test_invalid_corpus_keeps_trigger_pending_and_blocks_release_guards; test_new_golden_invalidates_old_baseline|Corpus/newGolden invalidatesB; reason explicit; Trigger pending/unlinked, guard fails.|
|ID-08|F::ID-08 ignores an old same-question comparison after Baseline changes; ID-08 clears Candidate Drawer and rejects an old candidate report after identity changes; ID-08 refuses incoherent parallel app identities after one bounded retry; B::1280-native-stale-comparison|Late response cannot populate changedidentity/question; oldDrawer cleared; incoherence boundedretry rejects. Native old response discarded.|
|GV-01|test_v14_golden_v2.py::test_gv01_04_boundaries_repeatability_profiles_and_merge|n0 rejects, n1/2/3/5 legalK and conservedchunks/slots.|
|GV-02|same method|Repeated plan exact equality for same corpus/seed/config.|
|GV-03|same method|Stable merges across small/all-small clusters and totalchunk count conserved.|
|GV-04|same method|Exact Mini20/Medium49/Full98 and group quotas8/4/8,20/9/20,40/18/40.|
|GV-05|test_v14_golden_v2.py::test_gv05_07_gaps_unused_material_and_honest_fallback; test_equal_twenty_topics_use_all_anchor_capacity_and_separate_evidence|Single allocatedtopic records3gaps;20topics records12anchor8evidence-gap rather than fake coverage.|
|GV-06|test_v14_golden_v2.py::test_gv05_07_gaps_unused_material_and_honest_fallback|UsedC000 excluded whenunusedavailable; onechunk reuse count19 tracked.|
|GV-07|same method; test_specialty_priority_budget_and_bridge_nodes|No unsupportedspecialty; Ordinary fallback; supported Bridge/materialbudget only.|
|GV-08|test_v14_golden_v2.py::test_gv08_12_pool_topic_gaps_and_stale_plan|Correct20quota buttopic concentration previewinvalid/gaps; create blocked.|
|GV-09|test_v14_golden_v2.py::test_gv09_10_11_maximum_matching_and_new_unapproved_versions|NewRun preserves frozenPlan/matching; copiedquestions pendingreview, originalsunchanged.|
|GV-10|same method|Negative evidence_locations[] and coverageanchor.is_evidence false.|
|GV-11|same method; test_vp01_06_shared_validation_locations_paraphrase_construction|Reverse selection same matching, augmentingmatch success; Bridge bothrelatedclusters retained.|
|GV-12|test_v14_golden_v2.py::test_gv08_12_pool_topic_gaps_and_stale_plan; test_v14_probe_cost.py::test_planner_rejects_same_count_old_chunks_after_pointer_switch|Changedcontent/countsamepointer invalidates oldplan/chunks.|
|VP-01|test_v14_golden_v2.py::test_vp01_06_shared_validation_locations_paraphrase_construction|Sharedvalidator matches AI_errors; importedrow samevalidatorversion. Pool clone validatedsameboundary.|
|VP-02|same method|24V paraphrase passes with realcharlocation0; unsupportedextrafact fails.|
|VP-03|same method|OTHERchunk/page9/missingquotedfact blocked.|
|VP-04|same method; test_review_bridge_proof_uses_necessary_connected_answer_nodes|Twochunk declaration with singlefact notBridge; necessaryconnectednodes required.|
|VP-05|test_v14_golden_v2.py::test_vp01_06_shared_validation_locations_paraphrase_construction; test_review2_similarity_never_overrides_entity_fact_negation_or_group_scope|Missingaggregationitem andwrongentity/fact/scope rejected.|
|VP-06|test_v14_golden_v2.py::test_vp01_06_shared_validation_locations_paraphrase_construction|Standalone colloquialablation passes withoutquestion-number pairing.|
|VP-07|test_v14_probe_cost.py::test_vp07_09_actual_single_pipeline_capped_candidates_and_multihop_all_hit|CandidateA/B retained, finalA only; cap respected/rankingbasis. F separateAny/Allrenders.|
|VP-08|test_v14_probe_cost.py::test_vp08_probe_valid_evidence_retained_and_missing_legacy_candidate_unknown|Nonrecall validEvidence remainsP1/review, not illegal; missinglegacycandidatesnull unknown.|
|VP-09|test_v14_probe_cost.py::test_vp07_09_actual_single_pipeline_capped_candidates_and_multihop_all_hit|Anytrue/Allfalse/coverage.5; F CandidatevsFinal labeledseparately.|
|VP-10|test_v14_probe_cost.py::test_vp10_evaluation_stores_generation_evidence_and_separates_candidate_misses|Sufficientfinal/badJudge=>Generation evidence; candidatemiss=>Retrieval; legacyunknown.|
|VP-11|test_v14_probe_cost.py::test_vp11_14_raw_nonchunk_table_detected_related_only_and_judge_errors_uncertain|Raw48Vtable notinChunks hits; answerableStubJudge blocksfakeNegative.|
|VP-12|same method|Relatedrawmatch + answerablefalse remains passedvalidnegative.|
|VP-13|test_candidate_review_export.py::test_negative_subtypes_keep_topic_hits_as_signals_and_clarify_can_be_partial; test_negative_subtype_semantics_use_one_judge_only_when_local_signal_is_unclear|safe_rejection/safetycritical/injection with topicalC1 remain valid perexpectedbehavior; semanticmismatch rejected.|
|VP-14|test_v14_probe_cost.py::test_vp11_14_raw_nonchunk_table_detected_related_only_and_judge_errors_uncertain; test_r1_model_load_and_encoder_failure_persist_failed_probe_and_block_quality_api|Timeout/malformed/insufficientrawcannotPass; retrievalexecution failure persisted, QC409 cannotwaive.|
|VP-15|test_v14_golden_v2.py::test_vp15_17_frozen_generation_keeps_19_slots_and_bounded_refill; test_governance.py::test_changing_approved_question_evidence_or_answer_invalidates_approval|Editedquestion/answer/evidence resetsProbe/QC/review and historyaudit.|
|VP-16|test_v14_golden_v2.py::test_vp15_17_frozen_generation_keeps_19_slots_and_bounded_refill|19valid retained/failedslot audit; freezingincomplete raises.|
|VP-17|same method; test_revision_workflow.py::test_ai_stops_after_one_unsuccessful_targeted_fix; test_qc_timeout_retries_once_then_resumes_without_reapplying_or_reprobing|OnlyfailedQ01 refilled; singleAIrepair, boundedQCretry separate from generation.|
|DS-01|test_v14_golden_v2.py::test_ds01_03_migration_legacy_adapter_and_preview_no_mutation; test_generation_storage_legacy.py::test_generated_groups_use_named_columns_with_qc_at_end; test_snapshot_column_repairs_even_when_migration_marker_exists|Repeatedmigration, namedcolumns, partialschema repair preserve fields/semantics.|
|DS-02|test_phase1_closure.py::test_existing_column_order_import_and_clone_keep_fields_and_gate|Negative nullableanswer/EvidenceJSON surviveimport/clone/namedcolumns.|
|DS-03|test_v14_golden_v2.py::test_ds01_03_migration_legacy_adapter_and_preview_no_mutation; HTTP lifecycle|Legacy adapter no rewrite; storedfrozenSnapshot/Baseline unchanged aftertestpublish/Monitoring.|
|DS-04|test_v14_probe_cost.py::test_ds04_atomic_activation_and_failed_post_switch_restore_complete_bundle; test_supplement_audit_failure_rolls_back_and_preserves_previous_bundle|Failure before/after activation restoresoldpointer and completeoldbundle.|
|DS-05|test_v14_probe_cost.py::test_ds05_refuse_mixed_fulltext_fingerprint_and_checksum|Mixedsource/checksum sidecar rejected.|
|DS-06|test_v14_probe_cost.py::test_ds06_07_supplement_exact_unchanged_artifacts_and_refuse_parser_difference; test_ds06_supplement_accepts_reordered_ids_but_rejects_duplicate_missing_and_content_changes|Compatible sidecar schemaaudit; reverse traversal accepted; originaldocuments/chunks/faiss bytes unchanged.|
|DS-07|same two methods|Contentdiff, duplicateIDs, missingchunk/NoneID rejected; activepointer preserved. Real PDF reparse not executed.|
|CT-01|test_v14_probe_cost.py::test_ct01_04_official_alias_cache_math_zero_and_missing_reasons|Cachehit/miss/output exactofficialalias/unit/currency arithmetic, no doublebilling.|
|CT-02|same method; test_phase1_closure.py::test_telemetry_prices_require_complete_usage_and_preserve_official_basis|Missingcacheusage unavailable/null, no invented0cost.|
|CT-03|test_v14_probe_cost.py::test_ct03_peak_ambiguity_weekend_and_verified_holiday_calendar; test_ct03_reject_invalid_prices_and_keep_fixed_legacy_configuration; test_ct01_04_official_alias_cache_math_zero_and_missing_reasons|Unknownmodel/price/usage reasons; invalidpriceblocked; ambiguousperiodunavailable, verifiedcalendar only.|
|CT-04|test_v14_probe_cost.py::test_ct01_04_official_alias_cache_math_zero_and_missing_reasons; F::CT-04 displays collected zero cost and unknown cost reason separately|Collected0 vsnull distinct; previousversion estimate immutable; UIreasonreadable.|
|CT-05|test_v14_probe_cost.py::test_ct05_provider_nonstream_unknown_stream_first_content_and_nested_timing|NonstreamTTFTnull, streamfirstcontent measured; nestedspansnotadded; UIparent labeling.|
|RL-01|test_final_policy.py::test_candidate_qualification_requires_all_release_conditions; test_final_governance.py::test_multiple_pareto_candidates_require_human_recommendation|HTTP lifecycle sets an explicitly synthetic100 Overall on B while retaining genuine failed Baseline Gates; actualqualify_candidate derives failedqualification. Score is asserted higher than allactualABC scores; realrecommendation pareto excludesB, Gate2 HTTP409 and publishHTTP409, versionlist unchanged. OriginalB result restored before normalGate2; no forgedeligibilityboolean.|
|RL-02|test_v11_e2e.py::test_v12_d_new_failure_falls_back_to_winner; HTTP lifecycle|ActualD fullrunner unqualified/regressionfail, persistedrecommendation keepsqualifiedA.|
|RL-03|test_api.py::test_publish_blocks_an_incomplete_a_b_c_round_without_old_approval_routes; test_v12_tuning.py::test_report_cannot_confirm_while_a_candidate_is_running; test_final_policy.py::test_regression_allows_no_new_critical_and_at_most_one_ordinary; F::RL-03/05 uses centered confirmation and keeps failed release visible without fake success|HTTP lifecycle independently calls publish for actualunrunA, fullyevaluatedqualifiedA beforeGate2, and genuinelyengine-evaluatedD with11/11GatePASS butRegressionFAIL. EachHTTP409 withidenticalentireversionlist; actualRegressionrule and UI409dialog remain covered. Transactioneligibility mutation separately provenRL05.|
|RL-04|test_v14_golden_v2.py::test_ds01_03_migration_legacy_adapter_and_preview_no_mutation; HTTP lifecycle|Preview no DBmutation; initialProduction unchangeduntiltestGate3; storedBaseline/Snapshot remain equal. Realdata safety proof ownedbyroot, not inferredfromfixtures.|
|RL-05|HTTP lifecycle; F::RL-03/05 uses centered confirmation and keeps failed release visible without fake success|Eligibility changesinsidepublishtransaction→HTTP409, noversioninsert, rollbackrestoresqualification. UI409 retainsdialog/reason and doesnotfakepublished.|


## UI 整合复审修复断言（5ef7f7b，四项复审通过）

| 发现 | 具名前端测试 / 浏览器补验 |
| --- | --- |
| Gate 与发布资格混用 | `review R1 separates Gate PASS from unqualified Regression FAIL in Sandbox and D report`；四尺寸 D 报告/Sandbox |
| 旧 Production / 非完成 Baseline 流程误导 | 参数化 `review R2 keeps %s Baseline at Evaluation before Agent`（missing/running/failed）；`review R2 an older Production does not finish a new recommendation Gate3` |
| Golden 类型风险汇总/筛选缺失 | `review R3 persisted Golden risks count and filter exact rows without changing approval`；1280/390 八类精确筛选，补充边界数据明确为合成夹具 |
| Monitoring 借用旧 A/B/C 进度 | `review R4 pending Trigger ignores prior ABC and explicitly starts its same Round0 context`；`review R4 selected historical Monitoring context is identified and cannot start under a new Baseline`；四尺寸 Pending Trigger 不借旧 A/B/C |

前端 `frontend/src/v14-ui-contract.test.tsx`，最终 105 项前端测试和构建通过；Chromium 187 检查/147 截图。新测试是离线边界断言，不代表真实 QC、Provider 或 Trigger 实测。
