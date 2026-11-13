# Báo cáo cá nhân — Day 6

**Học viên:** Nguyễn Đắc Tuấn Nghĩa · **MSSV:** 2A202603442 · **Lớp:** L3A
**Ngày chạy:** 2026-11-13 (UTC) · **Chi phí:** 0 USD (không dùng API trả phí)

> Công cụ AI: bài làm được thực hiện cùng Claude (Anthropic) để viết code, soạn bộ câu hỏi và đề xuất nhãn chấm thủ công. Mọi số liệu dưới đây lấy từ file kết quả thật trong `results/`; nhãn thủ công cần được học viên đọc lại và xác nhận (xem mục Hạn chế).

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Corpus là tài liệu ngôn ngữ Python dạng "pydoc topics": file `Lib/pydoc_data/topics.py` của CPython, sinh tự động bởi Sphinx từ Language Reference và một phần Library Reference. Dùng hai snapshot: **Python 3.11** (CPython 3.11.18, Sphinx build "Sun Oct 25 19:41:15 2026") và **Python 3.13** (CPython 3.13.18, "Sun Oct 25 19:31:17 2026"). Bản sao nguyên byte nằm trong `data/raw/`, kèm SHA-256 trong `data/manifest.json`.
  - Giấy phép: Python Software Foundation License v2 (PSF-2.0), cho phép tái phân phối khi giữ thông báo bản quyền; file license đi kèm ở `data/raw/PSF_LICENSE.txt`. Không có dữ liệu cá nhân hay dữ liệu mật.
  - Quy tắc đếm: văn bản không có trang vật lý, nên theo GUIDE tôi dùng **đơn vị nguồn độc lập**: mỗi *topic* là một tài liệu (`document_id = py<version>/<topic>`), mỗi *mục có heading* bên trong topic là một "trang" (`page` = số thứ tự mục, `page_id = py<version>/<topic>#<n>`). Chỉ tính các topic có **≥1.500 ký tự** sau chuẩn hóa và chỉ tính **bản 3.13**: được **42 đơn vị nội dung** (≥30). Bản 3.11 (41 topic đủ chuẩn) là phiên bản khác của cùng tài liệu, chỉ dùng để thử filter `python_version` và **không tính** vào 30 đơn vị để tránh đếm bản gần trùng.
  - Quy mô: 3.13 có 81 topic / 252 trang (mục) / 559.304 ký tự; 3.11 có 79 topic / 216 trang / 479.097 ký tự (`results/corpus_stats.json`).
- **Chuẩn hóa, lỗi và giới hạn:**
  - Đọc file bằng `ast.literal_eval` (không thực thi code). Chuẩn hóa Unicode **NFC** (không dùng NFKC để giữ ký tự như `’`, `…`), CRLF→LF, tab→4 khoảng trắng, xóa NBSP/zero-width, bỏ khoảng trắng cuối dòng, gộp nhiều dòng trống; **giữ thụt lề** vì nó đánh dấu code và grammar.
  - Tách mục theo heading kiểu reStructuredText (dòng tiêu đề + dòng gạch `*`, `=`, `-`, `~`...).
  - Log lỗi `results/errors.log`: **0 lỗi** (không có topic hay mục rỗng). Không cần OCR.
  - Giới hạn: topic `compound` là chương tổng hợp, lặp lại nguyên văn các topic `try`, `for`, `while`, `with`, `match`, `class`, `function`...; đây là nội dung gốc của upstream, không phải do tôi nhân bản. Hai phiên bản 3.11/3.13 cũng trùng phần lớn văn bản. Nhãn `section` lấy đúng heading nguồn, nhưng có chỗ dễ gây hiểu lầm (ví dụ các hàm `pdb.run*/post_mortem` nằm dưới heading "Command-line interface" ở bản 3.13).
- **Embedding, vector store, metric, lệnh chạy và chi phí:**
  - Embedding: **WordLlama `l2_supercat`**, gói `wordllama==0.4.0.post1`, **256 chiều**, chạy local trên CPU. Weights và tokenizer nằm sẵn trong wheel PyPI, được nạp với `disable_download=True`; nếu thiếu thì báo lỗi, không fallback sang vector giả. Query và document xử lý giống nhau (model đối xứng, không prefix), vector được chuẩn hóa L2. Đây là model embedding đã huấn luyện (token embedding trích từ LLM rồi fine-tune cho độ tương đồng câu, average pooling), không phải TF-IDF hay vector ngẫu nhiên. Lý do chọn: môi trường chạy không truy cập được Hugging Face hay API trả phí, và gói này chạy offline trên Windows mà không cần key.
  - Vector store: **Chroma 1.5.9**, `PersistentClient` lưu trên đĩa tại `starter/chroma_db/`, chỉ mục HNSW (tìm kiếm **xấp xỉ**, `search_ef=200`), metric **cosine**, filter bằng `where`. Mỗi cấu hình chunking có một collection: `day06_A_fixed500_o50`, `day06_B_para1000`; C dùng lại collection của B. Kiểm tra exact (numpy brute force) và HNSW: top-3 trùng 52/60 (A), 58/60 (B), 59/60 (C). Ở lần chạy lại, mọi khác biệt đều nằm giữa các chunk có điểm bằng nhau tuyệt đối (`results/rerun_check/README.md`).
  - Lệnh: `cd starter && pip install -r requirements.txt && python -m scripts.verify_benchmark && python -m src.run --rebuild && python -m scripts.audit`.
  - Môi trường đo: container Linux 4 vCPU, Python 3.13.18. Nạp model 0,24 s. Chi phí **0**.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  - Bắt buộc: `document_id` (str), `source` (đường dẫn file nguồn), `page` (int, số thứ tự mục), cùng `page_id` để truy vết.
  - Bổ sung: `python_version` (str, "3.11" hoặc "3.13"): **trường lọc**, lấy từ file nguồn: mỗi file được chép từ thư mục cài đặt của một trình thông dịch cụ thể (CPython 3.11.18 và 3.13.18, đã kiểm tra bằng `python3.11 --version` / `python3.13 --version`), không suy đoán. Lý do: hai phiên bản có câu trả lời khác nhau cho cùng câu hỏi (ví dụ escape sequence không hợp lệ cho `DeprecationWarning` ở 3.11 nhưng `SyntaxWarning` từ 3.12), và người dùng thường biết mình dùng phiên bản nào.
  - Phụ trợ để truy vết: `topic`, `topic_title`, `section` (heading nguồn), `snapshot` (ngày build Sphinx), `char_start`/`char_end`, `chunk_sha256`.

## Cấu hình và benchmark

- **A / B / C:**

  | | Chunking | Kích thước | Overlap | Filter |
  |---|---|---|---|---|
  | A | Cửa sổ ký tự cố định trong từng mục | 500 | 50 | Không |
  | B | Gom đoạn (ngăn bởi dòng trống) trong từng mục; đoạn >1000 ký tự tách theo dòng; thêm dòng ngữ cảnh `[<topic> > <section>]` khi chunk không bắt đầu bằng heading | ≤1000 (+ dòng ngữ cảnh, tối đa 1066) | 0 | Không |
  | C | Giống hệt B (cùng collection, cùng vector) | như B | 0 | `python_version` khi câu hỏi có cung cấp |

  B–C chỉ khác **duy nhất** filter. A–B thay chunking: ranh giới chunk, kích thước và dòng ngữ cảnh heading, cả ba đều thuộc chiến lược chunking. Chunk không bao giờ vượt qua ranh giới mục. Cùng model, store, metric và câu hỏi cho cả ba.
- **≥20 câu, phân chia, câu filter và cách kiểm chứng evidence:**
  - 20 câu tiếng Anh (corpus và model là tiếng Anh) ở `benchmark/questions.json`, gồm các loại direct, paraphrase, condition và metadata_filter. Chia theo topic trước khi chạy: **15 dev** (try, raise, assert, for/while, booleans, global, augassign, assignment-expressions, lambda, strings, debugger, import) và **5 test** (match, typesmapping, class, with).
  - **5 câu có filter**: dev q13 (3.11), q14 (3.13), q15 (3.13); test q19 (3.11), q20 (3.13). Filter là ngữ cảnh người dùng nêu trước khi truy xuất ("I am on Python 3.11..."), không lấy từ gold.
  - Kiểm chứng: `scripts/verify_benchmark.py` tìm evidence (không phân biệt khoảng trắng) trong văn bản đã chuẩn hóa của `gold_source_id`, điền `gold_page`, và liệt kê **mọi trang khác chứa cùng evidence** vào `accepted_gold` (ví dụ bản `compound`, bản 3.11). Với câu có filter, chỉ chấp nhận trang đúng phiên bản. Ví dụ q13 tìm thấy câu "Changed in version 3.6..." ở cả 3.13 nhưng bản 3.13 đã bị loại vì người dùng hỏi về 3.11.
  - Rủi ro rò rỉ: topic `compound` chứa cả văn bản của topic dev và test; đã ghi nhận và chấp nhận `compound` như nguồn hợp lệ.
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test** (`benchmark/selection_criteria.md`): (1) Evidence Hit@3 trên dev; (2) hòa thì Hit@1 dev; (3) vẫn hòa thì ít chunk/tài nguyên hơn; không chỉnh gì dựa trên test.

## Kết quả

Hit tự động (nghiêm ngặt): chunk thuộc trang trong `accepted_gold` **và** chứa **trọn** câu evidence.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 4/15 | 4/15 | 2501 | ingest 3,40 s (embed 0,58 s); query TB 3,8 ms | 0 |
| A | test | 1/5 | 1/5 | 2501 | như trên | 0 |
| B | dev | 7/15 | 8/15 | 1415 | ingest 2,50 s (embed 0,57 s); query TB 3,3 ms | 0 |
| B | test | 0/5 | 1/5 | 1415 | như trên | 0 |
| C | dev | 7/15 | 8/15 | 1415 (dùng chung với B) | query TB 4,7 ms (có `where`) | 0 |
| C | test | 0/5 | 2/5 | 1415 | như trên | 0 |

Chẩn đoán phụ (không thay chỉ số chính): trang gold có trong top-3 nhưng chunk không chứa trọn evidence: **A dev 8/15** (q01, q02, q05, q09, q10, q12, q13, q14), B/C dev 2/15 (q03, q05).

Chấm thủ công trên test, bằng chứng tương đương do người chấm xác nhận (`results/audit/equivalent_evidence_labels.csv`). q17 có câu bước 3 "If duplicate keys are detected... SyntaxError... ValueError" trên trang gold. q18 có câu "Replacing an existing key does not change the order" ở trang `types#14`, một nguồn hợp lệ mà tôi chưa ghi vào gold trước khi chạy. Gold **không bị sửa** sau khi xem test. Kết quả sau điều chỉnh: Hit@3 test A 3/5, B 4/5, C 4/5; Hit@1 test A 3/5, B 2/5, C 2/5.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,3 (10) | 15/15 | test 0/2 · dev 0/3 | 1 / 1 / 3 → 1,4 |
| B | 1,8 (10) | 15/15 | test 0/2 · dev 0/3 | 1 / 0 / 4 → 1,6 |
| C | 1,8 (10, cùng chunk với B) | 15/15 | test 2/2 · dev 3/3 | 1 / 0 / 4 → 1,6 |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- Trace đầy đủ top-3 (câu hỏi, ID chunk, text, score, metadata, hit, tuân thủ filter): `results/traces/{A,B,C}.jsonl`; bảng tổng: `results/metrics.md`.
- Coherence: `results/audit/coherence_samples.json` và `coherence_labels.csv`. 10 vị trí được cố định bằng code **trước khi xem điểm**: sắp xếp page_id của bản 3.13, lấy mỗi trang thứ k (k = 252 // 10), vị trí là ký tự ở giữa trang; chấm chunk chứa vị trí đó.
- Metadata: `results/audit/metadata_audit.csv` (5 câu test × top-3 × 3 chiến lược). Script đối chiếu `source`, `page`, `document_id`, `python_version`, `section` với trang nạp lại từ file nguồn, và kiểm tra text chunk thật sự nằm trong trang đó; sau đó tôi đọc lại bằng tay. Tuân thủ filter: `results/audit/filter_compliance.json`.
- Grounding: `results/audit/grounding_labels.csv`, đọc top-3 của 5 câu test cho từng cấu hình.

## Phân tích và kết luận

- **So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:**
  - **A–B (chunking):** B gấp đôi A trên dev (Hit@3 8/15 so với 4/15; Hit@1 7/15 so với 4/15), dù A thường tìm đúng trang (trang gold trong top-3 ở 12/15 câu dev). Nguyên nhân chính là cửa sổ 500/50 cắt ngang câu evidence (8 câu dev). Coherence của B cao hơn (1,8 so với 1,3): A thường bắt đầu hoặc kết thúc giữa từ (`xpression2)`, `OR Patterns contai`). B có số chunk ít hơn 43% (1415 so với 2501) và ingest nhanh hơn (2,5 s so với 3,4 s). Đổi lại, chunk của B dài hơn nên có thể làm loãng điểm: ở q16 (test), A có Hit@1 còn B lại xếp một đoạn khác cùng trang lên đầu, evidence chỉ ở rank 2.
  - **B–C (filter):** với 15 câu không có filter, C và B giống hệt nhau (đúng thiết kế). Với câu có filter, top-3 của B lẫn phiên bản (tuân thủ 0/5) còn C tuân thủ 5/5. Ở q13 (dev, `py3.11/strings#2`), B vẫn hit nhưng rank 2 là bản 3.13 nói `SyntaxWarning`, mâu thuẫn với câu trả lời đúng cho 3.11; C chỉ giữ 3.11. Ở q20 (test, `py3.13/class#1`), B xếp `py3.11/specialnames#17` lên đầu còn C tìm được câu gold ở rank 3. Filter chỉ giúp được khi lỗi là lẫn phiên bản, không sửa được lỗi xếp hạng sai chủ đề.
  - **Ví dụ sai 1, q09 (dev, `py3.13/global#1`), chiến lược A:** hai chunk rank 1–2 đều thuộc trang gold, nhưng câu "A SyntaxError is raised if a variable is used or assigned | to prior to its global declaration" bị cắt đúng giữa `A:...global#1:c000` và `c001`, vì overlap 50 ký tự không đủ chứa câu. B giữ trọn đoạn và có Hit@1.
  - **Ví dụ sai 2, q19 (test, `py3.11/with#1`, filter 3.11), cả A/B/C đều trượt:** evidence là đoạn code `enter = type(manager).__enter__ ... value = enter(manager)`. Top-3 lại là "Modules", "assert" và "Customizing module attribute access" (`__getattr__`). WordLlama lấy trung bình embedding token nên yếu với văn bản nhiều định danh và code; C đã lọc đúng 3.11 mà vẫn sai chủ đề.
  - Lỗi khác cần ghi: nhiều slot top-3 bị chiếm bởi bản sao giống hệt (3.11/3.13, `compound`/topic riêng) có điểm bằng nhau, làm giảm độ đa dạng của top-3 (ví dụ q12, q17, q18).
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - Trên dev, B và C hòa ở cả ba tiêu chí đã chốt (Hit@3 8/15, Hit@1 7/15, cùng 1415 chunk). Tôi phá hòa bằng một chỉ số dev khác là tuân thủ filter trên các câu dev có filter (C 3/3, B 0/3) và **chọn C**. Cần nói rõ: quy tắc phá hòa này được thêm sau khi xem kết quả dev, và script in dev cùng test trong một lần chạy nên test đã hiện ra cùng lúc. Không có tham số nào được chỉnh sau đó, nhưng test không thể coi là hoàn toàn "chưa nhìn thấy".
  - Trên test, C được 2/5 Hit@3 tự động (4/5 sau khi xác nhận bằng chứng tương đương), grounding 1,6/2, filter 2/2.
  - Đánh đổi: C cần metadata phiên bản đáng tin và người dùng phải cho biết phiên bản; nếu không có thì C giống B. Filter làm query chậm thêm khoảng 1,4 ms (không đáng kể). Với corpus đơn phiên bản, C không mang lại gì thêm so với B.
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - Test chỉ có 5 câu nên mỗi câu bằng 20 điểm phần trăm; khác biệt B và C trên test (1/5 so với 2/5) chỉ do 1 câu. Không suy rộng ra ngoài corpus này.
  - Model embedding nhẹ, chỉ hỗ trợ tiếng Anh, nên câu hỏi phải viết bằng tiếng Anh và điểm tuyệt đối thấp. Kết quả phản ánh cả giới hạn của model, không chỉ của chiến lược dữ liệu.
  - Gold chưa đủ: q17 và q18 có nguồn tương đương mà tôi không liệt kê trước khi chạy. Tôi báo riêng nhãn thủ công thay vì sửa gold.
  - Nhãn coherence, grounding và metadata do một người chấm (tác giả, có AI hỗ trợ đề xuất) nên có nguy cơ thiên lệch; chưa có người chấm thứ hai.
  - "Trang" là số thứ tự mục, không phải trang vật lý. Thời gian đo trên container Linux 4 vCPU, chạy một lần, chưa lặp lại nhiều lần; trên máy khác thời gian sẽ khác. HNSW là tìm kiếm xấp xỉ và thứ tự giữa các điểm hòa không cố định (hit không đổi qua 2 lần chạy).
  - Nạp lại: lần chạy thứ hai `embedded=0, deleted=0`, số chunk không đổi (`results/ingest_log.json`, `results/rerun_check/`). Với tài liệu thay đổi (`results/reingest_change_demo.json`): sửa 1 trang và xóa 1 trang thì chỉ 1 chunk được embed lại và 1 chunk cũ bị xóa (1415 → 1414); khôi phục thì về lại 1415.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?**
  - Dùng embedding transformer đa ngữ (ví dụ `paraphrase-multilingual-MiniLM-L12-v2`) khi có mạng, để hỏi được bằng tiếng Việt và bắt nghĩa tốt hơn; giữ nguyên benchmark để so sánh.
  - Hybrid dense + BM25 cho câu hỏi chứa định danh/code như q19, chỉnh trọng số trên dev.
  - Loại trùng: gom các chunk có `chunk_sha256` giống nhau giữa phiên bản hoặc giữa `compound` và topic riêng, rồi lưu danh sách nguồn trong metadata; hoặc mặc định lọc theo phiên bản mới nhất.
  - Chunk cố định nhưng cắt ở ranh giới câu hoặc tăng overlap; viết thêm câu test (≥10) và đưa nguồn tương đương vào gold ngay từ đầu; nhờ người thứ hai chấm độc lập.
