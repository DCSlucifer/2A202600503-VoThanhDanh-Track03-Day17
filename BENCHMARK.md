# BENCHMARK - Lab 17 Multi-Memory Agent

Tệp này là tài liệu benchmark (đánh giá chuẩn) và reflection (phản ánh) dành cho việc nộp bài Lab 17.
Nguồn thực thi chính là `benchmark/scenarios/*.yaml`; mỗi kịch bản đều bao gồm nhiều lượt tương tác (multi-turn) và được chạy lại hai lần: `with-memory` (có bộ nhớ) và `no-memory` (không có bộ nhớ).

## Cách chạy

Benchmark với kết quả cố định (Deterministic):

```powershell
.\.venv\Scripts\python -m scripts.run_benchmark
```

Benchmark với OpenAI thật:

```powershell
$env:AGENT_RUNTIME__MODE="openai"
$env:AGENT_EMBEDDING__MODE="openai"
$env:AGENT_USE_FAKE_REDIS="false"
$env:AGENT_USE_EPHEMERAL_CHROMA="true"
$env:REDIS_URL="redis://localhost:6379/0"
.\.venv\Scripts\python -m scripts.run_benchmark
```

Mỗi lần chạy sẽ ghi ra:

- `outputs/reports/<run_id>/report.md`
- `outputs/reports/<run_id>/metrics_table.csv`
- `outputs/reports/<run_id>/memory_hit_rate.md`
- `outputs/reports/<run_id>/token_budget.md`
- `outputs/reports/<run_id>/scenario_deep_dives/*.md`

## Ma trận Kịch bản

| # | Kịch bản | Nhóm bộ nhớ | Kỳ vọng khi Không có bộ nhớ | Kỳ vọng khi Có bộ nhớ |
|---:|---|---|---|---|
| 1 | Sở thích trong cùng phiên | hồ sơ sở thích | Có thể hỏi lại sở thích | Nhớ ngôn ngữ ưa thích trong cùng phiên |
| 2 | Sở thích khác phiên | hồ sơ Redis | Phiên/process mới quên sở thích | Gợi ý Python và tránh dùng Java |
| 3 | Xung đột sở thích | cập nhật mâu thuẫn | Không thể biết sở thích mới nhất | Dùng sở thích Rust mới nhất, không dùng Python cũ |
| 4 | Sửa đổi dị ứng trong hồ sơ | hồ sơ thực tế | Không thể trả lời dị ứng | Trả lời dị ứng mới nhất: đậu nành, không phải sữa bò |
| 5 | Sự kiện về tech stack | hồ sơ thực tế | Không thể nhớ tech stack | Nhớ sự kiện kỹ thuật Postgres 15 |
| 6 | Nhầm lẫn Async/await | theo giai thoại | Giải thích chung chung | Bổ sung giải thích đơn giản, từng bước |
| 7 | Bộ nhớ đa dạng, mơ hồ | router phân tán | Thiếu ngữ cảnh liên quan được gợi nhớ | Định tuyến tới nhiều backend bộ nhớ |
| 8 | Sự chính xác không liên quan | quyền riêng tư/sự chính xác | Không rò rỉ thông tin cá nhân | Không chèn sở thích không liên quan |
| 9 | Cắt bớt cuộc hội thoại dài | ngân sách ngữ cảnh | Sở thích có thể bị mất | Giữ nguyên hồ sơ đã ghim dưới áp lực token |
| 10 | Khởi động lạnh | độ bền bỉ | Hoạt động không cần bộ nhớ | Vẫn hoạt động với bộ nhớ trống |

## Các chỉ số đo lường

Benchmark báo cáo:

- Độ liên quan của phản hồi: có mặt các tín hiệu mong đợi và vắng mặt các tín hiệu tiêu cực.
- Tỉ lệ sử dụng ngữ cảnh: tỉ lệ token prompt lấy từ bộ nhớ được gợi nhớ.
- Hiệu suất token: độ liên quan trên mỗi 1k token prompt.
- Tỉ lệ trúng bộ nhớ (hit rate): bộ nhớ được gợi nhớ đóng góp vào các tín hiệu trả lời mong đợi.
- Chỉ số đại diện mức độ hài lòng của người dùng: độ liên quan cộng với việc tôn trọng sở thích và không có tình trạng mất trí nhớ giả.

## Phạm vi Bộ nhớ

- Ngắn hạn: `ConversationBuffer` chạy trực tiếp trong process.
- Hồ sơ dài hạn: Các sở thích và sự kiện trên Redis.
- Theo giai thoại (Episodic): Log JSONL với các thẻ sự kiện đáng chú ý như `confusion` (nhầm lẫn).
- Ngữ nghĩa (Semantic): Chỉ mục vector Chroma cho các sở thích, sự kiện đã được chắt lọc, và các giai thoại đáng chú ý.

## Phản ánh về Quyền riêng tư

Bộ nhớ nhạy cảm nhất là hồ sơ dài hạn vì nó có thể chứa PII (Thông tin nhận dạng cá nhân) hoặc các thuộc tính người dùng riêng tư như tên, dị ứng, vai trò, công ty, dự án, và tech stack. Bộ nhớ theo giai thoại cũng rủi ro vì nó có thể lưu lại sự nhầm lẫn của người dùng, lỗi hoặc ngữ cảnh làm việc.

Hệ thống cần yêu cầu sự đồng ý trước khi lưu trữ các sự kiện hồ sơ nhạy cảm trong môi trường production. Các sự kiện hồ sơ trên Redis có hỗ trợ TTL (thời gian sống), và việc xóa cấp độ người dùng có thể thực hiện thông qua `RedisMemory.clear_user(user_id)`. Bộ nhớ ngữ nghĩa hỗ trợ xóa theo người dùng với `SemanticMemory.delete(user_id=...)`. Bộ nhớ đệm ngắn hạn có phạm vi theo phiên và có thể xóa theo từng phiên. File JSONL theo giai thoại chỉ cho phép ghi thêm (append-only) trong bài lab này, vì vậy việc xóa trong môi trường production sẽ cần một job thu gọn (compaction) hoặc bôi đen/xóa thông tin nhạy cảm (redaction); đây là hạn chế rõ ràng nhất về quyền riêng tư.

Lỗi truy xuất là một rủi ro quyền riêng tư khác: nếu độ chính xác của router kém, tác nhân (agent) có thể chèn các chi tiết cá nhân không liên quan vào những câu trả lời không liên quan. Kịch bản 8 kiểm tra điều này bằng cách đặt một câu hỏi không liên quan sau khi đã có sở thích được lưu.

## Hạn chế Kỹ thuật

- Việc trích xuất sự kiện và sở thích dựa trên regex, do đó việc gợi nhớ đáng tin cậy trong các bài test benchmark nhưng sẽ bỏ sót nhiều cách diễn đạt khác nhau (paraphrase).
- Chroma lưu trữ các sự kiện đã được chắt lọc và các giai thoại đáng chú ý, chứ không phải các lượt hội thoại thô; điều này làm giảm rủi ro về quyền riêng tư nhưng có thể làm giảm chi tiết gợi nhớ.
- Bộ nhớ theo giai thoại hiện tại quét các file JSONL và không thể mở rộng (scale) tốt với lượng log lớn.
- Điểm mức độ hài lòng của người dùng là một phép thử mang tính đại diện xác định (deterministic proxy), không phải đánh giá từ con người.
- Router đang dựa trên các quy tắc (rule-based); một router học máy hoặc LLM có khả năng sẽ cải thiện việc gợi nhớ đối với lưu lượng truy cập production đa nghĩa.
