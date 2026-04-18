BỐI CẢNH
Mẹ bạn mở một quán trà sữa (menu như file csv đính kèm), chủ yếu bán trực tiếp tại cửa
hàng. Quán nằm gần khu văn phòng nên nhiều khách thường nhắn tin để đặt online.
Gần đây lượng đơn tăng nhiều, mẹ trả lời không kịp, thông tin đơn dễ bị thiếu hoặc
nhầm, khách phải chờ lâu nên bắt đầu phàn nàn.

ĐỀ BÀI
Ứng dụng các mô hình ngôn ngữ lớn để phát triển một bản sao AI của mẹ, hoạt động
trên Telegram hoặc Zalo để giao tiếp với khách, hỗ trợ khách đặt món, tính tiền. Sau khi
khách tính tiền sẽ tổng hợp lại thông tin để làm món và giao hàng.

Thông tin
Thang điểm đánh giá dựa trên khả năng bot
sẽ vận hành hiệu quả trên thực tế.
Nếu có yêu cầu, BTC sẽ cấp cho mỗi bạn
một api key của OpenAI để sử dụng trong dự
án.
Khuyến khích sử dụng payOS để tạo QR
thanh toán và xác nhận thanh toán.
Cho phép vibe code nhưng phải kiểm soát và
hiểu được những phần code do AI tạo ra.

Hình thức nộp bài
Bài nộp gửi về email hr@cas.so, bao gồm:
Video demo (Gửi link Google Drive hoặc
Youtube)
Mã nguồn (Repo link tại Github hoặc
GitLab,…)
Tài liệu phân tích giải pháp (file pdf)
Khuyến khích ứng viên deploy lên server
& gửi tên Bot để BGK có thể trực tiếp vào
để testing.

==================================================
HUONG DAN CHAY CODE MVP (TELEGRAM BOT)
==================================================

1) Chuan bi moi truong
- Cai Python 3.10+.
- Tao virtual env:
	python -m venv .venv
- Kich hoat tren PowerShell:
	.\.venv\Scripts\Activate.ps1

2) Cai thu vien
- pip install -r requirements.txt

3) Cau hinh bien moi truong
- Copy file .env.example thanh .env
- Dien TELEGRAM_BOT_TOKEN
- Neu muon chat AI: dien OPENAI_API_KEY
- Neu muon tao link VietQR khi checkout: dien BANK_CODE, BANK_ACCOUNT, BANK_ACCOUNT_NAME

4) Chay bot
- python bot.py

5) Lenh su dung trong Telegram
- /start
- /menu
- /add <ma_mon> <M|L> <so_luong>
- /cart
- /remove <so_dong>
- /clear
- /checkout
- /order
- /paid
- /cancelorder

6) Deploy nhanh bang Docker
- Repo nay co san Dockerfile va Procfile de chay tren cac nen tang ho tro Docker.
- Cach de nhat la dung Render web service hoac nen tang co ho tro Docker.
- Can set cac bien moi truong tren host:
	TELEGRAM_BOT_TOKEN
	OPENAI_API_KEY (neu dung AI)
	OPENAI_MODEL (neu muon doi model)
	BANK_CODE
	BANK_ACCOUNT
	BANK_ACCOUNT_NAME
	WEBHOOK_HOST (neu deploy webhook)
	PORT (thuong host se cap san)

6.1) Deploy tren Render
- Vao Render -> New -> Web Service.
- Connect repository GitHub nay.
- Render se doc file render.yaml va tao web service Docker tu dong.
- Add cac environment variables o tren trong trang setting cua Render (Environment), KHONG dung file .env local.
- Neu dung webhook, co the dien WEBHOOK_HOST bang URL public cua service, vi du https://ten-service.onrender.com.
- Neu khong dien WEBHOOK_HOST, bot tu dong thu dung bien RENDER_EXTERNAL_URL do Render cap.

7) Ghi chu deploy
- Bot ho tro ca polling va webhook.
- Khi co WEBHOOK_HOST, bot se chay tren web service.
- Khi khong co WEBHOOK_HOST, bot se chay polling.

==================================================
XU LY SU CO THUONG GAP TREN RENDER
==================================================

1) Da doi BANK_ACCOUNT/BANK_ACCOUNT_NAME nhung QR van hien thong tin cu
- Nguyen nhan: ban moi doi file .env local; Render khong doc file .env trong may cua ban.
- Cach sua:
	- Vao Render -> Service -> Environment
	- Cap nhat BANK_CODE, BANK_ACCOUNT, BANK_ACCOUNT_NAME
	- Bam Save Changes va Redeploy service

2) Tat VS Code xong bot khong tra loi
- Neu bot chi chay local (`python bot.py`), tat VS Code thi process dung la binh thuong.
- De bot chay 24/7 tren Render:
	- Bao dam service dang Deploy thanh cong va status la Live.
	- Dat TELEGRAM_BOT_TOKEN dung.
	- Kiem tra logs co dong "Bot dang chay o che do webhook".
	- Neu chua co, them WEBHOOK_HOST hoac de bot tu lay RENDER_EXTERNAL_URL roi redeploy lai.

Ghi chu:
- Menu doc tu file Menu.csv.
- Don hang duoc luu vao orders.jsonl theo tung su kien: tao don, xac nhan thong tin giao hang, xac nhan thanh toan.
- Sau /checkout, bot yeu cau nguoi dung gui thong tin giao hang theo mau:
	Ten: Nguyen Van A
	SDT: So dien thoai nguoi nhan
	Dia chi: So nha, duong, quan
	Vi du: 0812345678
- Khi chua cau hinh thong tin ngan hang, /checkout van chot don nhung khong tao link QR.
- /paid la buoc xac nhan thanh toan phuc vu demo quy trinh (chua doi soat giao dich tu dong).
