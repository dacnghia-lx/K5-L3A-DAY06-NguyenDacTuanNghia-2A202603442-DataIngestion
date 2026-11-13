# Tiêu chí chọn chiến lược (chốt trước khi chạy retrieval lần đầu)

Ghi ngày 2026-11-13, trước lần chạy `python -m src.run` đầu tiên.

1. Chọn cấu hình chỉ dựa trên **dev** (15 câu): ưu tiên Evidence Hit@3 dev cao nhất.
2. Hoà thì xét Hit@1 dev.
3. Vẫn hoà thì chọn cấu hình ít chunk hơn / tài nguyên thấp hơn.
4. Sau khi chọn, chạy test (5 câu) một lần; không sửa chunking, model, query hay benchmark dựa trên test.

Filter (`python_version`) là ngữ cảnh người dùng cung cấp trước truy xuất (người hỏi nói họ dùng Python 3.11/3.13); không lấy từ gold.
