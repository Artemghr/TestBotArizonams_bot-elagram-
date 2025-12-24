#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WAITING_FOR_QUESTION, WAITING_FOR_ADMIN_RESPONSE = range(2)

CONFIG_FILE = 'config.json'
TICKETS_FILE = 'tickets.json'
FAQ_FILE = 'faq.json'
STATS_FILE = 'stats.json'

def load_config():
    default_config = {
        'bot_token': 'YOUR_BOT_TOKEN_HERE',
        'admin_ids': [],
        'faq_enabled': True,
        'auto_assign_tickets': True
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**default_config, **config}
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
    
    return default_config

CONFIG = load_config()

def load_json_file(filename: str, default: List = None) -> List:
    if default is None:
        default = []
    
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filename}: {e}")
            return default
    return default

def save_json_file(filename: str, data: List):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")
        return False

def init_database():
    if not os.path.exists(TICKETS_FILE):
        save_json_file(TICKETS_FILE, [])
        logger.info(f"Создан файл {TICKETS_FILE}")
    
    if not os.path.exists(FAQ_FILE):
        save_json_file(FAQ_FILE, [])
        logger.info(f"Создан файл {FAQ_FILE}")
        add_default_faq()
    else:
        faq_data = load_json_file(FAQ_FILE)
        if len(faq_data) == 0:
            add_default_faq()
    
    if not os.path.exists(STATS_FILE):
        save_json_file(STATS_FILE, [])
        logger.info(f"Создан файл {STATS_FILE}")

def add_default_faq():
    default_faq = [
        {
            "id": 1,
            "question": "Как связаться с поддержкой?",
            "answer": "Вы можете создать заявку через этого бота, написав /new или нажав кнопку 'Создать заявку'",
            "category": "general",
            "usage_count": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 2,
            "question": "Сколько времени занимает ответ?",
            "answer": "Обычно мы отвечаем в течение 1-2 рабочих часов. В нерабочее время ответ может занять до 24 часов.",
            "category": "general",
            "usage_count": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 3,
            "question": "Как отменить заявку?",
            "answer": "Напишите /cancel или используйте кнопку 'Отменить заявку' в меню",
            "category": "general",
            "usage_count": 0,
            "created_at": datetime.now().isoformat()
        },
        {
            "id": 4,
            "question": "Где посмотреть статус заявки?",
            "answer": "Используйте команду /my_tickets для просмотра всех ваших заявок",
            "category": "general",
            "usage_count": 0,
            "created_at": datetime.now().isoformat()
        }
    ]
    save_json_file(FAQ_FILE, default_faq)

def get_next_id(data: List) -> int:
    if not data:
        return 1
    return max(item.get('id', 0) for item in data) + 1

def create_ticket(user_id: int, username: str, first_name: str, question: str) -> int:
    tickets = load_json_file(TICKETS_FILE)
    
    ticket_id = get_next_id(tickets)
    ticket = {
        "id": ticket_id,
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "question": question,
        "status": "open",
        "admin_id": None,
        "admin_response": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    tickets.append(ticket)
    save_json_file(TICKETS_FILE, tickets)
    
    log_action(user_id, 'ticket_created', ticket_id)
    return ticket_id

def get_user_tickets(user_id: int) -> List[Dict]:
    tickets = load_json_file(TICKETS_FILE)
    user_tickets = [t for t in tickets if t.get('user_id') == user_id]
    user_tickets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return user_tickets

def get_all_tickets(status: Optional[str] = None) -> List[Dict]:
    tickets = load_json_file(TICKETS_FILE)
    
    if status:
        tickets = [t for t in tickets if t.get('status') == status]
    
    tickets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return tickets

def get_ticket_by_id(ticket_id: int) -> Optional[Dict]:
    tickets = load_json_file(TICKETS_FILE)
    for ticket in tickets:
        if ticket.get('id') == ticket_id:
            return ticket
    return None

def update_ticket_status(ticket_id: int, status: str, admin_id: Optional[int] = None, response: Optional[str] = None):
    tickets = load_json_file(TICKETS_FILE)
    
    for ticket in tickets:
        if ticket.get('id') == ticket_id:
            ticket['status'] = status
            ticket['updated_at'] = datetime.now().isoformat()
            if admin_id is not None:
                ticket['admin_id'] = admin_id
            if response is not None:
                ticket['admin_response'] = response
            break
    
    save_json_file(TICKETS_FILE, tickets)

def get_faq_items(category: Optional[str] = None) -> List[Dict]:
    faq_items = load_json_file(FAQ_FILE)
    
    if category:
        faq_items = [item for item in faq_items if item.get('category') == category]
    
    faq_items.sort(key=lambda x: x.get('usage_count', 0), reverse=True)
    return faq_items

def get_faq_by_id(faq_id: int) -> Optional[Dict]:
    faq_items = load_json_file(FAQ_FILE)
    for item in faq_items:
        if item.get('id') == faq_id:
            return item
    return None

def add_faq(question: str, answer: str, category: str = 'general') -> int:
    faq_items = load_json_file(FAQ_FILE)
    
    faq_id = get_next_id(faq_items)
    faq_item = {
        "id": faq_id,
        "question": question,
        "answer": answer,
        "category": category,
        "usage_count": 0,
        "created_at": datetime.now().isoformat()
    }
    
    faq_items.append(faq_item)
    save_json_file(FAQ_FILE, faq_items)
    
    return faq_id

def update_faq(faq_id: int, question: Optional[str] = None, answer: Optional[str] = None, category: Optional[str] = None):
    faq_items = load_json_file(FAQ_FILE)
    
    for item in faq_items:
        if item.get('id') == faq_id:
            if question is not None:
                item['question'] = question
            if answer is not None:
                item['answer'] = answer
            if category is not None:
                item['category'] = category
            save_json_file(FAQ_FILE, faq_items)
            return True
    
    return False

def delete_faq(faq_id: int) -> bool:
    faq_items = load_json_file(FAQ_FILE)
    
    original_len = len(faq_items)
    faq_items = [item for item in faq_items if item.get('id') != faq_id]
    
    if len(faq_items) < original_len:
        save_json_file(FAQ_FILE, faq_items)
        return True
    
    return False

def increment_faq_usage(faq_id: int):
    faq_items = load_json_file(FAQ_FILE)
    
    for item in faq_items:
        if item.get('id') == faq_id:
            item['usage_count'] = item.get('usage_count', 0) + 1
            break
    
    save_json_file(FAQ_FILE, faq_items)

def log_action(user_id: int, action: str, details: Optional[str] = None):
    stats = load_json_file(STATS_FILE)
    
    stat_entry = {
        "id": get_next_id(stats),
        "user_id": user_id,
        "action": f"{action}:{details}" if details else action,
        "timestamp": datetime.now().isoformat()
    }
    
    stats.append(stat_entry)
    save_json_file(STATS_FILE, stats)

def is_admin(user_id: int) -> bool:
    return user_id in CONFIG.get('admin_ids', [])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    welcome_text = f"""Добро пожаловать, {user.first_name}!

Я бот службы поддержки. Я могу помочь вам:
- Ответить на частые вопросы
- Создать заявку в службу поддержки
- Просмотреть статус ваших заявок

Используйте кнопки ниже или команды:
/new - Создать новую заявку
/faq - Часто задаваемые вопросы
/my_tickets - Мои заявки
/help - Справка
"""
    
    keyboard = [
        [KeyboardButton("Создать заявку"), KeyboardButton("FAQ")],
        [KeyboardButton("Мои заявки"), KeyboardButton("Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    log_action(user.id, 'start')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """Справка по использованию бота:

Основные команды:
/start - Главное меню
/new - Создать новую заявку
/faq - Часто задаваемые вопросы
/my_tickets - Просмотреть мои заявки
/cancel - Отменить текущее действие

Как создать заявку:
1. Нажмите "Создать заявку" или напишите /new
2. Опишите ваш вопрос или проблему
3. Дождитесь ответа от службы поддержки

FAQ:
Используйте раздел FAQ для быстрых ответов на популярные вопросы.

Для администраторов:
/admin - Панель администратора
"""
    
    await update.message.reply_text(help_text)
    log_action(update.effective_user.id, 'help')

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq_items = get_faq_items()
    
    if not faq_items:
        await update.message.reply_text("FAQ пока пуст.")
        return
    
    keyboard = []
    for item in faq_items[:10]:
        keyboard.append([InlineKeyboardButton(
            item['question'][:50] + ('...' if len(item['question']) > 50 else ''),
            callback_data=f"faq_{item['id']}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите вопрос из списка:",
        reply_markup=reply_markup
    )
    log_action(update.effective_user.id, 'faq_viewed')

async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("faq_helpful_"):
        faq_id = int(query.data.split('_')[2])
        await query.answer("Спасибо за обратную связь!")
        log_action(query.from_user.id, 'faq_helpful', faq_id)
        return
    
    elif query.data.startswith("faq_not_helpful_"):
        faq_id = int(query.data.split('_')[3])
        await query.answer("Создайте заявку, мы поможем!")
        log_action(query.from_user.id, 'faq_not_helpful', faq_id)
        await query.edit_message_text(
            "Пожалуйста, опишите ваш вопрос или проблему.\n\n"
            "Вы можете отменить создание заявки командой /cancel"
        )
        context.user_data['waiting_for_ticket'] = True
        return WAITING_FOR_QUESTION
    
    elif query.data == "create_ticket_from_faq":
        await query.edit_message_text(
            "Пожалуйста, опишите ваш вопрос или проблему.\n\n"
            "Вы можете отменить создание заявки командой /cancel"
        )
        context.user_data['waiting_for_ticket'] = True
        return ConversationHandler.END
    
    faq_id = int(query.data.split('_')[1])
    
    faq_item = get_faq_by_id(faq_id)
    
    if faq_item:
        increment_faq_usage(faq_id)
        answer_text = f"""Вопрос:
{faq_item['question']}

Ответ:
{faq_item['answer']}

---
Помог ли этот ответ? Если нет, создайте заявку через /new
"""
        keyboard = [[InlineKeyboardButton("Помогло", callback_data=f"faq_helpful_{faq_id}"),
                    InlineKeyboardButton("Не помогло", callback_data=f"faq_not_helpful_{faq_id}")],
                   [InlineKeyboardButton("Создать заявку", callback_data="create_ticket_from_faq")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(answer_text, reply_markup=reply_markup)
        log_action(query.from_user.id, 'faq_used', faq_id)
    else:
        await query.edit_message_text("FAQ не найден.")

async def new_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, опишите ваш вопрос или проблему.\n\n"
        "Вы можете отменить создание заявки командой /cancel"
    )
    return WAITING_FOR_QUESTION

async def new_ticket_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    question = update.message.text
    
    if len(question) < 10:
        await update.message.reply_text(
            "Вопрос слишком короткий. Пожалуйста, опишите проблему подробнее (минимум 10 символов)."
        )
        return WAITING_FOR_QUESTION
    
    ticket_id = create_ticket(
        user.id,
        user.username or "Unknown",
        user.first_name or "Unknown",
        question
    )
    
    await update.message.reply_text(
        f"Заявка #{ticket_id} успешно создана!\n\n"
        f"Ваш вопрос: {question}\n\n"
        f"Мы свяжемся с вами в ближайшее время. "
        f"Используйте /my_tickets для просмотра статуса заявки."
    )
    
    if CONFIG.get('admin_ids'):
        admin_message = f"""Новая заявка #{ticket_id}

Пользователь: {user.first_name} (@{user.username or 'без username'})
Вопрос: {question}

Используйте /admin для управления заявками.
"""
        for admin_id in CONFIG['admin_ids']:
            try:
                await context.bot.send_message(admin_id, admin_message)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('adding_faq', None)
    context.user_data.pop('faq_question', None)
    context.user_data.pop('faq_answer', None)
    context.user_data.pop('editing_faq_id', None)
    context.user_data.pop('editing_faq_type', None)
    context.user_data.pop('responding_to_ticket', None)
    context.user_data.pop('waiting_for_ticket', None)
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tickets = get_user_tickets(user.id)
    
    if not tickets:
        await update.message.reply_text("У вас пока нет заявок. Создайте новую через /new")
        return
    
    text = "Ваши заявки:\n\n"
    for ticket in tickets[:10]:
        status_text = {
            'open': 'Открыта',
            'in_progress': 'В работе',
            'closed': 'Закрыта',
            'cancelled': 'Отменена'
        }.get(ticket['status'], ticket['status'])
        
        created = datetime.fromisoformat(ticket['created_at']).strftime('%d.%m.%Y %H:%M')
        
        text += f"Заявка #{ticket['id']} - {status_text}\n"
        text += f"   Создана: {created}\n"
        text += f"   Вопрос: {ticket['question'][:50]}...\n"
        
        if ticket.get('admin_response'):
            text += f"   Ответ: {ticket['admin_response'][:50]}...\n"
        
        text += "\n"
    
    await update.message.reply_text(text)
    log_action(user.id, 'tickets_viewed')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("У вас нет доступа к панели администратора.")
        return
    
    open_tickets = get_all_tickets('open')
    in_progress_tickets = get_all_tickets('in_progress')
    all_tickets = get_all_tickets()
    
    text = f"""Панель администратора

Статистика:
- Всего заявок: {len(all_tickets)}
- Открытых: {len(open_tickets)}
- В работе: {len(in_progress_tickets)}
"""
    
    keyboard = [
        [InlineKeyboardButton("Все заявки", callback_data="admin_all_tickets"),
         InlineKeyboardButton("Открытые", callback_data="admin_open_tickets")],
        [InlineKeyboardButton("Статистика", callback_data="admin_stats"),
         InlineKeyboardButton("Управление FAQ", callback_data="admin_faq")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    log_action(user.id, 'admin_panel')

async def admin_faq_panel(query):
    faq_items = get_faq_items()
    
    text = f"""Управление FAQ

Всего вопросов: {len(faq_items)}
"""
    
    keyboard = [
        [InlineKeyboardButton("Список FAQ", callback_data="admin_faq_list")],
        [InlineKeyboardButton("Добавить FAQ", callback_data="admin_faq_add")],
        [InlineKeyboardButton("Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_faq_list(query):
    faq_items = get_faq_items()
    
    if not faq_items:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="admin_faq")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("FAQ пуст.", reply_markup=reply_markup)
        return
    
    text = f"Список FAQ ({len(faq_items)}):\n\n"
    keyboard = []
    
    for item in faq_items[:20]:
        text += f"#{item['id']} - {item['question'][:40]}...\n"
        keyboard.append([InlineKeyboardButton(
            f"#{item['id']} - {item['question'][:30]}...",
            callback_data=f"admin_faq_view_{item['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_faq")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_faq_view(query, faq_id):
    faq_item = get_faq_by_id(faq_id)
    
    if not faq_item:
        await query.edit_message_text("FAQ не найден.")
        return
    
    text = f"""FAQ #{faq_id}

Вопрос: {faq_item['question']}

Ответ: {faq_item['answer']}

Категория: {faq_item['category']}
Использований: {faq_item.get('usage_count', 0)}
"""
    
    keyboard = [
        [InlineKeyboardButton("Редактировать вопрос", callback_data=f"admin_faq_edit_question_{faq_id}")],
        [InlineKeyboardButton("Редактировать ответ", callback_data=f"admin_faq_edit_answer_{faq_id}")],
        [InlineKeyboardButton("Редактировать категорию", callback_data=f"admin_faq_edit_category_{faq_id}")],
        [InlineKeyboardButton("Удалить", callback_data=f"admin_faq_delete_{faq_id}")],
        [InlineKeyboardButton("Назад", callback_data="admin_faq_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_faq_add_start(query, context):
    context.user_data['adding_faq'] = True
    await query.edit_message_text(
        "Введите вопрос для нового FAQ:\n\n"
        "Используйте /cancel для отмены."
    )

async def admin_faq_edit_question_start(query, faq_id, context):
    context.user_data['editing_faq_id'] = faq_id
    context.user_data['editing_faq_type'] = 'question'
    await query.edit_message_text(
        f"Введите новый вопрос для FAQ #{faq_id}:\n\n"
        f"Используйте /cancel для отмены."
    )

async def admin_faq_edit_answer_start(query, faq_id, context):
    context.user_data['editing_faq_id'] = faq_id
    context.user_data['editing_faq_type'] = 'answer'
    await query.edit_message_text(
        f"Введите новый ответ для FAQ #{faq_id}:\n\n"
        f"Используйте /cancel для отмены."
    )

async def admin_faq_edit_category_start(query, faq_id, context):
    context.user_data['editing_faq_id'] = faq_id
    context.user_data['editing_faq_type'] = 'category'
    await query.edit_message_text(
        f"Введите новую категорию для FAQ #{faq_id}:\n\n"
        f"Используйте /cancel для отмены."
    )

async def admin_faq_delete(query, faq_id):
    if delete_faq(faq_id):
        await query.answer("FAQ удален!")
        await query.edit_message_text(f"FAQ #{faq_id} успешно удален.")
    else:
        await query.answer("Ошибка при удалении FAQ.")
        await query.edit_message_text("Ошибка при удалении FAQ.")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("У вас нет доступа.")
        return
    
    if query.data == "admin_back":
        open_tickets = get_all_tickets('open')
        in_progress_tickets = get_all_tickets('in_progress')
        all_tickets = get_all_tickets()
        
        text = f"""Панель администратора

Статистика:
- Всего заявок: {len(all_tickets)}
- Открытых: {len(open_tickets)}
- В работе: {len(in_progress_tickets)}
"""
        
        keyboard = [
            [InlineKeyboardButton("Все заявки", callback_data="admin_all_tickets"),
             InlineKeyboardButton("Открытые", callback_data="admin_open_tickets")],
            [InlineKeyboardButton("Статистика", callback_data="admin_stats"),
             InlineKeyboardButton("Управление FAQ", callback_data="admin_faq")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    elif query.data == "admin_all_tickets":
        tickets = get_all_tickets()
        await show_tickets_list(query, tickets, "Все заявки")
    
    elif query.data == "admin_open_tickets":
        tickets = get_all_tickets('open')
        await show_tickets_list(query, tickets, "Открытые заявки")
    
    elif query.data == "admin_stats":
        await show_admin_stats(query)
    
    elif query.data == "admin_faq":
        await admin_faq_panel(query)
    
    elif query.data == "admin_faq_list":
        await admin_faq_list(query)
    
    elif query.data == "admin_faq_add":
        await admin_faq_add_start(query, context)
    
    elif query.data.startswith("admin_faq_view_"):
        faq_id = int(query.data.split('_')[3])
        await admin_faq_view(query, faq_id)
    
    elif query.data.startswith("admin_faq_edit_question_"):
        faq_id = int(query.data.split('_')[4])
        await admin_faq_edit_question_start(query, faq_id, context)
    
    elif query.data.startswith("admin_faq_edit_answer_"):
        faq_id = int(query.data.split('_')[4])
        await admin_faq_edit_answer_start(query, faq_id, context)
    
    elif query.data.startswith("admin_faq_edit_category_"):
        faq_id = int(query.data.split('_')[4])
        await admin_faq_edit_category_start(query, faq_id, context)
    
    elif query.data.startswith("admin_faq_delete_"):
        faq_id = int(query.data.split('_')[3])
        await admin_faq_delete(query, faq_id)
    
    elif query.data.startswith("ticket_") and not query.data.startswith("ticket_action_"):
        ticket_id = int(query.data.split("_")[1])
        await show_ticket_details(query, ticket_id)
    
    elif query.data.startswith("ticket_action_"):
        parts = query.data.split("_")
        ticket_id = int(parts[2])
        action = parts[3]
        await handle_ticket_action(query, ticket_id, action, context)

async def show_tickets_list(query, tickets, title):
    if not tickets:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"{title} отсутствуют.", reply_markup=reply_markup)
        return
    
    text = f"{title} ({len(tickets)}):\n\n"
    keyboard = []
    
    for ticket in tickets[:20]:
        text += f"#{ticket['id']} - {ticket['question'][:40]}...\n"
        keyboard.append([InlineKeyboardButton(
            f"#{ticket['id']} - {ticket['question'][:30]}...",
            callback_data=f"ticket_{ticket['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_ticket_details(query, ticket_id):
    ticket = get_ticket_by_id(ticket_id)
    
    if not ticket:
        await query.edit_message_text("Заявка не найдена.")
        return
    
    status_text = {
        'open': 'Открыта',
        'in_progress': 'В работе',
        'closed': 'Закрыта',
        'cancelled': 'Отменена'
    }.get(ticket['status'], ticket['status'])
    
    created = datetime.fromisoformat(ticket['created_at']).strftime('%d.%m.%Y %H:%M')
    updated = datetime.fromisoformat(ticket['updated_at']).strftime('%d.%m.%Y %H:%M')
    
    text = f"""Заявка #{ticket['id']}

{status_text}
Пользователь: {ticket['first_name']} (@{ticket['username']})
ID: {ticket['user_id']}
Создана: {created}
Обновлена: {updated}

Вопрос:
{ticket['question']}
"""
    
    if ticket.get('admin_response'):
        text += f"\nОтвет:\n{ticket['admin_response']}"
    
    keyboard = []
    if ticket['status'] == 'open':
        keyboard.append([InlineKeyboardButton("Взять в работу", callback_data=f"ticket_action_{ticket_id}_in_progress")])
    if ticket['status'] != 'closed':
        keyboard.append([InlineKeyboardButton("Закрыть", callback_data=f"ticket_action_{ticket_id}_close")])
    keyboard.append([InlineKeyboardButton("Ответить", callback_data=f"ticket_action_{ticket_id}_respond")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_open_tickets")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def handle_ticket_action(query, ticket_id, action, context: ContextTypes.DEFAULT_TYPE):
    if action == "in_progress":
        update_ticket_status(ticket_id, 'in_progress', query.from_user.id)
        await query.answer("Заявка взята в работу")
        await show_ticket_details(query, ticket_id)
    
    elif action == "close":
        update_ticket_status(ticket_id, 'closed', query.from_user.id)
        await query.answer("Заявка закрыта")
        
        ticket = get_ticket_by_id(ticket_id)
        
        if ticket:
            try:
                await query.bot.send_message(
                    ticket['user_id'],
                    f"Ваша заявка #{ticket_id} была закрыта администратором."
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
        
        await show_ticket_details(query, ticket_id)
    
    elif action == "respond":
        await query.edit_message_text(
            f"Введите ответ на заявку #{ticket_id} в формате:\n\n"
            f"ответ #{ticket_id} ваш текст ответа\n\n"
            f"Или используйте команду /cancel для отмены."
        )
        context.user_data['responding_to_ticket'] = ticket_id

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if context.user_data.get('waiting_for_ticket'):
        context.user_data['waiting_for_ticket'] = False
        user = update.effective_user
        question = text
        
        if len(question) < 10:
            await update.message.reply_text(
                "Вопрос слишком короткий. Пожалуйста, опишите проблему подробнее (минимум 10 символов)."
            )
            context.user_data['waiting_for_ticket'] = True
            return
        
        ticket_id = create_ticket(
            user.id,
            user.username or "Unknown",
            user.first_name or "Unknown",
            question
        )
        
        await update.message.reply_text(
            f"Заявка #{ticket_id} успешно создана!\n\n"
            f"Ваш вопрос: {question}\n\n"
            f"Мы свяжемся с вами в ближайшее время. "
            f"Используйте /my_tickets для просмотра статуса заявки."
        )
        
        if CONFIG.get('admin_ids'):
            admin_message = f"""Новая заявка #{ticket_id}

Пользователь: {user.first_name} (@{user.username or 'без username'})
Вопрос: {question}

Используйте /admin для управления заявками.
"""
            for admin_id in CONFIG['admin_ids']:
                try:
                    await context.bot.send_message(admin_id, admin_message)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        return
    
    if text == "Создать заявку":
        await new_ticket_start(update, context)
        return WAITING_FOR_QUESTION
    
    elif text == "FAQ":
        await faq_command(update, context)
    
    elif text == "Мои заявки":
        await my_tickets(update, context)
    
    elif text == "Помощь":
        await help_command(update, context)
    
    elif is_admin(update.effective_user.id):
        if context.user_data.get('adding_faq'):
            if 'faq_question' not in context.user_data:
                question = text
                context.user_data['faq_question'] = question
                await update.message.reply_text(
                    "Введите ответ на вопрос:\n\n"
                    "Используйте /cancel для отмены."
                )
                return
            elif 'faq_answer' not in context.user_data:
                answer = text
                context.user_data['faq_answer'] = answer
                await update.message.reply_text(
                    "Введите категорию (или отправьте 'general' для категории по умолчанию):\n\n"
                    "Используйте /cancel для отмены."
                )
                return
            else:
                category = text.strip() or 'general'
                question = context.user_data.get('faq_question')
                answer = context.user_data.get('faq_answer')
                
                if question and answer:
                    faq_id = add_faq(question, answer, category)
                    await update.message.reply_text(f"FAQ #{faq_id} успешно добавлен!")
                else:
                    await update.message.reply_text("Ошибка при добавлении FAQ.")
                
                context.user_data.pop('adding_faq', None)
                context.user_data.pop('faq_question', None)
                context.user_data.pop('faq_answer', None)
                return
        
        if 'editing_faq_id' in context.user_data and 'editing_faq_type' in context.user_data:
            faq_id = context.user_data['editing_faq_id']
            edit_type = context.user_data['editing_faq_type']
            
            if edit_type == 'question':
                if update_faq(faq_id, question=text):
                    await update.message.reply_text(f"Вопрос FAQ #{faq_id} обновлен!")
                else:
                    await update.message.reply_text("Ошибка при обновлении вопроса.")
            elif edit_type == 'answer':
                if update_faq(faq_id, answer=text):
                    await update.message.reply_text(f"Ответ FAQ #{faq_id} обновлен!")
                else:
                    await update.message.reply_text("Ошибка при обновлении ответа.")
            elif edit_type == 'category':
                category = text.strip() or 'general'
                if update_faq(faq_id, category=category):
                    await update.message.reply_text(f"Категория FAQ #{faq_id} обновлена!")
                else:
                    await update.message.reply_text("Ошибка при обновлении категории.")
            
            context.user_data.pop('editing_faq_id', None)
            context.user_data.pop('editing_faq_type', None)
            return
        
        if 'responding_to_ticket' in context.user_data:
            ticket_id = context.user_data['responding_to_ticket']
            response_text = text
            del context.user_data['responding_to_ticket']
            
            ticket = get_ticket_by_id(ticket_id)
            
            if ticket:
                update_ticket_status(ticket_id, 'closed', update.effective_user.id, response_text)
                
                try:
                    await context.bot.send_message(
                        ticket['user_id'],
                        f"Ответ на вашу заявку #{ticket_id}:\n\n{response_text}"
                    )
                    await update.message.reply_text(f"Ответ отправлен пользователю.")
                except Exception as e:
                    await update.message.reply_text(f"Ошибка отправки: {e}")
            else:
                await update.message.reply_text("Заявка не найдена.")
            return
        
        elif text.startswith("ответ #") or text.lower().startswith("ответ #"):
            try:
                parts = text.split("#", 1)
                if len(parts) == 2:
                    ticket_id = int(parts[1].strip().split()[0])
                    response_text = parts[1].strip().split(maxsplit=1)[1] if len(parts[1].strip().split()) > 1 else "Ответ получен"
                    
                    ticket = get_ticket_by_id(ticket_id)
                    
                    if ticket:
                        update_ticket_status(ticket_id, 'closed', update.effective_user.id, response_text)
                        
                        try:
                            await context.bot.send_message(
                                ticket['user_id'],
                                f"Ответ на вашу заявку #{ticket_id}:\n\n{response_text}"
                            )
                            await update.message.reply_text(f"Ответ отправлен пользователю.")
                        except Exception as e:
                            await update.message.reply_text(f"Ошибка отправки: {e}")
                    else:
                        await update.message.reply_text("Заявка не найдена.")
            except Exception as e:
                await update.message.reply_text(f"Ошибка: {e}")

async def show_admin_stats(query):
    tickets = get_all_tickets()
    total_tickets = len(tickets)
    open_tickets = len([t for t in tickets if t.get('status') == 'open'])
    closed_tickets = len([t for t in tickets if t.get('status') == 'closed'])
    
    stats = load_json_file(STATS_FILE)
    created_count = len([s for s in stats if 'ticket_created' in s.get('action', '')])
    
    faq_items = get_faq_items()
    faq_count = len(faq_items)
    
    text = f"""Статистика бота

Заявки:
- Всего: {total_tickets}
- Открытых: {open_tickets}
- Закрытых: {closed_tickets}

FAQ:
- Всего вопросов: {faq_count}

Активность:
- Создано заявок: {created_count}
"""
    
    keyboard = [[InlineKeyboardButton("Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

def main():
    init_database()
    
    if CONFIG['bot_token'] == 'YOUR_BOT_TOKEN_HERE':
        logger.error("Установите токен бота в config.json!")
        return
    
    try:
        application = Application.builder().token(CONFIG['bot_token']).build()
    except Exception as e:
        logger.error(f"Ошибка создания приложения: {e}")
        logger.error("Попробуйте обновить python-telegram-bot: pip install --upgrade python-telegram-bot")
        return
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(CommandHandler("my_tickets", my_tickets))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    ticket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("new", new_ticket_start),
            MessageHandler(filters.Regex("^Создать заявку$"), new_ticket_start)
        ],
        states={
            WAITING_FOR_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_ticket_receive)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(ticket_conv)
    
    application.add_handler(CallbackQueryHandler(faq_callback, pattern="^(faq_|create_ticket_from_faq)"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|ticket_)"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
