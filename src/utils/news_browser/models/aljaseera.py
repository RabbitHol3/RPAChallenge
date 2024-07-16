from ..base import NewsBrowser, Article, SearchResultPage
from RPA.core.webdriver import webdriver
from typing import TYPE_CHECKING, List
from RPA.Browser.Selenium import (
    By,
    Selenium,
    WebElement,
    expected_conditions as EC,
    WebDriverWait,
)
from datetime import datetime
import re
if TYPE_CHECKING:
    from RPA.core.webdriver import WebDriver


class AjArticle(Article):

    _XPATH_DATE: str = ".//footer//span[2]"
    _XPATH_TITLE: str = ".//h3[@class='gc__title']"
    _XPATH_DESCRIPTION: str = ".//div[@class='gc__body-wrap']//p"
    _XPATH_PICTURE: str = ".//img"

    def __init__(self, element: WebElement):
        super().__init__(element)
        self.title = self.get_title()
        self.date = self.parse_date(self._get_date())
        self.description = self.get_description()
        self.picture_url = self.get_picture_url()
        self.url = self.get_url()

    def get_title(self) -> str:
        el = self._get_title()
        return el.text.strip() if el else None

    @staticmethod
    def parse_date(el: WebElement) -> datetime:
        try:
            date_str = re.search(r"(\d{1,2} \w{3} \d{4})", el.text).group(0)
        except AttributeError:
            return None
        date = datetime.strptime(date_str, "%d %b %Y")
        return date

    def get_url(self) -> str:
        return self._get_title().find_element(By.TAG_NAME, "a").get_attribute("href")

    def get_description(self) -> str:
        el = self._get_description()

        if not el:
            return None
        # it comes with 'hour ago ...' at the beginning
        # and ' ...' at the end
        return re.sub(r'(\d+\s+\w+\s+ago\s+...\s+...\s+(?=\w+))', '', el.text).rstrip('...').strip()

    def get_picture_url(self) -> str:
        el = self._get_picture()
        return el.get_attribute("src") if el else None


class AjSearchResultPage(SearchResultPage):

    XPATH_NEXT_PAGE_BUTTON = "//button[contains(@class, 'show-more-button')]"
    XPATH_LOADING_ELEMENT = "//div[contains(@class, 'show-more-button--loading')]"
    XPATH_RESULT_DIV = "//div[@class='search-result__list']"
    has_news_section: bool = False
    __finished: bool = False

    def __init__(self, driver: 'WebDriver', handle: str):
        super().__init__(driver, handle)
        # wait page to be loaded
        self.wait.until(EC.presence_of_element_located(
            (By.XPATH, self.XPATH_RESULT_DIV)))

    def go_to_next_page(self) -> bool:
        if self.__finished:
            return 0
        btn = self.find_element(self.XPATH_NEXT_PAGE_BUTTON)
        if not btn:
            return 0
        self.driver.execute_script(
            "arguments[0].scrollIntoView();arguments[0].click()", btn)
        self.wait.until(EC.invisibility_of_element_located(
            (By.XPATH, self.XPATH_LOADING_ELEMENT)))
        return 1

    def get_articles(self, month_threshold: int = 1) -> List[dict]:

        div_result = self.find_element(self.XPATH_RESULT_DIV)
        # Building article xpath
        # This is a bit of a hack
        # I'm getting all the xpaths from the AjArticle class
        # and joining them with an 'and' operator
        # to get the articles
        # This is to avoid if the xpaths change in the future
        # I can just change the xpaths in the AjArticle class
        # and it will be reflected here
        article_xpath = f"//article[{' and '.join(map(lambda a: getattr(AjArticle, a) ,filter(lambda x:'_XPATH' in x.upper(), dir(AjArticle))))}]"
        # Getting articles
        articles_els = div_result.find_elements(By.XPATH, article_xpath)
        ars = []
        for a in articles_els:
            # first check if the article is in threshold
            a_date = AjArticle.parse_date(
                a.find_element(By.XPATH, AjArticle._XPATH_DATE))
            # Example of how this should work: 0 or 1 - only the current month, 2 - current and previous month, 3 - current and two previous months, and so on
            diff = datetime.now() - a_date
            if diff.days > 30*(month_threshold or 1):
                self.__finished = True
                break
            ars.append(AjArticle(a))
        return ars
        # return [AjArticle(article) for article in articles_els]


class AljazeeraBrowser(NewsBrowser):
    __url: str = "https://www.aljazeera.com"

    def __init__(self, options=None, *args, **kwargs):
        if not options:
            options = webdriver.ChromeOptions()
            options.page_load_strategy = 'eager'
            options.add_argument("--disable-proxy-certificate-handler")

        super().__init__(url=self.__url, options=options, *args, **kwargs)

    def new_page(self, url: str) -> AjSearchResultPage:
        self.driver.switch_to.new_window('tab')
        self.driver.get(url)
        return AjSearchResultPage(self.driver, self.driver.current_window_handle)

    @NewsBrowser.log
    def search(self, search_phrase: str) -> AjSearchResultPage:
        return self.new_page(url=f"{self.__url}/search/{search_phrase}?sort=date")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
