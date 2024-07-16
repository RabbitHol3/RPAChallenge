from RPA.Browser.Selenium import (
    By,
    Selenium,
    WebElement,
    expected_conditions as EC,
    WebDriverWait,
)
from contextlib import contextmanager
from RPA.core.webdriver import webdriver, WebDriver
from RPA.Browser.Selenium import WebElement
import re
import requests
from datetime import datetime
from enum import Enum

from typing import List, TYPE_CHECKING, Generator, Any


if TYPE_CHECKING:
    from loguru import Logger

lib_selenium = Selenium()

DEFAULT_WAIT_TIME = 10


class Article:

    _XPATH_DATE: str
    _XPATH_TITLE: str
    _XPATH_DESCRIPTION: str
    _XPATH_PICTURE: str

    title: str
    date: datetime
    description: str
    picture_url: str
    url: str

    element: WebElement

    def __init__(self, element: WebElement):
        self.element = element

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} title='{self.title}'>"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Article):
            return False
        return self.url == value.url and self.date == value.date

    def __contains__(self, item: str) -> bool:
        return item in self.title or item in self.description

    def __hash__(self) -> int:
        return hash(self.url)

    @property
    def text(self) -> str:
        return self.element.text

    def find_element(self, value, by=By.XPATH) -> WebElement:
        return next(iter(self.find_elements(by=by, value=value) or ()))

    def find_elements(self, value, by=By.XPATH) -> List[WebElement]:
        return self.element.find_elements(by, value)

    def _get_title(self) -> WebElement:
        return self.find_element(self._XPATH_TITLE)

    def _get_date(self) -> WebElement:
        return self.find_element(self._XPATH_DATE)

    def _get_description(self) -> WebElement:
        return self.find_element(self._XPATH_DESCRIPTION)

    def _get_picture(self) -> WebElement:
        return self.find_element(self._XPATH_PICTURE)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "date": int(self.date.timestamp()),
            "picture_url": self.picture_url,
        }

    def __dict__(self) -> dict:
        return self.to_dict()


class SearchResultPage(WebDriver):
    handle: str
    has_news_section: bool = False

    __last_page: dict[WebDriver, str] = {}

    def __init__(self, driver: 'WebDriver', handle: str):
        self.handle = handle
        self.driver = driver
        self.wait = WebDriverWait(self.driver, DEFAULT_WAIT_TIME)

    # Handling context manager
    # This is a context manager that will switch the driver handle to the respective
    # when interacting with the page object
    # since selenium has dont handle multiple windows as different objects
    def __getattr__(self, name: str) -> Any:  # Handling attribute access gracefully
        if self.driver.current_window_handle != self.handle:
            # if self.driver.current_window_handle not in SearchResultPage.__pages[self]:
            #     SearchResultPage.__pages[self].append(self.driver.current_window_handle)
            SearchResultPage.__last_page[self.driver] = self.driver.current_window_handle
            self.driver.switch_to.window(self.handle)
        return getattr(self.driver, name)

    def __enter__(self) -> 'SearchResultPage':
        self.driver.switch_to.window(self.handle)
        return self

    def __exit__(self, *args) -> None:
        self.driver.close()

        self.driver.switch_to.window(self.driver.window_handles[-1])

    def __repr__(self):
        return f"<{self.__class__.__name__} title='{self.driver.title}'>"

    def find_element(self, value: str, by=By.XPATH) -> 'WebElement':
        try:
            return next(iter(self.find_elements(by=by, value=value) or ()))
        except StopIteration:
            return None

    def find_elements(self, value: str, by=By.XPATH) -> List['WebElement']:
        return self.driver.find_elements(by, value)

    def go_to_next_page(self) -> bool: ...

    def get_articles(self) -> List[Article]: raise NotImplementedError

    def select_section(self, section: str) -> None: raise NotImplementedError


class NewsBrowser:
    wait: WebDriverWait
    driver: WebDriver
    logger: 'Logger'

    def __init__(self, logger: 'Logger' = None, *args, **kwargs):
        logger.debug("Creating browser") if logger else None

        lib_selenium.open_available_browser(
            browser_selection="Chrome",
            *args, **kwargs)

        self.driver = lib_selenium.driver
        self.wait = WebDriverWait(self.driver, DEFAULT_WAIT_TIME)
        self.logger: 'Logger' = logger
        self.driver.add_cookie(
            {"name": "cookieyes-consent", "value": "consent:yes,action:yes"})
        self.driver.refresh()

    @staticmethod
    def log(func):
        def wrapper(*args, **kwargs):
            self = args[0]
            assert isinstance(
                self, NewsBrowser), "This decorator can only be used in NewsBrowser subclasses"
            if self.logger:
                self.logger.debug(
                    f"Calling {func.__name__} with args: {args[1:]} {' and kwargs: ' + str(kwargs) if kwargs else ''}")
                start = datetime.now()
            res = func(*args, **kwargs)

            if self.logger:
                end = datetime.now()
                self.logger.debug(
                    f"Finished '{func.__name__}' in {end - start}")
            return res

        return wrapper

    @log
    def new_page(self, url: str) -> WebDriver: ...

    @log
    def search(self, search_phrase: str) -> SearchResultPage: ...

    def __enter__(self) -> 'NewsBrowser':
        return self

    def __exit__(self, *args) -> None:
        self.driver.quit()
        if self.logger:
            self.logger.debug("Quitting browser") if self.logger else None
