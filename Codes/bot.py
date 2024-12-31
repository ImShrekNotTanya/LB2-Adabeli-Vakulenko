from flask import Flask, request
import requests
from dotenv import load_dotenv
import os
from os.path import join, dirname
from yookassa import Configuration, Payment
import json
import logging
import sqlite3
from datetime import datetime

app = Flask(__name__)


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            message TEXT,
            chat_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def log_to_db(command, message, chat_id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (command, message, chat_id) VALUES (?, ?, ?)
    ''', (command, message, chat_id))
    conn.commit()
    conn.close()


def create_invoice(chat_id):
    Configuration.account_id = get_from_env("SHOP_ID")
    Configuration.secret_key = get_from_env("PAYMENT_TOKEN")

    payment = Payment.create({
        "amount": {
            "value": "100.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://www.google.com"  # Замените на ваш URL
        },
        "capture": True,
        "description": "Заказ №1",
        "metadata": {"chat_id": chat_id}
    })

    return payment.confirmation.confirmation_url


def get_from_env(key):
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    return os.environ.get(key)


def send_message(chat_id, text):
    method = "sendMessage"
    token = get_from_env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)


def send_pay_button(chat_id, text):
    invoice_url = create_invoice(chat_id)

    method = "sendMessage"
    token = get_from_env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"

    data = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": json.dumps({
            "inline_keyboard": [[{
                "text": "Потратить денюшки немедленно!",
                "url": f"{invoice_url}"
            }]]
        })
    }

    requests.post(url, data=data)


def check_if_successful_payment(request):
    try:
        if request.json["event"] == "payment.succeeded":
            return True
    except KeyError:
        return False

    return False


def send_main_menu(chat_id):
    method = "sendMessage"
    token = get_from_env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"

    data = {
        "chat_id": chat_id,
        "text": "Выберите действие:",
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [
                    {"text": "Оплатить", "callback_data": "pay"},
                    {"text": "Информация", "callback_data": "info"}
                ],
                [
                    {"text": "Помощь", "callback_data": "help"},
                    {"text": "Посмотреть статистику", "callback_data": "stats"}
                ]
            ]
        })
    }

    requests.post(url, data=data)


def get_user_stats(chat_id):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT command, timestamp, message FROM logs WHERE chat_id = ? ORDER BY timestamp DESC
    ''', (chat_id,))

    rows = cursor.fetchall()

    stats_message = "Ваша статистика:\n"

    if not rows:stats_message += "Нет данных."
    else:
        for row in rows:
            stats_message += f"Команда: {row[0]}, Время: {row[1]}, Сообщение: {row[2]}\n"

    conn.close()  # Не забываем закрыть соединение
    return stats_message  # Возвращаем сообщение со статистикой


# Функция для обработки входящих сообщений от пользователей
def handle_user_message(chat_id, user_message):
    command = 'user_message'  # Здесь можно задать команду в зависимости от вашей логики
    log_to_db(command, user_message, chat_id)  # Логируем сообщение пользователя
    send_message(chat_id, f"Вы написали: {user_message}")  # Ответ пользователю


# Пример вызова функции для получения статистики
# stats_message = get_user_stats(chat_id)
# send_message(chat_id, stats_message)


@app.route('/', methods=["GET", "POST"])
def process():
    if request.method == 'POST':
        print("Received POST request")
        print("Request JSON:", request.json)

        try:
            if "callback_query" in request.json:
                callback_query = request.json["callback_query"]
                chat_id = callback_query["message"]["chat"]["id"]
                data = callback_query["data"]

                log_to_db(data, f"Кнопка нажата: {data}", chat_id)

                if data == "pay":
                    send_pay_button(chat_id, "Вы выбрали оплату.")
                elif data == "info":
                    send_message(chat_id, "Информация о нашем сервисе...")
                elif data == "help":
                    send_message(chat_id, "Как мы можем помочь вам?")
                elif data == "stats":
                    stats_message = get_user_stats(chat_id)
                    send_message(chat_id, stats_message)

                return {"ok": True}

            # Проверяем, если это успешная оплата
            if check_if_successful_payment(request):
                chat_id = request.json["object"]["metadata"]["chat_id"]
                send_message(chat_id, "Оплата прошла успешно")
                log_to_db("payment.succeeded", f"Оплата успешна для чата {chat_id}", chat_id)
            else:
                # Обработка текстового сообщения от пользователя
                if "message" in request.json:
                    message = request.json["message"]
                    chat_id = message["chat"]["id"]
                    user_message = message.get("text", "")  # Получаем текст сообщения

                    # Логируем сообщение пользователя
                    handle_user_message(chat_id, user_message)

                send_main_menu(chat_id=chat_id)

            return {"ok": True}
        except Exception as e:
            print("Error processing POST request:", e)
            return {"error": str(e)}, 500
    else:
        return "This is a GET request to the root endpoint"

if __name__ == '__main__':
    init_db()  # Инициализируем базу данных при запуске приложения
    logging.basicConfig(level=logging.INFO)
    app.run()