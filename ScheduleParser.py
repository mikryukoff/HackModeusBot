from config import USER_LOGIN, USER_PASS, USER_DATA_DIR

import json
from datetime import datetime
from itertools import zip_longest
from dataclasses import dataclass
# import hashlib

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ChromeOptions

from bs4 import BeautifulSoup
import lxml

from fake_useragent import UserAgent


class NoDataException(Exception):
    text = "Нет данных"


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

    # Логин и пароль, по которым идёт авторизация в Modeus.
    # Используются данные из файла config.py.
    __login: str = USER_LOGIN
    __password: str = USER_PASS

    def __post_init__(self) -> None:
        # self.params = {
        #     "calendar": f'%7B"view":"agendaWeek","date":"{date}"%7D',
        #     "timeZone": r"Asia%2FYekaterinburg",
        #     "grid": "Grid.07",
        #     "selectedEvent": ""
        # }

        # URL страницы с расписанием.
        self.url = 'https://urfu.modeus.org/schedule-calendar'

        # Заголовки запроса.
        self.headers = {
            "user-agent": UserAgent().random
            }

        # Путь к директории профиля браузера Chrome, берётся из config.py.
        profile_directory: str = USER_DATA_DIR.split("\\")[-1]

        # -------------------- Настройки Chrome Webdriver -------------------- #

        self.options = ChromeOptions()

        # Путь к директории профиля браузера Chrome.
        self.options.add_argument(f"user-data-dir={USER_DATA_DIR}")

        # Запуск браузера в полноэкранном режиме.
        self.options.add_argument("--start-maximized")

        # Название директории профиля браузера Chrome.
        self.options.add_argument(f"--profile-directory={profile_directory}")

        # ЗАПОЛНИТЬ
        self.options.add_argument("--disable-blink-features=AutomationControlled")

        # Запуск браузера без графической оболочки.
        self.options.add_argument("--headless")

        # Отключение использования GPU.
        self.options.add_argument("--disable-gpu")

        # -------------------- Конец блока настроек Chrome Webdriver -------------------- #

        # Авторизируемся на сайте Modeus, если регистрации ещё не было.
        if not self.__page_user_name:
            self.__autorization()

    def get_soup(self, page_source: str) -> BeautifulSoup:
        '''
        Принимает код страницы и возвращает объект BeautifulSoup.

        Параметры:
            page_source: str - код страницы.

        Возвращает:
            BeautifulSoup - объект BeautifulSoup.
        '''

        return BeautifulSoup(page_source, "lxml")

    def save_next_week_schedule(self) -> None:
        '''
        Используется, если требуется получить расписание на следующую неделю.
        Вызывает метод ScheduleParser.save_week_schedule() с аргументом next_week=True.
        '''

        self.save_week_schedule(next_week=True)

    def save_week_schedule(self, next_week: bool = False) -> None:
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

        # Проверка, что в файле schedule.json не сохранено расписание на требуемую неделю.
        self._check_saved_file()

        if next_week:
            self._change_to_next_week()

        soup = self.get_soup(self.browser.page_source)

        # Даты дней недели.
        days = self.get_days(soup=soup)

        # Записываем в файл schedule.json расписание.
        full_schedule: dict = {}
        with open("schedule.json", "w", encoding="utf-8") as json_file:
            for day in days:
                full_schedule.setdefault(self.user_name, {}).setdefault(day, self.get_day_schedule(soup=soup, day_num=days.index(day)))
            json.dump(full_schedule, json_file, ensure_ascii=False)

        # self.browser.close()
        # self.browser.quit()

    def get_day_schedule(self, soup: BeautifulSoup, day_num: int) -> dict:
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
        day = soup.select(".fc-content-col")[day_num]

        # Если каких-то данных не достаёт, заполняем значением NoDataException,
        # то есть строкой "нет данных".
        day_schedule: dict = {}
        for subject, classroom, time in zip_longest(
            day.select(".fc-title"), day.select("small"), day.select(".fc-time span"),
            fillvalue=NoDataException
        ):
            day_schedule.setdefault(time.text.zfill(13), (subject.text, classroom.text))

        return day_schedule

    def get_days(self, soup: BeautifulSoup) -> list:
        '''
        Возвращает список с названиями дней, указанных на странице.

        Принимает:
            soup: BeautifulSoup - суп страницы с расписанием.
        Возвращает:
            Список с названиями дней.
        '''

        return [day.text for day in soup.select(".fc-day-header span")]

    '''
    def load_cookies(self, webdriver: webdriver.Chrome) -> None:
        with open(file="cookies.json", mode="r", encoding="utf-8") as cookies_file:
            for cookie in json.load(cookies_file):
                webdriver.add_cookie(cookie)

    def save_cookies(self, webdriver: webdriver.Chrome) -> None:
        with open(file="cookies.json", mode="w", encoding="utf-8") as cookies_file:
            json.dump(webdriver.get_cookies(), cookies_file)
    '''

    def __autorization(self) -> None:
        self.browser = webdriver.Chrome(options=self.options)
        self.browser.get(self.url)

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.ID, "userNameInput"))
        )

        self.browser.find_element(By.ID, "userNameInput").send_keys(self.__login)
        self.browser.find_element(By.ID, "passwordInput").send_keys(self.__password)
        self.browser.find_element(By.ID, "submitButton").click()

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ".fc-title"))
        )

        self.__page_user_name = self.browser.find_element(By.CSS_SELECTOR, ".user-name.user-full-name.user-visible-name").text

        if self.__page_user_name != self.user_name:
            self._change_user()

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

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ".fc-title"))
        )

    def _change_to_next_week(self) -> None:
        self.browser.find_element(By.XPATH, "//span[@class='fc-icon fc-icon-right-single-arrow']").click()
        self.browser.refresh()

        WebDriverWait(self.browser, 10).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ".fc-title"))
        )

    def _check_saved_file(self) -> None:
        try:
            with open("schedule.json", "r", encoding="utf-8") as json_file:
                schedule = json.load(json_file)
                if self.date in schedule:
                    raise ScheduleException
        except FileNotFoundError:
            return

    def __save_user_data(self, login: str, password: str) -> None:
        pass