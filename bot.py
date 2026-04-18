import asyncio
import csv
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from urllib.parse import quote_plus

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)


@dataclass
class MenuItem:
    category: str
    item_id: str
    name: str
    description: str
    price_m: int
    price_l: int
    available: bool

    def price_by_size(self, size: str) -> int:
        if self.category.lower() == "topping":
            return self.price_m
        return self.price_l if size.upper() == "L" else self.price_m


@dataclass
class CartLine:
    item_id: str
    size: str
    qty: int


@dataclass
class Session:
    cart: List[CartLine] = field(default_factory=list)
    pending_order: "PendingOrder | None" = None


@dataclass
class PendingOrder:
    order_code: str
    amount: int
    lines: List[CartLine]
    created_at: str
    qr_link: str | None
    payment_status: str = "unpaid"
    delivery_name: str = ""
    delivery_phone: str = ""
    delivery_address: str = ""


SESSIONS: Dict[int, Session] = {}
MENU: Dict[str, MenuItem] = {}
OPENAI_CLIENT: OpenAI | None = None
OPENAI_MODEL: str = "gpt-4o-mini"


def load_menu(csv_path: str) -> Dict[str, MenuItem]:
    menu: Dict[str, MenuItem] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = MenuItem(
                category=row["category"],
                item_id=row["item_id"].upper(),
                name=row["name"],
                description=row["description"],
                price_m=int(row["price_m"]),
                price_l=int(row["price_l"]),
                available=row["available"].strip().lower() == "true",
            )
            if item.available:
                menu[item.item_id] = item
    return menu


def get_session(user_id: int) -> Session:
    if user_id not in SESSIONS:
        SESSIONS[user_id] = Session()
    return SESSIONS[user_id]


def vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + "đ"


def build_menu_text() -> str:
    by_category: Dict[str, List[MenuItem]] = {}
    for item in MENU.values():
        by_category.setdefault(item.category, []).append(item)

    lines = ["MENU HIEN CO:"]
    for category in sorted(by_category.keys()):
        lines.append(f"\n{category}:")
        for item in sorted(by_category[category], key=lambda x: x.item_id):
            if item.category.lower() == "topping":
                lines.append(f"- {item.item_id} | {item.name} | {vnd(item.price_m)}")
            else:
                lines.append(
                    f"- {item.item_id} | {item.name} | M {vnd(item.price_m)} | L {vnd(item.price_l)}"
                )
    lines.append("\nDung /add <ma_mon> <M|L> <so_luong>. Vi du: /add TS01 L 2")
    lines.append("Voi topping, size co the de M. Vi du: /add TOP01 M 1")
    return "\n".join(lines)


def cart_total(session: Session) -> int:
    total = 0
    for line in session.cart:
        item = MENU.get(line.item_id)
        if not item:
            continue
        total += item.price_by_size(line.size) * line.qty
    return total


def build_cart_text(session: Session) -> str:
    if not session.cart:
        return "Gio hang dang trong. Dung /menu de xem mon va /add de them mon."

    lines = ["GIO HANG CUA BAN:"]
    for idx, line in enumerate(session.cart, start=1):
        item = MENU.get(line.item_id)
        if not item:
            continue
        unit_price = item.price_by_size(line.size)
        line_total = unit_price * line.qty
        size_label = "" if item.category.lower() == "topping" else f" size {line.size.upper()}"
        lines.append(
            f"{idx}. {item.name}{size_label} x{line.qty} = {vnd(line_total)} ({line.item_id})"
        )

    lines.append(f"\nTong tam tinh: {vnd(cart_total(session))}")
    lines.append("Dung /remove <so_dong> de xoa, /clear de xoa tat ca, /checkout de chot don.")
    return "\n".join(lines)


def build_lines_text(lines_data: List[CartLine]) -> str:
    lines = []
    for idx, line in enumerate(lines_data, start=1):
        item = MENU.get(line.item_id)
        if not item:
            continue
        unit_price = item.price_by_size(line.size)
        line_total = unit_price * line.qty
        size_label = "" if item.category.lower() == "topping" else f" size {line.size.upper()}"
        lines.append(
            f"{idx}. {item.name}{size_label} x{line.qty} = {vnd(line_total)} ({line.item_id})"
        )
    return "\n".join(lines) if lines else "Khong co mon hop le trong don."


def build_pending_order_text(order: PendingOrder) -> str:
    payment_label = "DA THANH TOAN" if order.payment_status == "paid" else "CHUA THANH TOAN"
    rows = [
        f"DON HANG {order.order_code}",
        build_lines_text(order.lines),
        f"\nTong thanh toan: {vnd(order.amount)}",
        f"Trang thai thanh toan: {payment_label}",
    ]
    if order.delivery_phone and order.delivery_address:
        rows.append(f"Nguoi nhan: {order.delivery_name}")
        rows.append(f"SDT: {order.delivery_phone}")
        rows.append(f"Dia chi: {order.delivery_address}")
    return "\n".join(rows)


def parse_delivery_info(user_text: str) -> Dict[str, str] | None:
    text = user_text.strip()
    if not text:
        return None

    name_match = re.search(r"(?:ten|nguoi\s*nhan)\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    phone_match = re.search(
        r"(?:sdt|so\s*dien\s*thoai|dien\s*thoai)\s*[:\-]\s*([0-9+() .\-]{8,20})",
        text,
        flags=re.IGNORECASE,
    )
    address_match = re.search(r"(?:dia\s*chi|dc)\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)

    if not (name_match and phone_match and address_match):
        return None

    phone = re.sub(r"[^0-9+]", "", phone_match.group(1)).strip()
    if len(phone) < 8:
        return None

    return {
        "name": name_match.group(1).strip(),
        "phone": phone,
        "address": address_match.group(1).strip(),
    }


def create_vietqr_link(amount: int, order_code: str) -> str | None:
    bank_code = os.getenv("BANK_CODE", "").strip()
    bank_account = os.getenv("BANK_ACCOUNT", "").strip()
    account_name = os.getenv("BANK_ACCOUNT_NAME", "").strip()
    if not bank_code or not bank_account:
        return None

    add_info = quote_plus(f"Thanh toan don {order_code}")
    account_name_param = quote_plus(account_name) if account_name else ""

    if account_name_param:
        return (
            f"https://img.vietqr.io/image/{bank_code}-{bank_account}-compact2.png"
            f"?amount={amount}&addInfo={add_info}&accountName={account_name_param}"
        )
    return f"https://img.vietqr.io/image/{bank_code}-{bank_account}-compact2.png?amount={amount}&addInfo={add_info}"


def save_order_event(
    user_id: int,
    order: PendingOrder,
    event: str,
    username: str = "",
    full_name: str = "",
) -> None:
    payload = {
        "event": event,
        "saved_at": datetime.now().isoformat(),
        "order_code": order.order_code,
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "created_at": order.created_at,
        "amount": order.amount,
        "payment_status": order.payment_status,
        "delivery_name": order.delivery_name,
        "delivery_phone": order.delivery_phone,
        "delivery_address": order.delivery_address,
        "lines": [line.__dict__ for line in order.lines],
    }
    with open("orders.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_short_menu_for_ai() -> str:
    rows = []
    for item in sorted(MENU.values(), key=lambda x: x.item_id):
        if item.category.lower() == "topping":
            rows.append(f"{item.item_id}: {item.name}, gia {item.price_m}")
        else:
            rows.append(f"{item.item_id}: {item.name}, M {item.price_m}, L {item.price_l}")
    return "\n".join(rows)


async def ai_chat_reply(user_text: str) -> str:
    if not OPENAI_CLIENT:
        return (
            "Minh da nhan tin nhan cua ban. De dat nhanh, hay dung lenh: \n"
            "/menu\n/add <ma_mon> <M|L> <so_luong>\n/cart\n/checkout"
        )

    system_prompt = (
        "Ban la nhan vien quan tra sua, noi chuyen than thien, ngan gon. "
        "Chi tra loi bang tieng Viet khong dau. "
        "Huong dan khach dat mon bang cac lenh /menu, /add, /cart, /checkout. "
        "Khong tu y xac nhan da dat mon neu khach chua dung lenh /add.\n\n"
        f"Menu:\n{build_short_menu_for_ai()}"
    )

    def _call() -> str:
        response = OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or "Ban thu gui lai tin nhan nhe."

    return await asyncio.to_thread(_call)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Xin chao, minh la bot dat tra sua.\n"
        "Lenh co san:\n"
        "/menu - xem menu\n"
        "/add <ma_mon> <M|L> <so_luong> - them mon\n"
        "/cart - xem gio\n"
        "/remove <so_dong> - xoa 1 dong\n"
        "/clear - xoa gio\n"
        "/checkout - chot don va nhap thong tin giao hang\n"
        "/order - xem don dang xu ly\n"
        "/paid - xac nhan da thanh toan (demo)\n"
        "/cancelorder - huy don dang xu ly\n"
        "/help - xem huong dan"
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_cmd(update, context)


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(build_menu_text())


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)

    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Sai cu phap. Dung: /add <ma_mon> <M|L> <so_luong>")
        return

    item_id = args[0].upper().strip()
    size = args[1].upper().strip()

    try:
        qty = int(args[2])
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("So luong phai la so nguyen duong.")
        return

    item = MENU.get(item_id)
    if not item:
        await update.message.reply_text("Khong tim thay ma mon. Dung /menu de xem lai.")
        return

    if item.category.lower() != "topping" and size not in {"M", "L"}:
        await update.message.reply_text("Do uong chi co size M hoac L.")
        return

    if item.category.lower() == "topping":
        size = "M"

    session.cart.append(CartLine(item_id=item_id, size=size, qty=qty))
    unit = item.price_by_size(size)
    await update.message.reply_text(
        f"Da them: {item.name} x{qty}, don gia {vnd(unit)}.\n{build_cart_text(session)}"
    )


async def cart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)
    await update.message.reply_text(build_cart_text(session))


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)

    if not context.args:
        await update.message.reply_text("Dung: /remove <so_dong> (xem so dong bang /cart)")
        return

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("So dong khong hop le.")
        return

    if idx < 0 or idx >= len(session.cart):
        await update.message.reply_text("Khong co dong nay trong gio.")
        return

    removed = session.cart.pop(idx)
    item = MENU.get(removed.item_id)
    item_name = item.name if item else removed.item_id
    await update.message.reply_text(f"Da xoa {item_name}.\n{build_cart_text(session)}")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)
    session.cart.clear()
    await update.message.reply_text("Da xoa toan bo gio hang.")


async def order_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)

    if not session.pending_order:
        await update.message.reply_text("Ban chua co don nao dang xu ly.")
        return

    await update.message.reply_text(build_pending_order_text(session.pending_order))


async def paid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)
    order = session.pending_order

    if not order:
        await update.message.reply_text("Khong co don nao can xac nhan thanh toan.")
        return

    if not order.delivery_phone or not order.delivery_address:
        await update.message.reply_text(
            "Don nay chua du thong tin giao hang. Vui long gui theo mau:\n"
            "Ten: Nguyen Van A\nSDT: So dien thoai nguoi nhan\nDia chi: So nha, duong, quan\nVi du: 0812345678"
        )
        return

    if order.payment_status == "paid":
        await update.message.reply_text("Don nay da o trang thai DA THANH TOAN roi.")
        return

    order.payment_status = "paid"
    user = update.effective_user
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    save_order_event(
        user_id=user_id,
        order=order,
        event="payment_confirmed",
        username=user.username or "",
        full_name=full_name,
    )
    await update.message.reply_text(
        "Da ghi nhan thanh toan. Quan se lam mon va giao hang som.\n\n"
        + build_pending_order_text(order)
    )


async def cancelorder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)
    if not session.pending_order:
        await update.message.reply_text("Khong co don nao de huy.")
        return

    order_code = session.pending_order.order_code
    session.pending_order = None
    await update.message.reply_text(f"Da huy don dang xu ly: {order_code}")


async def checkout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session(user_id)

    if session.pending_order and session.pending_order.payment_status != "paid":
        await update.message.reply_text(
            "Ban dang co 1 don chua hoan tat. Dung /order de xem, /paid de xac nhan thanh toan, "
            "hoac /cancelorder de huy don do."
        )
        return

    if not session.cart:
        await update.message.reply_text("Gio hang trong. Ban hay them mon truoc khi checkout.")
        return

    amount = cart_total(session)
    order_code = datetime.now().strftime("OD%y%m%d%H%M%S")
    qr_link = create_vietqr_link(amount, order_code)

    order_lines = [CartLine(item_id=line.item_id, size=line.size, qty=line.qty) for line in session.cart]
    session.pending_order = PendingOrder(
        order_code=order_code,
        amount=amount,
        lines=order_lines,
        created_at=datetime.now().isoformat(),
        qr_link=qr_link,
    )
    session.cart.clear()

    lines = [
        f"DON HANG {order_code}",
        build_lines_text(order_lines),
        f"\nTong thanh toan: {vnd(amount)}",
        "Trang thai thanh toan: CHUA THANH TOAN",
    ]
    if qr_link:
        lines.append(f"QR thanh toan: {qr_link}")
    else:
        lines.append(
            "Chua cau hinh BANK_CODE/BANK_ACCOUNT nen chua tao duoc link QR."
        )
    lines.append(
        "\nHUONG DAN SAU BUOC NAY:\n"
        "1) Neu ban thanh toan that: quet QR/chuyen khoan truoc.\n"
        "2) Gui thong tin giao hang theo mau ben duoi.\n"
        "3) Neu dang demo (khong co giao dich that), sau khi gui thong tin giao hang hay dung /paid de qua buoc xac nhan thanh toan."
    )

    user = update.effective_user
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    save_order_event(
        user_id=user_id,
        order=session.pending_order,
        event="order_created",
        username=user.username or "",
        full_name=full_name,
    )
    lines.append(
        "\nVui long gui thong tin giao hang theo mau:\n"
        "Ten: Nguyen Van A\nSDT: So dien thoai nguoi nhan\nDia chi: So nha, duong, quan\nVi du: 0812345678"
    )

    await update.message.reply_text("\n".join(lines))


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    session = get_session(user_id)
    order = session.pending_order

    if order and not order.delivery_phone:
        delivery = parse_delivery_info(update.message.text)
        if not delivery:
            await update.message.reply_text(
                "Minh chua doc du thong tin giao hang. Ban gui theo mau:\n"
                "Ten: Nguyen Van A\nSDT: So dien thoai nguoi nhan\nDia chi: So nha, duong, quan\nVi du: 0812345678"
            )
            return

        order.delivery_name = delivery["name"]
        order.delivery_phone = delivery["phone"]
        order.delivery_address = delivery["address"]
        user = update.effective_user
        full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
        save_order_event(
            user_id=user_id,
            order=order,
            event="delivery_info_confirmed",
            username=user.username or "",
            full_name=full_name,
        )

        reply_lines = [
            "Da nhan thong tin giao hang.",
            build_pending_order_text(order),
            "\nNeu ban da thanh toan, dung /paid de xac nhan (demo).",
        ]
        await update.message.reply_text("\n".join(reply_lines))
        return

    if order and order.payment_status == "unpaid":
        text_lc = update.message.text.lower()
        paid_keywords = ["da chuyen khoan", "da thanh toan", "da ck", "ck roi", "chuyen khoan roi"]
        if any(keyword in text_lc for keyword in paid_keywords):
            order.payment_status = "paid"
            user = update.effective_user
            full_name = " ".join(part for part in [user.first_name, user.last_name] if part)
            save_order_event(
                user_id=user_id,
                order=order,
                event="payment_confirmed_by_text",
                username=user.username or "",
                full_name=full_name,
            )
            await update.message.reply_text(
                "Minh da ghi nhan thong bao thanh toan. Quan se xu ly don ngay.\n\n"
                + build_pending_order_text(order)
            )
            return

    reply = await ai_chat_reply(update.message.text)
    await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Loi khi xu ly update", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Bot dang gap loi tam thoi. Ban gui lai lenh giup minh nhe."
        )


def main() -> None:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Thieu TELEGRAM_BOT_TOKEN trong file .env")

    global MENU
    MENU = load_menu("Menu.csv")

    global OPENAI_CLIENT
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        OPENAI_CLIENT = OpenAI(api_key=api_key)

    global OPENAI_MODEL
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("cart", cart_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("checkout", checkout_cmd))
    app.add_handler(CommandHandler("order", order_cmd))
    app.add_handler(CommandHandler("paid", paid_cmd))
    app.add_handler(CommandHandler("cancelorder", cancelorder_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    webhook_host = os.getenv("WEBHOOK_HOST", "").strip()
    if not webhook_host:
        # Render web service exposes a public URL that can be used for Telegram webhook.
        webhook_host = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    webhook_port = int(os.getenv("PORT", "10000"))

    if webhook_host:
        webhook_url = f"{webhook_host.rstrip('/')}/{token}"
        print(f"Bot dang chay o che do webhook: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=webhook_port,
            url_path=token,
            webhook_url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
        return

    print("Bot dang chay o che do polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
