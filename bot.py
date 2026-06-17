import json
import os
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ================== НАСТРОЙКИ ==================
TOKEN = "8525903678:AAGUDpBKwaFoXmCITcttc062tlUX1fwtsrI"
STAFF_CHAT_ID = -1004342122879
ADMIN_ID = 477402841

MENU_FILE = "menu.json"
LOCATIONS_FILE = "locations.json"
ORDER_FILE = "order_number.json"

# Заказ
(
    ORDER_COFFEE,
    ORDER_QTY,
    ORDER_SUGAR,
    ORDER_MORE_COFFEE,
    ORDER_DOG,
    ORDER_PHONE,
    ORDER_COMMENT,
    ORDER_LOCATION,
    ORDER_CONFIRM,
) = range(100, 109)

# Админка
(
    ADMIN_MENU,
    ADMIN_ADD_COFFEE_NAME,
    ADMIN_ADD_COFFEE_PRICE,
    ADMIN_EDIT_PRICE_NAME,
    ADMIN_EDIT_PRICE_VALUE,
    ADMIN_DELETE_COFFEE_NAME,
    ADMIN_FRENCHDOG_PRICE,
    ADMIN_ADD_LOCATION_NAME,
    ADMIN_DELETE_LOCATION_NAME,
) = range(200, 209)


# ================== ФАЙЛЫ ==================
def ensure_files():
    if not os.path.exists(MENU_FILE):
        save_menu({
            "coffee": {
                "Капучино": 4,
                "Латте": 4,
                "Американо": 3
            },
            "frenchdog": 4.5
        })

    if not os.path.exists(LOCATIONS_FILE):
        save_locations([
            "Беседка общежитие",
            "Стадион",
            "Столовая",
            "Беседка за домиками"
        ])

    if not os.path.exists(ORDER_FILE):
        with open(ORDER_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_order": 0}, f, ensure_ascii=False, indent=2)


def load_menu():
    ensure_files()
    with open(MENU_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "coffee" not in data:
        data["coffee"] = {}
    if "frenchdog" not in data:
        data["frenchdog"] = 4.5
    return data


def save_menu(data):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_locations():
    ensure_files()
    with open(LOCATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or not data:
        data = ["Стадион"]
        save_locations(data)
    return data


def save_locations(data):
    with open(LOCATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_order_number():
    ensure_files()
    with open(ORDER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["last_order"] = int(data.get("last_order", 0)) + 1

    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data["last_order"]


def money(value):
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return str(value).replace(".", ",")


def main_keyboard(is_admin=False):
    buttons = [
        ["🛒 Сделать заказ"],
        ["📋 Меню"],
    ]
    if is_admin:
        buttons.append(["⚙️ Админка"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def is_admin_user(update: Update):
    return ADMIN_ID == 0 or update.effective_user.id == ADMIN_ID


def order_summary(user_data, with_total=True):
    menu = load_menu()
    lines = []
    total = 0

    for item in user_data.get("cart", []):
        name = item["name"]
        qty = int(item["qty"])
        sugar = item["sugar"]
        price = float(menu["coffee"].get(name, 0))
        item_total = price * qty
        total += item_total
        lines.append(f"• {name} × {qty}, {sugar} = {money(item_total)} руб")

    dog_qty = int(user_data.get("dog_qty", 0))
    if dog_qty > 0:
        dog_total = float(menu.get("frenchdog", 4.5)) * dog_qty
        total += dog_total
        lines.append(f"• Френчдог × {dog_qty} = {money(dog_total)} руб")

    text = "\n".join(lines) if lines else "Корзина пустая"

    if with_total:
        text += f"\n\n💰 Итого: {money(total)} руб"

    return text, total


# ================== ОБЩИЕ КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌺 Добро пожаловать в Aloha Coffee!",
        reply_markup=main_keyboard(is_admin_user(update))
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = load_menu()
    locations = load_locations()

    coffee_text = "\n".join(
        f"☕ {name} — {money(price)} руб"
        for name, price in menu["coffee"].items()
    )

    loc_text = "\n".join(f"• {loc}" for loc in locations)

    text = (
        "📋 Меню Aloha Coffee\n\n"
        f"{coffee_text}\n\n"
        f"🌭 Френчдог — {money(menu['frenchdog'])} руб\n\n"
        "📍 Локации доставки:\n"
        f"{loc_text}"
    )
    await update.message.reply_text(text)


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш Telegram ID:\n{update.effective_user.id}")


async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ID этого чата:\n{update.effective_chat.id}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=main_keyboard(is_admin_user(update))
    )
    return ConversationHandler.END


# ================== ЗАКАЗ ==================
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = load_menu()

    if not menu["coffee"]:
        await update.message.reply_text("Сейчас меню кофе пустое.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["cart"] = []

    keyboard = [[name] for name in menu["coffee"].keys()]
    keyboard.append(["❌ Отмена"])

    await update.message.reply_text(
        "☕ Выберите кофе:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_COFFEE


async def order_choose_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    menu = load_menu()
    if text not in menu["coffee"]:
        await update.message.reply_text("Выберите кофе кнопкой.")
        return ORDER_COFFEE

    context.user_data["current_coffee"] = text
    keyboard = [["1", "2", "3"], ["4", "5"], ["❌ Отмена"]]

    await update.message.reply_text(
        f"Сколько порций «{text}»?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_QTY


async def order_choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    try:
        qty = int(text)
        if qty < 1 or qty > 20:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите количество от 1 до 20.")
        return ORDER_QTY

    context.user_data["current_qty"] = qty
    keyboard = [["С сахаром", "Без сахара"], ["❌ Отмена"]]

    await update.message.reply_text(
        "🍬 С сахаром или без?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_SUGAR


async def order_choose_sugar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    if text not in ["С сахаром", "Без сахара"]:
        await update.message.reply_text("Выберите вариант кнопкой.")
        return ORDER_SUGAR

    context.user_data["cart"].append({
        "name": context.user_data["current_coffee"],
        "qty": context.user_data["current_qty"],
        "sugar": text
    })

    keyboard = [["➕ Добавить ещё кофе"], ["➡️ Продолжить"], ["🧹 Очистить корзину"], ["❌ Отмена"]]
    summary, _ = order_summary(context.user_data)

    await update.message.reply_text(
        f"Добавлено.\n\nВаш заказ сейчас:\n{summary}\n\nЧто дальше?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_MORE_COFFEE


async def order_more_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "❌ Отмена":
        return await cancel(update, context)

    if text == "🧹 Очистить корзину":
        context.user_data["cart"] = []
        return await order_start(update, context)

    if text == "➕ Добавить ещё кофе":
        menu = load_menu()
        keyboard = [[name] for name in menu["coffee"].keys()]
        keyboard.append(["❌ Отмена"])

        await update.message.reply_text(
            "☕ Выберите кофе:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ORDER_COFFEE

    if text == "➡️ Продолжить":
        if not context.user_data.get("cart"):
            await update.message.reply_text("Корзина пустая. Сначала выберите кофе.")
            return ORDER_MORE_COFFEE

        keyboard = [["0", "1", "2"], ["3", "4", "5"], ["❌ Отмена"]]
        await update.message.reply_text(
            "🌭 Сколько френчдогов добавить? Если не нужно — нажмите 0.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ORDER_DOG

    await update.message.reply_text("Выберите вариант кнопкой.")
    return ORDER_MORE_COFFEE


async def order_choose_dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    try:
        qty = int(text)
        if qty < 0 or qty > 20:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите количество от 0 до 20.")
        return ORDER_DOG

    context.user_data["dog_qty"] = qty

    phone_button = KeyboardButton("📱 Отправить номер", request_contact=True)
    keyboard = [[phone_button], ["❌ Отмена"]]

    await update.message.reply_text(
        "📱 Укажите номер телефона:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_PHONE


async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()

    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7:
        await update.message.reply_text("Похоже, номер слишком короткий. Введите номер ещё раз.")
        return ORDER_PHONE

    context.user_data["phone"] = phone

    keyboard = [["Без комментария"], ["❌ Отмена"]]
    await update.message.reply_text(
        "💬 Комментарий к заказу:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_COMMENT


async def order_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    context.user_data["comment"] = "Нет" if text == "Без комментария" else text

    locations = load_locations()
    keyboard = [[loc] for loc in locations]
    keyboard.append(["❌ Отмена"])

    await update.message.reply_text(
        "📍 Куда доставить?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_LOCATION


async def order_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)

    locations = load_locations()
    if text not in locations:
        await update.message.reply_text("Выберите локацию кнопкой.")
        return ORDER_LOCATION

    context.user_data["location"] = text
    summary, total = order_summary(context.user_data)

    keyboard = [["✅ Подтвердить заказ"], ["↩️ Изменить локацию"], ["❌ Отмена"]]
    confirm_text = (
        "Проверьте заказ:\n\n"
        f"{summary}\n\n"
        f"📱 Телефон: {context.user_data['phone']}\n"
        f"💬 Комментарий: {context.user_data['comment']}\n"
        f"📍 Локация: {context.user_data['location']}"
    )

    await update.message.reply_text(
        confirm_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ORDER_CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "❌ Отмена":
        return await cancel(update, context)

    if text == "↩️ Изменить локацию":
        locations = load_locations()
        keyboard = [[loc] for loc in locations]
        keyboard.append(["❌ Отмена"])
        await update.message.reply_text(
            "📍 Выберите новую локацию:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ORDER_LOCATION

    if text != "✅ Подтвердить заказ":
        await update.message.reply_text("Нажмите кнопку подтверждения или отмены.")
        return ORDER_CONFIRM

    order_number = next_order_number()
    summary, total = order_summary(context.user_data)
    user = update.effective_user
    client = f"@{user.username}" if user.username else user.full_name
    time_now = datetime.now().strftime("%d.%m.%Y %H:%M")

    staff_text = (
        f"🔔 Новый заказ №{order_number:03d}\n\n"
        f"{summary}\n\n"
        f"📱 Телефон: {context.user_data['phone']}\n"
        f"💬 Комментарий: {context.user_data['comment']}\n"
        f"📍 Локация: {context.user_data['location']}\n"
        f"👤 Клиент: {client}\n"
        f"🕒 Время: {time_now}"
    )

    await context.bot.send_message(chat_id=STAFF_CHAT_ID, text=staff_text)

    await update.message.reply_text(
        f"✅ Ваш заказ №{order_number:03d} принят!\n\n💰 Итого: {money(total)} руб",
        reply_markup=main_keyboard(is_admin_user(update))
    )

    context.user_data.clear()
    return ConversationHandler.END


# ================== АДМИНКА ==================
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update):
        await update.message.reply_text("⛔ Нет доступа")
        return ConversationHandler.END

    keyboard = [["☕ Кофе"], ["🌭 Цена френчдога"], ["📍 Локации"], ["❌ Закрыть"]]

    await update.message.reply_text(
        "⚙️ Админка Aloha Coffee",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ADMIN_MENU


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "❌ Закрыть":
        context.user_data.clear()
        await update.message.reply_text(
            "Админка закрыта.",
            reply_markup=main_keyboard(is_admin_user(update))
        )
        return ConversationHandler.END

    if text == "☕ Кофе":
        menu = load_menu()
        coffee_text = "\n".join(
            f"• {name} — {money(price)} руб"
            for name, price in menu["coffee"].items()
        ) or "Кофе нет"

        keyboard = [["➕ Добавить кофе"], ["✏️ Изменить цену кофе"], ["🗑 Удалить кофе"], ["⬅️ Назад"]]
        await update.message.reply_text(
            f"☕ Кофе:\n\n{coffee_text}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_MENU

    if text == "🌭 Цена френчдога":
        await update.message.reply_text("Введите новую цену френчдога, например: 4.5")
        return ADMIN_FRENCHDOG_PRICE

    if text == "📍 Локации":
        locations = load_locations()
        loc_text = "\n".join(f"{i+1}. {loc}" for i, loc in enumerate(locations))
        keyboard = [["➕ Добавить локацию"], ["🗑 Удалить локацию"], ["⬅️ Назад"]]
        await update.message.reply_text(
            f"📍 Локации:\n\n{loc_text}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_MENU

    if text == "⬅️ Назад":
        return await admin_start(update, context)

    if text == "➕ Добавить кофе":
        await update.message.reply_text("Введите название нового кофе:")
        return ADMIN_ADD_COFFEE_NAME

    if text == "✏️ Изменить цену кофе":
        menu = load_menu()
        keyboard = [[name] for name in menu["coffee"].keys()]
        keyboard.append(["⬅️ Назад"])
        await update.message.reply_text(
            "Выберите кофе:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_EDIT_PRICE_NAME

    if text == "🗑 Удалить кофе":
        menu = load_menu()
        if len(menu["coffee"]) <= 1:
            await update.message.reply_text("Нельзя удалить последний кофе.")
            return ADMIN_MENU
        keyboard = [[name] for name in menu["coffee"].keys()]
        keyboard.append(["⬅️ Назад"])
        await update.message.reply_text(
            "Выберите кофе для удаления:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_DELETE_COFFEE_NAME

    if text == "➕ Добавить локацию":
        await update.message.reply_text("Введите новую локацию:")
        return ADMIN_ADD_LOCATION_NAME

    if text == "🗑 Удалить локацию":
        locations = load_locations()
        if len(locations) <= 1:
            await update.message.reply_text("Нельзя удалить последнюю локацию.")
            return ADMIN_MENU
        keyboard = [[loc] for loc in locations]
        keyboard.append(["⬅️ Назад"])
        await update.message.reply_text(
            "Выберите локацию для удаления:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ADMIN_DELETE_LOCATION_NAME

    await update.message.reply_text("Выберите действие кнопкой.")
    return ADMIN_MENU


async def admin_add_coffee_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or name == "⬅️ Назад":
        return await admin_start(update, context)

    menu = load_menu()
    if name in menu["coffee"]:
        await update.message.reply_text("Такой кофе уже есть. Введите другое название:")
        return ADMIN_ADD_COFFEE_NAME

    context.user_data["new_coffee_name"] = name
    await update.message.reply_text("Введите цену, например: 4 или 4.5")
    return ADMIN_ADD_COFFEE_PRICE


async def admin_add_coffee_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()

    try:
        price = float(text)
        if price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите цену числом, например: 4.5")
        return ADMIN_ADD_COFFEE_PRICE

    menu = load_menu()
    name = context.user_data["new_coffee_name"]
    menu["coffee"][name] = price
    save_menu(menu)

    await update.message.reply_text(f"✅ Добавлено: {name} — {money(price)} руб")
    return await admin_start(update, context)


async def admin_edit_price_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    if name == "⬅️ Назад":
        return await admin_start(update, context)

    menu = load_menu()
    if name not in menu["coffee"]:
        await update.message.reply_text("Выберите кофе кнопкой.")
        return ADMIN_EDIT_PRICE_NAME

    context.user_data["edit_coffee_name"] = name
    await update.message.reply_text(f"Введите новую цену для «{name}»:")
    return ADMIN_EDIT_PRICE_VALUE


async def admin_edit_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()

    try:
        price = float(text)
        if price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите цену числом, например: 4.5")
        return ADMIN_EDIT_PRICE_VALUE

    menu = load_menu()
    name = context.user_data["edit_coffee_name"]
    menu["coffee"][name] = price
    save_menu(menu)

    await update.message.reply_text(f"✅ Цена обновлена: {name} — {money(price)} руб")
    return await admin_start(update, context)


async def admin_delete_coffee_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    if name == "⬅️ Назад":
        return await admin_start(update, context)

    menu = load_menu()
    if name not in menu["coffee"]:
        await update.message.reply_text("Выберите кофе кнопкой.")
        return ADMIN_DELETE_COFFEE_NAME

    if len(menu["coffee"]) <= 1:
        await update.message.reply_text("Нельзя удалить последний кофе.")
        return await admin_start(update, context)

    del menu["coffee"][name]
    save_menu(menu)

    await update.message.reply_text(f"🗑 Удалено: {name}")
    return await admin_start(update, context)


async def admin_frenchdog_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()

    try:
        price = float(text)
        if price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите цену числом, например: 4.5")
        return ADMIN_FRENCHDOG_PRICE

    menu = load_menu()
    menu["frenchdog"] = price
    save_menu(menu)

    await update.message.reply_text(f"✅ Цена френчдога обновлена: {money(price)} руб")
    return await admin_start(update, context)


async def admin_add_location_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.text.strip()
    if loc == "⬅️ Назад":
        return await admin_start(update, context)

    locations = load_locations()
    if loc in locations:
        await update.message.reply_text("Такая локация уже есть.")
        return ADMIN_ADD_LOCATION_NAME

    locations.append(loc)
    save_locations(locations)

    await update.message.reply_text(f"✅ Локация добавлена: {loc}")
    return await admin_start(update, context)


async def admin_delete_location_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.text
    if loc == "⬅️ Назад":
        return await admin_start(update, context)

    locations = load_locations()
    if loc not in locations:
        await update.message.reply_text("Выберите локацию кнопкой.")
        return ADMIN_DELETE_LOCATION_NAME

    if len(locations) <= 1:
        await update.message.reply_text("Нельзя удалить последнюю локацию.")
        return await admin_start(update, context)

    locations.remove(loc)
    save_locations(locations)

    await update.message.reply_text(f"🗑 Локация удалена: {loc}")
    return await admin_start(update, context)


# ================== MAIN ==================
def main():
    ensure_files()
    app = Application.builder().token(TOKEN).build()

    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 Сделать заказ$"), order_start)],
        states={
            ORDER_COFFEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_choose_coffee)],
            ORDER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_choose_qty)],
            ORDER_SUGAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_choose_sugar)],
            ORDER_MORE_COFFEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_more_coffee)],
            ORDER_DOG: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_choose_dog)],
            ORDER_PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, order_phone)],
            ORDER_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_comment)],
            ORDER_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_location)],
            ORDER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⚙️ Админка$"), admin_start),
            CommandHandler("admin", admin_start),
            CommandHandler("settings", admin_start),
        ],
        states={
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)],
            ADMIN_ADD_COFFEE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_coffee_name)],
            ADMIN_ADD_COFFEE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_coffee_price)],
            ADMIN_EDIT_PRICE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_price_name)],
            ADMIN_EDIT_PRICE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_price_value)],
            ADMIN_DELETE_COFFEE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_coffee_name)],
            ADMIN_FRENCHDOG_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_frenchdog_price)],
            ADMIN_ADD_LOCATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_location_name)],
            ADMIN_DELETE_LOCATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_location_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(MessageHandler(filters.Regex("^📋 Меню$"), show_menu))
    app.add_handler(order_conv)
    app.add_handler(admin_conv)

    print("Aloha Coffee bot запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
