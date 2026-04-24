# Báo cáo cá nhân - Lab 17: Multi-Memory Agent với LangGraph

**Sinh viên:** Võ Thành Danh  
**Repo:** `2A202600503-VoThanhDanh-Track03-Day17`  
**Mục tiêu:** xây dựng một agent có 4 loại memory, routing theo intent, quản lý context window, benchmark `with-memory` vs `no-memory`, và báo cáo privacy/limitations.

## Kết luận điểm

Theo rubric Lab 17, bài hiện tại đã đủ evidence để đạt **100/100 core points**. Phần bonus cũng có đủ 5 nhóm evidence: Redis thật, Chroma thật, LLM-based extraction có parse/error handling, token counting bằng `tiktoken`, và graph/UI demo rõ ràng.

Verification mới nhất:

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

Kết quả: **52 passed**.

Benchmark deterministic mới nhất:

```text
outputs/reports/run_20260424_121031_fb4011/report.md
```

Kết quả chính: **with-memory wins >= 3/5 metrics on 7/10 scenarios**.

## Rubric mapping

| Hạng mục | Điểm | Evidence |
|---|---:|---|
| 1. Full memory stack | 25/25 | 4 backend riêng: `BufferMemory`, `RedisMemory`, `EpisodicMemory`, `SemanticMemory`. |
| 2. LangGraph state/router + prompt injection | 30/30 | `AgentState`, `StateGraph`, nodes `ingest -> route_memory -> recall -> plan_context -> llm -> persist -> log_turn`; prompt có L0/L1/L2/L3. |
| 3. Save/update memory + conflict handling | 15/15 | Preference/fact extraction, Redis update, allergy correction, episodic write, semantic mirror. |
| 4. Benchmark 10 multi-turn conversations | 20/20 | 10 YAML scenarios, `with-memory` vs `no-memory`, report markdown/csv/token/memory-hit/deep-dives. |
| 5. Reflection privacy/limitations | 10/10 | `BENCHMARK.md` có PII/privacy, deletion, TTL, consent, retrieval risk, limitations. |

## Những gì đã làm được

### 1. Full memory stack

Tôi đã implement đủ 4 memory backend với interface tách biệt:

- Short-term memory: `src/agent/memory/buffer.py`
- Long-term profile memory: `src/agent/memory/redis_store.py`
- Episodic memory: `src/agent/memory/episodic.py`
- Semantic memory: `src/agent/memory/semantic.py`
- Protocol chung: `src/agent/memory/base.py`

Long-term Redis lưu cả preference và profile facts. Semantic memory dùng Chroma để lưu distilled preference/fact/episode chunks. Episodic memory dùng JSONL append log để recall kinh nghiệm như user từng bị confused với `async/await`.

### 2. LangGraph workflow

Graph chính nằm ở `src/agent/graph/build.py`, dùng LangGraph `StateGraph` và state ở `src/agent/graph/state.py`.

Luồng graph:

```text
ingest -> route_memory -> recall -> plan_context -> llm -> persist -> log_turn
```

Khi `memory_enabled=False`, graph bỏ qua router/recall/persist để benchmark công bằng với no-memory. Khi `memory_enabled=True`, router chọn backend theo intent rồi context manager inject memory vào prompt.

Evidence:

- Router: `src/agent/services/router.py`
- Recall node: `src/agent/graph/nodes/recall.py`
- Context manager: `src/agent/services/context_manager.py`
- Prompt rendering: `src/agent/schemas/context.py`

### 3. Memory router

Router phân biệt các nhóm intent:

- `preference_capture`
- `preference_recall`
- `fact_capture`
- `factual_recall`
- `experience_recall`
- `task_default`

Điểm quan trọng là tôi tách `fact_capture` khỏi `factual_recall`. Nếu user nói "Tôi dị ứng đậu nành chứ không phải sữa bò", agent không inject fact cũ "sữa bò" trước khi ghi correction mới. Nếu user hỏi "Tôi dị ứng gì?", router mới đọc `redis_fact`.

Test evidence:

- `tests/unit/test_router.py::test_allergy_question_selects_redis_fact`
- `tests/unit/test_router.py::test_allergy_statement_is_fact_capture_without_redis_read`

### 4. Save/update memory và conflict handling

Preference extractor xử lý các câu như:

```text
Tôi thích Python, không thích Java.
Actually I prefer Rust now.
```

Fact extractor xử lý profile facts như:

```text
Tôi dị ứng sữa bò.
À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.
I'm using Postgres 15 for this project.
```

Evidence code:

- Rule extraction: `src/agent/memory/writers.py`
- Conflict resolver: `src/agent/memory/conflict.py`
- Persist node: `src/agent/graph/nodes/persist.py`
- Redis update/history: `src/agent/memory/redis_store.py`

Test evidence:

- `tests/unit/test_writers.py::test_fact_extract_vn_allergy`
- `tests/unit/test_writers.py::test_fact_extract_vn_allergy_correction`
- `tests/unit/test_writers.py::test_fact_extract_technical_stack`
- `tests/unit/test_conflict.py`

Benchmark evidence:

- `outputs/reports/run_20260424_121031_fb4011/scenario_deep_dives/s04_fact_profile.md`

Kết quả scenario allergy correction:

```text
with-memory response_relevance = 1.000
no-memory response_relevance   = 0.667
delta                          = +0.333
```

### 5. Context window management

Context manager chia prompt thành 4 level:

- L0: system prompt, current request, pinned profile
- L1: recent dialogue
- L2: recalled memory
- L3: ambient/older context

Khi gần quá budget, hệ thống drop/trim theo thứ tự L3 -> L2 -> summarize L1 -> compress L2, và không shrink L0.

Evidence:

- `src/agent/services/context_manager.py`
- `tests/unit/test_context_manager.py`
- `outputs/reports/run_20260424_121031_fb4011/token_budget.md`

### 6. Benchmark 10 multi-turn conversations

Benchmark source:

- `benchmark/scenarios/01_preference_same_session.yaml`
- `benchmark/scenarios/02_preference_cross_session.yaml`
- `benchmark/scenarios/03_preference_contradiction.yaml`
- `benchmark/scenarios/04_factual_profile.yaml`
- `benchmark/scenarios/05_factual_technical.yaml`
- `benchmark/scenarios/06_episodic_adaptation.yaml`
- `benchmark/scenarios/07_ambiguous_multi_memory.yaml`
- `benchmark/scenarios/08_precision_irrelevant.yaml`
- `benchmark/scenarios/09_long_conversation_trim.yaml`
- `benchmark/scenarios/10_cold_start.yaml`

Report artifacts:

- `outputs/reports/run_20260424_121031_fb4011/report.md`
- `outputs/reports/run_20260424_121031_fb4011/metrics_table.csv`
- `outputs/reports/run_20260424_121031_fb4011/memory_hit_rate.md`
- `outputs/reports/run_20260424_121031_fb4011/token_budget.md`
- `outputs/reports/run_20260424_121031_fb4011/scenario_deep_dives/`

Một số số liệu thật từ report:

| Scenario | With-memory relevance | No-memory relevance | Delta |
|---|---:|---:|---:|
| `s01_pref_same_session` | 1.00 | 0.75 | +0.250 |
| `s02_pref_cross_session` | 0.667 | 0.50 | +0.167 |
| `s03_pref_contradiction` | 1.00 | 0.667 | +0.333 |
| `s04_fact_profile` | 1.00 | 0.667 | +0.333 |
| `s05_fact_technical` | 1.00 | 0.50 | +0.500 |
| `s06_episodic_adaptation` | 0.50 | 0.00 | +0.500 |
| `s09_long_trim` | 1.00 | 0.90 | +0.100 |

## Bonus evidence

| Bonus | Status | Evidence |
|---|---|---|
| Redis thật chạy ổn | Done | `docker-compose.yml` có Redis; smoke test thật trả `redis_health=True`, write/read `python`. |
| Chroma thật chạy ổn | Done | `SemanticMemory` dùng `chromadb.PersistentClient`; smoke test trả `chroma_count=1`, hit `User uses Postgres 15`. |
| LLM-based extraction có parse/error handling | Done | `src/agent/services/extraction.py`; tests `tests/unit/test_llm_extraction.py`. |
| Token counting tốt hơn word count | Done | `src/agent/services/tokenizer.py` dùng `tiktoken`, fallback heuristic khi cần. |
| Graph flow demo rõ, dễ explain | Done | LangGraph nodes trong `src/agent/graph/build.py`; UI demo ở `src/agent/ui/app.py` và `scripts/run_ui.py`. |

Ghi chú: benchmark mặc định vẫn dùng rule extractor để deterministic. LLM extractor là optional qua config `memory.extraction_mode: llm`.

## UI demo

Tôi có thêm UI local để test trực quan:

```powershell
.\.venv\Scripts\python -m scripts.run_ui --host 127.0.0.1 --port 8765
```

UI cho phép:

- Chat với memory on/off.
- Compare response `with memory` vs `without memory`.
- Run full demo 3 session: preference write, cross-session recall, episodic recall.
- Xem memory snapshot và latest benchmark report.

Evidence:

- `src/agent/ui/app.py`
- `src/agent/ui/static/index.html`
- `tests/unit/test_ui_service.py`

## Cách chạy

Install:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Run tests:

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider
```

Run deterministic benchmark:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:AGENT_RUNTIME__MODE="mock"
$env:AGENT_EMBEDDING__MODE="hash"
$env:AGENT_USE_FAKE_REDIS="true"
$env:AGENT_USE_EPHEMERAL_CHROMA="true"
.\.venv\Scripts\python -m scripts.run_benchmark
```

Run real OpenAI benchmark:

```powershell
docker compose up -d redis

$env:PYTHONIOENCODING="utf-8"
$env:AGENT_RUNTIME__MODE="openai"
$env:AGENT_EMBEDDING__MODE="openai"
$env:AGENT_USE_FAKE_REDIS="false"
$env:AGENT_USE_EPHEMERAL_CHROMA="true"
$env:REDIS_URL="redis://localhost:6379/0"
.\.venv\Scripts\python -m scripts.run_benchmark
```

Nếu port Redis `6379` đã bị chiếm, dùng Redis đang chạy sẵn hoặc đổi mapping trong `docker-compose.yml`.

## File nộp quan trọng

Không thiếu file bắt buộc theo rubric. Các file chính:

- `README.md`
- `BENCHMARK.md`
- `pyproject.toml`
- `settings.yaml`
- `.env.example`
- `docker-compose.yml`
- `Makefile`
- `src/agent/**`
- `benchmark/scenarios/*.yaml`
- `outputs/reports/run_20260424_121031_fb4011/**`
- `tests/**`

## Bài học rút ra

1. Memory không chỉ là lưu dữ liệu. Phần khó hơn là quyết định khi nào đọc, khi nào không đọc, và inject vào prompt như thế nào để không làm agent nói sai.
2. Capture intent và recall intent phải tách riêng. Nếu một câu correction vừa ghi fact mới vừa đọc fact cũ, agent dễ trả lời bằng dữ liệu lỗi thời.
3. Benchmark no-memory vs with-memory cần cùng graph, cùng scenario, cùng seed. Nếu không, số liệu so sánh dễ bị lệch.
4. Context window management cần policy rõ ràng. L0 phải được bảo vệ, còn L2/L3 có thể trim theo priority.
5. Privacy là một phần của memory design. Profile facts và episodic logs có thể chứa PII hoặc thông tin nhạy cảm, nên cần deletion/TTL/consent ngay từ thiết kế.

## Nếu có thêm thời gian

- Thay regex extractor bằng LLM extractor hoặc hybrid extractor trong benchmark thật, kèm JSON schema validation chặt hơn.
- Thêm UI để inspect "why this memory was recalled".
- Thêm memory deletion/redaction job cho episodic JSONL thay vì append-only.
- Thêm learned router hoặc LLM router để xử lý paraphrase tốt hơn.
- Thêm LLM-as-judge để đánh giá response relevance mềm hơn substring matching.
- Thêm OpenTelemetry traces cho từng node graph khi scale thành service.
