import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import InitBotError, NoneEnvVarsError, StatusCodeIsNot200Error

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        logging.FileHandler(
            filename=os.path.expanduser('~/homework.log'),
            mode='w',
            encoding='utf-8')
    ]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка токенов на доступность."""
    env_vars = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    error_tokens = [name for name, token in env_vars.items() if token is None]
    if len(error_tokens) != 0:
        message = ('Программа остановлена. Отсутствуют переменные окружения: '
                   f'"{", ".join(error_tokens)}"')
        logging.critical(message)
        raise NoneEnvVarsError(message)


def send_message(bot, message):
    """Отправка статуса домашней работы пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Удачная отправка сообщения: "{message}"')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения: "{error}".')


def get_api_answer(timestamp):
    """Получение ответа от сервера."""
    if not isinstance(timestamp, int):
        message = 'Передана дата не в формате Unix Timestamp'
        logging.error(message)
        raise TypeError(message)
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
        if response.status_code != HTTPStatus.OK:
            message = (f'Проблема с эндпоинтом "{ENDPOINT}". '
                       f'Код ответа API: {response.status_code}')
            logging.error(message)
            raise StatusCodeIsNot200Error(message)
    except requests.RequestException as error:
        message = (f'Ошибка соединения с сервером: {error}')
        logging.error(message)
        raise ConnectionError(message)
    try:
        response_json = response.json()
    except json.JSONDecodeError as error:
        message = f'Ошибка декодирования JSON: {error}'
        logging.error(message)
        raise json.JSONDecodeError(message)
    code = response_json.get('code')
    error = response_json.get('error')
    if code or error:
        message = (f'Отказ сервера. Детали запроса: '
                   f'Code: {code}, Error: {error}')
        logging.error(message)
        raise Exception(message)
    return response_json


def check_response(response):
    """Проверка полученного ответа от сервера."""
    if type(response) != dict:
        message = 'Программа не получает cловарь в качестве ответа API'
        logging.error(message)
        raise TypeError(message)
    homeworks = response.get('homeworks')
    if homeworks is None:
        message = 'Отсутствие ожидаемого ключа "homeworks" в ответе API'
        logging.error(message)
        raise KeyError(message)
    if type(homeworks) != list:
        message = 'Ключ ответа API "homeworks" не является списком'
        logging.error(message)
        raise TypeError(message)
    return homeworks


def parse_status(homework):
    """Проверяет статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        message = 'Нет ключа "homework_name" в ответе API'
        logging.error(message)
        raise KeyError(message)
    status = homework['status']
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        message = f'Неожиданный статус домашней работы: {status}'
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = 1681635226
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not bot:
        message = 'Ошибка инициализации бота'
        logging.error(message)
        raise InitBotError(message)
    old_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug('Домашнюю работу ещё не начали проверять.')
                continue
            timestamp = response['current_date']
            new_message = parse_status(homeworks[0])
            if old_message != new_message:
                old_message = new_message
                send_message(bot, new_message)
        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
            if old_message != new_message:
                old_message = new_message
                send_message(bot, new_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
