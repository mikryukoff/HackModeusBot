from config import BOT_TOKEN
from ScheduleParser import ScheduleParser, ScheduleException
import keyboards as kb

from time import sleep
import json
import re
import string

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

users_chat_id: dict = {}


# Команда "/start"
@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
    await message.answer("Привет!\nМеня зовут ScheduleBot!\nЯ могу отправить расписание!")
    await message.answer("Для работы со мной, введите, пожалуйста, ваше ФИО\nНапример: Иванов Иван Иванович")

    global users_chat_id
    users_chat_id.setdefault(message.chat.id, tuple())


# Меню "Расписание"
@dp.message(F.text == "📅 Расписание")
async def send_schedule(message: Message):
    global users_chat_id

    msg = await message.answer("Обрабатываю запрос...")
    current_user_name = users_chat_id[message.chat.id][0]

    try:
        users_chat_id[message.chat.id][1].save_week_schedule()
    except ScheduleException:
        sleep(1)

    schedule = get_schedule_text(current_user_name)

    await msg.edit_text(schedule[0])
    del schedule[0]

    for text in schedule:
        await message.answer(text)

    print(users_chat_id)


# Авторизация по ФИО
@dp.message()
async def autorization(message: Message):
    global users_chat_id

    if users_chat_id[message.chat.id]:
        await message.answer(f"Вы уже подключены под именем: {users_chat_id[message.chat.id][0]}")
        return

    if not re.fullmatch(r"[А-ЯЁа-яё]+/s[А-ЯЁа-яё]+/s[А-ЯЁа-яё]+", message.text):
        '''
        Вспоминается сразу известное некогда имя БОЧ рВФ 260602
        (Биологический Объект Человек рода Ворониных-Пархоменко, родившийся 26.06.2002 года).
        - Алексей Шиманский Commented7 июл. 2017 в 6:33
        '''
        pass

    if len(message.text.split()) != 3 or len(message.text) > 100 or any(map(lambda x: x in string.ascii_letters, message.text)):
        await message.answer("Некорректное ФИО!")
    else:
        await message.answer("Подключаю ваше расписание...")
        users_chat_id[message.chat.id] = (message.text, ScheduleParser(message.text))
        await message.answer("Подключение прошло успешно!", reply_markup=kb.StartMenu)


def get_schedule_text(current_user_name: str) -> list:
    with open("schedule.json", mode="rb") as json_file:
        schedule = json.load(json_file)
        schedule = schedule[current_user_name]

        schedule_iter = []

        for day in schedule:
            if not schedule[day]:
                continue

            text = f"{day}:\n\n"

            for time, lesson_name in schedule[day].items():
                if not lesson_name:
                    continue

                text += f"{time}:\n{lesson_name[0]}\n{lesson_name[1]}\n\n"

            schedule_iter.append(text)

    return schedule_iter


if __name__ == "__main__":
    dp.run_polling(bot)
