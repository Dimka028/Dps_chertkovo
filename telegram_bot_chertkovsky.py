"""
Телеграм‑бот для анонимной публикации сообщений о дорожных событиях в Чертковском районе.

Этот скрипт использует Telegram Bot API напрямую через библиотеку `requests`, поэтому
не требует установки дополнительных зависимостей. Бот работает в режиме long
polling: он регулярно запрашивает новые обновления и пересылает содержимое
сообщений в заданный канал или группу, не раскрывая личность автора. Если
пользователь отправил координаты, они включаются в публикуемое сообщение.

Перед запуском:
  * Создайте бота через [BotFather](https://core.telegram.org/bots#6-botfather),
    скопируйте API‑токен и сохраните его в переменную окружения `BOT_TOKEN` или
    пропишите в константе `BOT_TOKEN` ниже. Руководство GitHub по подобному
    боту подчёркивает, что для запуска требуется указать токен и идентификатор
    чата/канала, куда будут отправляться сообщения【135631679578986†L262-L301】.
  * Создайте канал или группу, куда будут публиковаться сообщения, и добавьте
    туда созданного бота. Не забудьте дать боту права администратора — иначе
    он не сможет отправлять сообщения; это требование подтверждается в
    обсуждении на Stack Overflow【63075315159324†L1066-L1072】.
  * Определите идентификатор канала. Для публичного канала можно использовать
    его алиас с префиксом `@`, например `@my_channel`. Если канал приватный,
    используйте отрицательное число (например `-1001234567890`) или алиас
    вида `@channelname`. Комментарий на Stack Overflow поясняет, что алиас
    можно получить из ссылки t.me/имя_канала, просто добавив `@` в начале
    【63075315159324†L1037-L1040】.

Чтобы получить код идентификатора приватного канала, вы можете отправить
сообщение в канал и запросить обновления у бота: идентификатор будет
виден в поле `chat.id` JSON‑ответа.

Сохраните файл и запустите:

```bash
export BOT_TOKEN="123456789:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
export CHANNEL_ID="@my_channel"  # или целочисленный ID канала
python telegram_bot_chertkovsky.py
```

Бот будет работать в фоновом режиме. При получении сообщения от
пользователя он сформирует текст, включающий присланный текст и
координаты, если они были отправлены. Затем бот отправит этот текст в
канал/группу от своего имени, тем самым сохраняется анонимность
пользователя (имя и фамилия не отображаются).

"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import requests


# Загрузка конфигурации из переменных окружения. При желании можно
# непосредственно указать токен и идентификатор канала здесь.
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID: str | int = os.environ.get("CHANNEL_ID", "YOUR_CHANNEL_ID_HERE")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_updates(offset: int | None = None, timeout: int = 30) -> Dict[str, Any]:
    """Получает новые обновления от Telegram с использованием метода getUpdates.

    Args:
        offset: Смещение для следующего запроса (последний обработанный
            `update_id` + 1). Это позволяет пропускать уже обработанные
            сообщения.
        timeout: Тайм‑аут long polling в секундах (по умолчанию 30 секунд).

    Returns:
        Словарь с ответом Telegram API, содержащий список обновлений.
    """
    params: Dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    response = requests.get(f"{API_URL}/getUpdates", params=params, timeout=timeout + 5)
    response.raise_for_status()
    return response.json()


def send_message(text: str) -> None:
    """Отправляет текстовое сообщение в заданный канал или группу.

    Args:
        text: Текст сообщения для отправки.
    """
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    # Используем метод sendMessage для отправки нового сообщения. В ответ
    # приходит JSON, но мы его не используем. Если чат недоступен или
    # бот не имеет прав администратора, запрос завершится ошибкой.
    response = requests.post(f"{API_URL}/sendMessage", data=payload)
    try:
        response.raise_for_status()
    except Exception as exc:
        print(f"Не удалось отправить сообщение: {exc}\nОтвет: {response.text}")


def build_forward_text(message: Dict[str, Any]) -> str:
    """Формирует текст для публикации на основе исходного сообщения.

    Мы намеренно не используем метод forwardMessage, потому что при
    перенаправлении Telegram отображает имя отправителя. Вместо этого
    создаём собственный текст. Если пользователь отправил геопозицию, мы
    добавляем координаты в текст, чтобы читатели канала понимали место
    происшествия.

    Args:
        message: Объект `message` из Telegram update.

    Returns:
        Сформированный текст для отправки в канал.
    """
    parts: list[str] = []
    # Текст сообщения
    text = message.get("text") or message.get("caption")
    if text:
        parts.append(f"<b>Сообщение:</b> {text}")
    # Координаты
    location = message.get("location")
    if location:
        lat = location.get("latitude")
        lon = location.get("longitude")
        parts.append(f"<b>Местоположение:</b> {lat}, {lon}")
    if not parts:
        # Если ни текста, ни локации нет, отправим уведомление о пустом сообщении
        parts.append("(пустое сообщение)")
    return "\n".join(parts)


def main() -> None:
    """Точка входа для запуска бота.

    Бот постоянно опрашивает API Telegram с помощью long polling. При
    обнаружении новых сообщений формирует текст и отправляет его в
    канал/группу. После обработки обновлений увеличивает смещение, чтобы
    не дублировать обработку.
    """
    # Проверяем наличие токена и идентификатора канала
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Не указан BOT_TOKEN. Задайте переменную окружения BOT_TOKEN или пропишите её в коде."
        )
    if not CHANNEL_ID or CHANNEL_ID == "YOUR_CHANNEL_ID_HERE":
        raise RuntimeError(
            "Не указан CHANNEL_ID. Задайте переменную окружения CHANNEL_ID или пропишите её в коде."
        )

    print("Запуск бота. Нажмите Ctrl+C для остановки.")
    offset: int | None = None
    while True:
        try:
            updates = get_updates(offset=offset)
        except Exception as exc:
            print(f"Ошибка при получении обновлений: {exc}. Перезапрос через 5 секунд.")
            time.sleep(5)
            continue
        # Если Telegram вернул ok=False, выводим сообщение и продолжаем
        if not updates.get("ok", False):
            print(f"Telegram API вернул ошибку: {updates}")
            time.sleep(5)
            continue
        for update in updates.get("result", []):
            update_id = update.get("update_id")
            message: Dict[str, Any] = update.get("message", {})
            if not message:
                # Игнорируем обновления без сообщения (например, service)
                offset = update_id + 1 if update_id is not None else None
                continue
            forward_text = build_forward_text(message)
            # Публикуем сообщение в канал
            send_message(forward_text)
            # Отправляем пользователю подтверждение (опционально)
            chat_id = message.get("chat", {}).get("id")
            if chat_id is not None:
                confirm_payload = {
                    "chat_id": chat_id,
                    "text": "Спасибо! Ваше сообщение отправлено анонимно.",
                }
                requests.post(f"{API_URL}/sendMessage", data=confirm_payload)
            # Увеличиваем offset, чтобы не обрабатывать это сообщение повторно
            if update_id is not None:
                offset = update_id + 1
        # Маленькая задержка, чтобы снизить нагрузку на API
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")