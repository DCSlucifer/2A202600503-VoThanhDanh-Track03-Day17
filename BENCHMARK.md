# BENCHMARK - Lab 17 Multi-Memory Agent

This file is the submission-facing benchmark and reflection artifact for Lab 17.
The executable source of truth is `benchmark/scenarios/*.yaml`; each scenario is
multi-turn and is replayed twice: `with-memory` and `no-memory`.

## How To Run

Deterministic benchmark:

```powershell
.\.venv\Scripts\python -m scripts.run_benchmark
```

Real OpenAI benchmark:

```powershell
$env:AGENT_RUNTIME__MODE="openai"
$env:AGENT_EMBEDDING__MODE="openai"
$env:AGENT_USE_FAKE_REDIS="false"
$env:AGENT_USE_EPHEMERAL_CHROMA="true"
$env:REDIS_URL="redis://localhost:6379/0"
.\.venv\Scripts\python -m scripts.run_benchmark
```

Each run writes:

- `outputs/reports/<run_id>/report.md`
- `outputs/reports/<run_id>/metrics_table.csv`
- `outputs/reports/<run_id>/memory_hit_rate.md`
- `outputs/reports/<run_id>/token_budget.md`
- `outputs/reports/<run_id>/scenario_deep_dives/*.md`

## Scenario Matrix

| # | Scenario | Memory group | No-memory expectation | With-memory expectation |
|---:|---|---|---|---|
| 1 | Preference same-session | profile preference | May ask for preference again | Recalls preferred language in same session |
| 2 | Preference cross-session | Redis profile | New process/session forgets preference | Suggests Python and avoids Java |
| 3 | Preference contradiction | conflict update | Cannot know latest preference | Uses latest Rust preference, not old Python |
| 4 | Profile allergy correction | factual profile | Cannot answer allergy | Answers latest allergy: đậu nành, not sữa bò |
| 5 | Technical stack fact | factual profile | Cannot recall stack | Recalls Postgres 15 technical fact |
| 6 | Async/await confusion | episodic | Generic explanation | Adds simple, step-by-step explanation |
| 7 | Ambiguous multi-memory | router fan-out | Lacks relevant recalled context | Routes to multiple memory backends |
| 8 | Irrelevant precision | privacy/precision | No personal leak | Does not inject unrelated preference |
| 9 | Long conversation trim | context budget | Preference can be lost | Keeps pinned profile under token pressure |
| 10 | Cold start | robustness | Works without memory | Also works with empty memory |

## Metrics

The benchmark reports:

- Response relevance: expected signals present and negative signals absent.
- Context utilization: share of prompt tokens coming from recalled memory.
- Token efficiency: relevance per 1k prompt tokens.
- Memory hit rate: recalled memory contributes to expected answer signals.
- User satisfaction proxy: relevance plus preference-honoring and no false amnesia.

## Memory Coverage

- Short-term: in-process `ConversationBuffer`.
- Long-term profile: Redis preferences and facts.
- Episodic: JSONL log with notable event tags such as `confusion`.
- Semantic: Chroma vector index for distilled preferences, facts, and notable episodes.

## Privacy Reflection

The most sensitive memory is long-term profile memory because it can contain PII
or private user attributes such as name, allergy, role, company, project, and
technical stack. Episodic memory is also risky because it can capture user
confusion, errors, or work context.

The system should require consent before storing sensitive profile facts in a
production setting. Redis profile facts use TTL support for facts, and user-level
deletion is available through `RedisMemory.clear_user(user_id)`. Semantic memory
supports user deletion with `SemanticMemory.delete(user_id=...)`. Short-term
buffer memory is session-scoped and can be cleared per session. Episodic JSONL is
append-only in this lab, so production deletion would need a compaction or
redaction job; this is the clearest privacy limitation.

Retrieval mistakes are another privacy risk: if router precision is poor, the
agent can inject irrelevant personal details into unrelated answers. Scenario 8
tests this by asking an unrelated question after preferences exist.

## Technical Limitations

- Fact and preference extraction are regex-based, so recall is reliable for the
  benchmark cases but will miss many paraphrases.
- Chroma stores distilled facts and notable episodes, not raw turns; this lowers
  privacy risk but can reduce recall detail.
- Episodic memory currently scans JSONL files and does not scale to large logs.
- The user satisfaction score is a deterministic proxy, not a human judgement.
- The router is rule-based; a learned or LLM router would likely improve recall
  for ambiguous production traffic.
