import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NoneEnvVarsError

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='homework.log',
    filemode='w',
    level=logging.INFO,
    encoding='utf-8'
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
    error_tokens = []
    for name, token in env_vars.items():
        if token is None:
            error_tokens.append(name)
            logging.critical(f'Отсутствует переменная окружения "{name}"')
    if len(error_tokens) != 0:
        message = ('Программа остановлена. Отсутствуют переменные окружения: '
                   f'{", ".join(token for token in error_tokens)}')
        raise NoneEnvVarsError(message)


def send_message(bot, message):
    """Отправка статуса домашней работы пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения: "{error}".')
    logging.debug(f'Удачная отправка сообщения: "{message}"')


def get_api_answer(timestamp):
    """Получение ответа от сервера."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
        if response.status_code != HTTPStatus.OK:
            message = (f'Проблема с эндпоинтом "{ENDPOINT}". '
                       f'Код ответа API: {response.status_code}')
            logging.error(message)
            raise requests.RequestException(message)
    except Exception as error:
        message = (f'Ошибка соединения с сервером: {error}')
        logging.error(message)
        raise Exception(message)
    return response.json()


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
    timestamp = 1677517018
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    old_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug('Домашнюю работу ещё не начали проверять.')
                time.sleep(RETRY_PERIOD)
                continue
            new_message = parse_status(homeworks[0])
        except Exception as error:
            new_message = f'Сбой в работе программы: {error}'
        if old_message != new_message:
            old_message = new_message
            send_message(bot, new_message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
