from config import USER_LOGIN, USER_PASS, USER_DATA_DIR, USER_BROWSER_PROFILE

import json
from datetime import datetime
from itertools import zip_longest
from dataclasses import dataclass
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ChromeOptions

import asyncio
from async_property import async_property

from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import SessionNotCreatedException

from bs4 import BeautifulSoup
import lxml

from fake_useragent import UserAgent


class NoSuchStudentFound(TimeoutException):
    def __str__(self):
        return f"Student: {self.msg} not found."


class AlreadyAuthorisedException(TimeoutException):
    def __str__(self):
        return "User is already authorised."


class NoDataException(Exception):
    text = "Нет данных."


class ScheduleException(Exception):
    pass


@dataclass
class ScheduleParser:

    # ФИО пользователя.
    user_name: str = None

    # ФИО пользователя, авторизовавшегося по логину и паролю.
    __page_user_name: str = None

    # Дата для получения расписания в определенный день.
    date: datetime = None

    # URL страницы с расписанием.
    url: str = 'https://urfu.modeus.org/schedule-calendar'

    # Логин и пароль, по которым идёт авторизация в Modeus.
    # Используются данные из файла config.py.
    __login: str = USER_LOGIN
    __password: str = USER_PASS

    @property
    def soup(self) -> BeautifulSoup:
        '''
        Принимает код страницы и возвращает объект BeautifulSoup.

        Параметры:
            page_source: str - код страницы.

        Возвращает:
            BeautifulSoup - объект BeautifulSoup.
        '''

        return BeautifulSoup(self.page_source, "lxml")

    @async_property
    async def next_week_schedule(self) -> None:
        '''
        Используется, если требуется получить расписание на следующую неделю.
        Вызывает метод ScheduleParser.save_week_schedule() с аргументом next_week=True.
        '''

        await self.week_schedule(next_week=True)

    @async_property
    async def week_schedule(self, next_week=False):
        '''
        BLANK
        '''
        if not self._check_saved_file():
            await self.save_week_schedule(next_week=next_week)

        with open("schedule.json", mode="rb") as json_file:
            schedule = json.load(json_file)
            schedule = schedule[self.user_name]

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

        self.browser.close()
        self.browser.quit()
        print(f"browser closed {self.user_name}")

        return schedule_iter

    async def save_week_schedule(self, next_week: bool = False) -> None:
        '''
        Сохраняет в файл schedule.json расписание на неделю,
        если расписание на эту неделю ранее не сохранялось, в формате:

            {
                ФИО:
                {
                    день недели:
                    {
                        время 1-ой пары: [название предмета, аудитория],
                        ...,
                        время n-ой пары: [название предмета, аудитория]
                    }
                }
            }

        Параметры:
            next_week: bool - определяет, на какую неделю сохранять расписание.
            Если True, сохраняет расписание на следующую неделю, False - на текущую.
        '''

        # Авторизируемся на сайте Modeus, если регистрации ещё не было.
        if not self.__page_user_name:
            await self.__authorisation()

        if next_week:
            await self._change_to_next_week()

        with open("schedule.json", mode="r", encoding="utf-8") as json_file:
            schedule = json.load(json_file)

        # Записываем в файл schedule.json расписание.
        with open("schedule.json", mode="w", encoding="utf-8") as json_file:
            week_days = self.week_days
            schedule_cols = self.soup.select(".fc-content-col")

            for day in week_days:
                day_schedule = self.get_day_schedule(day_num=week_days.index(day), schedule_cols=schedule_cols)
                schedule.setdefault(self.user_name, {}).setdefault(day, day_schedule)

            json.dump(schedule, json_file, ensure_ascii=False, indent=2)

    def get_day_schedule(self, schedule_cols: list, day_num: int) -> dict:
        '''
        По номеру дня недели возвращает полное расписание на день
        в виде словаря:

            {
                время 1-ой пары: (название предмета, аудитория),
                ...,
                время n-ой пары: (название предмета, аудитория)
            }

        Параметры:
            soup: BeautifulSoup - суп страницы с расписанием;
            day_num: int - номер дня недели (0 - пн., 1 - вт., ..., 6 - вс.).

        Возвращает:
            day_schedule: dict - словаря с расписанием на день (структура описана выше).
        '''

        # Колонка с расписанием на день.
        day_col = schedule_cols[day_num]

        subjects = day_col.select(".fc-title")
        classrooms = day_col.select("small")
        subjects_time = day_col.select(".fc-time span")

        # Если каких-то данных не достаёт, заполняем значением NoDataException,
        # то есть строкой "нет данных".
        day_schedule: dict = {}
        for subject, classroom, time in zip_longest(
            subjects, classrooms, subjects_time,
            fillvalue=NoDataException
        ):
            day_schedule.setdefault(time.text.zfill(13), (subject.text, classroom.text))

        return day_schedule

    @property
    def week_days(self) -> list:
        '''
        Возвращает список с названиями дней, указанных на странице.

        Принимает:
            soup: BeautifulSoup - суп страницы с расписанием.
        Возвращает:
            Список с названиями дней.
        '''

        return [day.text for day in self.soup.select(".fc-day-header span")]

    def load_cookies(self, webdriver: webdriver.Chrome) -> None:
        with open(file="cookies.json", mode="r", encoding="utf-8") as cookies_file:
            for cookie in json.load(cookies_file):
                webdriver.add_cookie(cookie)

    def save_cookies(self, webdriver: webdriver.Chrome) -> None:
        with open(file="cookies.json", mode="w", encoding="utf-8") as cookies_file:
            json.dump(webdriver.get_cookies(), cookies_file)

    @async_property
    async def driver(self):

        # -------------------- Настройки Chrome Webdriver -------------------- #

        options = ChromeOptions()

        # Путь к директории профиля браузера Chrome.
        options.add_argument(r"{USER_DATA_DIR}")

        # Запуск браузера в полноэкранном режиме.
        options.add_argument("--start-maximized")

        # Название директории профиля браузера Chrome.
        options.add_argument(f"--profile-directory={USER_BROWSER_PROFILE}")

        # ЗАПОЛНИТЬ
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Запуск браузера без графической оболочки.
        options.add_argument("--headless")

        # Отключение использования GPU.
        options.add_argument("--disable-gpu")

        options.add_argument("--no-sandbox")

        options.add_argument(f'--user-agent={UserAgent().random}')

        options.add_argument('--disable-dev-shm-usage')

        options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        # -------------------- Конец блока настроек Chrome Webdriver -------------------- #
        try:
            self.browser = webdriver.Chrome(options=options)
        except SessionNotCreatedException:
            sleep(1)
            self.browser = webdriver.Chrome(options=options)

        return self

    async def __authorisation(self) -> None:
        self.browser.get(self.url)

        try:
            WebDriverWait(self.browser, 10).until(
                EC.visibility_of_any_elements_located((By.ID, "userNameInput"))
            )

            self.browser.find_element(By.ID, "userNameInput").send_keys(self.__login)
            self.browser.find_element(By.ID, "passwordInput").send_keys(self.__password)
            self.browser.find_element(By.ID, "submitButton").click()
        except AlreadyAuthorisedException:
            pass

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ".fc-title"))
        )

        self.__page_user_name = self.browser.find_element(By.CSS_SELECTOR, ".user-name.user-full-name.user-visible-name").text

        if self.__page_user_name != self.user_name:
            self._change_user()

        self.page_source = self.browser.page_source

    def _change_user(self):
        self.browser.find_element(By.CSS_SELECTOR, ".btn-filter.screen-only").click()
        self.browser.find_element(By.CSS_SELECTOR, ".clear").click()
        self.browser.find_elements(By.CSS_SELECTOR, ".p-multiselected-empty.ng-star-inserted")[6].click()
        self.browser.find_element(By.XPATH, "//input[contains(@class,'p-inputtext p-widget')]").send_keys(self.user_name)

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.XPATH, f"//div[text()='{self.user_name}']"))
        )

        self.browser.find_element(By.XPATH, f"//div[text()='{self.user_name}']").click()
        self.browser.find_element(By.CSS_SELECTOR, ".btn.btn-apply").click()
        sleep(1)

    async def _change_to_next_week(self) -> None:
        self.browser.find_element(By.XPATH, "//span[@class='fc-icon fc-icon-right-single-arrow']").click()
        self.browser.refresh()

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".fc-title"))
        )

    def _check_saved_file(self) -> bool:
        try:
            with open("schedule.json", "r", encoding="utf-8") as json_file:
                schedule = json.load(json_file)
                if self.user_name in schedule:
                    return True
                return False
        except FileNotFoundError:
            with open("schedule.json", "w", encoding="utf-8") as json_file:
                json.dump(dict(), json_file, ensure_ascii=False, indent=2)
                return False

    def __save_user_data(self, login: str, password: str) -> None:
        pass

    def __str__(self):
        return f"ScheduleParser({self.user_name})"

    def __repr__(self):
        return f"ScheduleParser({self.user_name})"
