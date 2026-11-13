# Lần chạy lại (không --rebuild) — kiểm tra nạp lại và ổn định kết quả

Lệnh: `cd starter && python -m src.run` sau lần `--rebuild`.

- `ingest_log_rerun.json`: cả hai collection `embedded=0, deleted=0`, số chunk giữ nguyên (2501 / 1415) → không nhân đôi.
- Hit@1/Hit@3 của A/B/C giống hệt lần chạy chính (results/metrics.md).
- Một số câu đổi thứ tự/ID chunk trong top-3, nhưng **mọi khác biệt đều giữa các chunk có điểm cosine bằng nhau tuyệt đối** (bản sao văn bản giống hệt giữa 3.11/3.13 hoặc giữa topic `compound` và topic riêng). HNSW không cố định thứ tự giữa các điểm hòa, nên exact-vs-HNSW overlap cũng dao động (lần chính A 52/60, B 58/60, C 59/60; lần này 50/60, 55/60, 56/60).
- Nhãn thủ công trong `results/audit/` được chấm trên trace của lần chạy chính (`results/traces/`).
