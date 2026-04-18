==================================================
TELEGRAM MILK TEA ORDER BOT - SYSTEM README
==================================================

1) Tong quan
- Day la Telegram bot ho tro:
  - xem menu
  - them/xoa mon trong gio
  - checkout
  - nhan thong tin giao hang
  - xac nhan thanh toan (demo)
- Bot co 2 che do van hanh:
  - Polling (thuong dung local)
  - Webhook (thuong dung tren Render)

2) Cau truc du an
- bot.py: source chinh cua bot
- Menu.csv: du lieu menu
- orders.jsonl: log su kien don hang
- .env.example: mau bien moi truong
- requirements.txt: danh sach thu vien Python
- Dockerfile, Procfile, render.yaml: phuc vu deploy

3) Yeu cau he thong
- Python 3.10+
- Telegram Bot Token
- (Tuy chon) OpenAI API key de chat AI
- (Tuy chon) thong tin ngan hang de tao link VietQR

4) Cai dat local
4.1 Tao va kich hoat virtual environment (PowerShell)
	 python -m venv .venv
	 .\.venv\Scripts\Activate.ps1

4.2 Cai dependencies
	 pip install -r requirements.txt

4.3 Cau hinh bien moi truong
	 copy .env.example .env

	 Bat buoc:
	 - TELEGRAM_BOT_TOKEN

	 Tuy chon:
	 - OPENAI_API_KEY
	 - OPENAI_MODEL (mac dinh: gpt-4o-mini)
	 - BANK_CODE
	 - BANK_ACCOUNT
	 - BANK_ACCOUNT_NAME
	 - WEBHOOK_HOST

4.4 Chay bot
	 python bot.py

5) Lenh Telegram ho tro
- /start
- /help
- /menu
- /add <ma_mon> <M|L> <so_luong>
- /cart
- /remove <so_dong>
- /clear
- /checkout
- /order
- /paid
- /cancelorder

6) Luong xu ly don hang
1. Nguoi dung xem menu va them mon vao gio
2. /checkout de tao don
3. Bot yeu cau thong tin giao hang theo mau:
	Ten: ...
	SDT: ...
	Dia chi: ...
4. Bot luu su kien vao orders.jsonl:
	- order_created
	- delivery_info_confirmed
	- payment_confirmed hoac payment_confirmed_by_text

7) Cac bien moi truong
- TELEGRAM_BOT_TOKEN: bat buoc
- OPENAI_API_KEY: bat AI chat
- OPENAI_MODEL: model OpenAI (default gpt-4o-mini)
- BANK_CODE/BANK_ACCOUNT/BANK_ACCOUNT_NAME: tao link VietQR
- WEBHOOK_HOST: URL public cua service (khi deploy webhook)
- PORT: cong web service (host thuong tu cap)

8) Deploy voi Docker/Render
- Du an da co san Dockerfile va render.yaml
- Tren Render:
  1. Tao Web Service tu repository nay
  2. Set environment variables trong Render dashboard
  3. Redeploy sau moi lan doi bien moi truong

Luu y:
- Render KHONG doc file .env local
- Neu khong set WEBHOOK_HOST, bot se thu dung RENDER_EXTERNAL_URL

9) Van hanh va giam sat
- Kiem tra log khoi dong:
  - "Bot dang chay o che do webhook: ..." hoac
  - "Bot dang chay o che do polling..."
- Theo doi file orders.jsonl de doi soat su kien don hang

10) Loi thuong gap
1. Thieu TELEGRAM_BOT_TOKEN
	- Trieu chung: bot khong khoi dong
	- Cach xu ly: bo sung token vao .env hoac environment cua host

2. Da doi thong tin ngan hang nhung QR van cu
	- Nguyen nhan: moi sua .env local, chua sua tren Render
	- Cach xu ly: cap nhat bien moi truong tren Render va redeploy

3. Bot khong tra loi sau khi tat may local
	- Nguyen nhan: bot dang chay polling local
	- Cach xu ly: deploy len host de chay 24/7

11) Bao mat
- Khong commit file .env
- Khong log thong tin nhay cam (token, API key)
- Nen xoay token/API key ngay khi nghi lo thong tin
