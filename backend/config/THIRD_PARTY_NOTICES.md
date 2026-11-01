# DeepSeek V4 tokenizer data

`deepseek_v4_tokenizer.zip` is the official tokenizer archive linked from the DeepSeek API token usage documentation:

- Documentation: https://api-docs.deepseek.com/quick_start/token_usage/
- Archive: https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip
- Retrieved for this Round 0 implementation on 2026-10-28.
- SHA-256: `e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495`.
- Attribution: DeepSeek. The archive contains no standalone license file; no independent license grant is asserted here.

Runtime loads only `deepseek_v4_tokenizer/tokenizer.json` through the installed Hugging Face `tokenizers` library. The Python helper distributed in the archive is never executed. No remote code, download, BGE tokenizer substitution, or inferred model window is used. Missing dependency, missing archive, or checksum failure explicitly blocks the enabled budget. OFF never loads this artifact.

`tokens_before` and `tokens_after` count the exact rendered retrieval context, including its source legend and headers, with `add_special_tokens=False`; these are local context counts, separate from actual Provider input/output/reasoning usage and the complete chat template. Every excluded source block prevents generation because required or safety evidence cannot be proven unnecessary offline.

Legal limits 8192 / 16384 / 32768 / 65536 are opt-in retrieval-context capacities. The current Corpus uses Parent 1400 / Child 400 / Overlap 80 under its existing BGE chunk tokenizer (unchanged); these units are not DeepSeek token counts. With TopK 4 or 6 the tiers permit bounded experiments from smaller context selection through generous complete-parent capacity. The official API model window must be checked separately; the archived tokenizer_config template's `model_max_length` is not used as an API context contract. Context limits remain OFF by default.

Read-only measurement against `CORPUS-38c90d5628b68c76d53e` on 2026-10-28 (349 complete Parents, this exact bundled tokenizer): body token P50 55, P95 267, maximum 839; sum of the largest four bodies 2708, largest six 3799. Source legends/headers add overhead counted at runtime. Thus even the lowest 8192 tier is generous for this current corpus and TopK, while larger tiers reserve room for future legal complete-source contexts. This is measured capacity justification, not a quality improvement result.
