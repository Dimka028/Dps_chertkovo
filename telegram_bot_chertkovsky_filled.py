"""
Этот файл представляет собой скрипт телеграм‑бота, аналогичный оригинальному
`telegram_bot_chertkovsky.py`, но с уже заполненными переменными BOT_TOKEN и
CHANNEL_ID. Скрипт публикует дорожные сообщения в заданный канал, сохраняя
анонимность пользователей.

Внимание: данный файл содержит рабочий токен и идентификатор канала.
Используйте его только в закрытой среде и не размещайте в публичных
репозиториях, чтобы не допустить компрометации данных.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import requests

# Конкретные параметры бота. Значения получены от пользователя и не
# должны публиковаться в открытом доступе.
BOT_TOKEN: str = "8537531623:AAHGfKEq1F_JBY7VZGivAYFgRpdVxf0qGWA"
CHANNEL_ID: str | int = "8142424816"

# Базовый URL для API
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_updates(offset: int | None = None, timeout: int = 30) -> Dict[str, Any]:
    """Получает новые обновления от Telegram с использованием метода getUpdates.

    Args:
        offset: Смещение для следующего запроса (последний обработанный
            `update_id` + 1).
        timeout: Тайм‑аут long polling в секундах.

    Returns:
        JSON‑ответ Telegram API.
    """
    params: Dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    response = requests.get(f"{API_URL}/getUpdates", params=params, timeout=timeout + 5)
    response.raise_for_status()
    return response.json()


def send_message(text: str) -> None:
    """Отправляет текстовое сообщение в заданный канал.

    Args:
        text: Текст сообщения для отправки.
    """
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    response = requests.post(f"{API_URL}/sendMessage", data=payload)
    try:
        response.raise_for_status()
    except Exception as exc:
        print(f"Не удалось отправить сообщение: {exc}\nОтвет: {response.text}")


def build_forward_text(message: Dict[str, Any]) -> str:
    """Формирует текст для публикации на основе исходного сообщения.

    Args:
        message: Объект `message` из Telegram update.

    Returns:
        Сформированный текст для отправки в канал.
    """
    parts: list[str] = []
    text = message.get("text") or message.get("caption")
    if text:
        parts.append(f"<b>Сообщение:</b> {text}")
    location = message.get("location")
    if location:
        lat = location.get("latitude")
        lon = location.get("longitude")
        parts.append(f"<b>Местоположение:</b> {lat}, {lon}")
    if not parts:
        parts.append("(пустое сообщение)")
    return "\n".join(parts)


def main() -> None:
    """Запускает бота и непрерывно обрабатывает входящие сообщения."""
    print("Запуск бота с заданными токеном и каналом. Нажмите Ctrl+C для остановки.")
    offset: int | None = None
    while True:
        try:
            updates = get_updates(offset=offset)
        except Exception as exc:
            print(f"Ошибка при получении обновлений: {exc}. Повтор через 5 секунд.")
            time.sleep(5)
            continue
        if not updates.get("ok", False):
            print(f"Telegram API вернул ошибку: {updates}")
            time.sleep(5)
            continue
        for update in updates.get("result", []):
            update_id = update.get("update_id")
            message: Dict[str, Any] = update.get("message", {})
            if not message:
                offset = update_id + 1 if update_id is not None else None
                continue
            forward_text = build_forward_text(message)
            send_message(forward_text)
            chat_id = message.get("chat", {}).get("id")
            if chat_id is not None:
                confirm_payload = {
                    "chat_id": chat_id,
                    "text": "Спасибо! Ваше сообщение отправлено анонимно.",
                }
                requests.post(f"{API_URL}/sendMessage", data=confirm_payload)
            if update_id is not None:
                offset = update_id + 1
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")