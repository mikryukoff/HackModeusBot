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
schedule_parser = None


# Команда "/start"
@dp.message(Command(commands=["start"]))
async def process_start_command(message: Message):
    await message.answer("Привет!\nМеня зовут ScheduleBot!\nЯ могу отправить расписание!")
    await message.answer("Для работы со мной, введите, пожалуйста, ваше ФИО\nНапример: Иванов Иван Иванович")


# Меню "Расписание"
@dp.message(F.text == "📅 Расписание")
async def send_schedule(message: Message):
    msg = await message.answer("Обрабатываю запрос...")
    global schedule_parser

    try:
        schedule_parser.save_week_schedule()
    except ScheduleException:
        sleep(1)

    schedule = get_schedule_text()

    await msg.edit_text(schedule[0])
    del schedule[0]

    for text in schedule:
        await message.answer(text)


# Команда "/schedule"
@dp.message(Command(commands=["schedule"]))
async def process_help_command(message: Message):
    msg = await message.answer("Обрабатываю запрос...")
    try:
        schedule_parser.save_week_schedule()
    except ScheduleException:
        sleep(1)

    await msg.edit_text("Высылаю Вам расписание!")

    for text in get_schedule_text():
        await message.answer(text)


# Авторизация по ФИО
@dp.message()
async def autorization(message: Message):
    global schedule_parser

    if not re.fullmatch(r"[А-ЯЁа-яё]+/s[А-ЯЁа-яё]+/s[А-ЯЁа-яё]+", message.text):
        '''
        Вспоминается сразу известное некогда имя БОЧ рВФ 260602
        (Биологический Объект Человек рода Ворониных-Пархоменко, родившийся 26.06.2002 года).
        - Алексей Шиманский Commented7 июл. 2017 в 6:33
        '''
        pass

    if len(message.text.split()) != 3 or len(message.text) > 100 or any(map(lambda x: x in string.ascii_letters, message.text)):
        await message.answer("Некорректное ФИО!")

    elif schedule_parser:
        await message.answer(f"Вы уже подключены под именем: {schedule_parser.user_name}")

    else:
        await message.answer("Подключаю ваше расписание...")
        if not schedule_parser:
            schedule_parser = ScheduleParser(message.text)
        await message.answer("Подключение прошло успешно!", reply_markup=kb.StartMenu)


def get_schedule_text() -> list:
    with open("schedule.json", mode="rb") as json_file:
        schedule = json.load(json_file)
        schedule = schedule[schedule_parser.user_name]

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
