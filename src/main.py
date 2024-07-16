from functools import wraps
from src.utils import news_browser
from src.utils.news_browser import (
    NewsBrowser,
    Article,
    Aljazeera
)
from src.utils.default import retry_on_error
import multiprocessing.pool
from robocorp.tasks import task, ITask, setup
from robocorp import workitems
from loguru import logger
import psutil
import pathlib
import requests
import sys
import random
import multiprocessing
import re
from src.utils import exceptions
import string
import pandas as pd


OUTPUT_DIR = "output"
IMAGE_DIR = OUTPUT_DIR / "images"
MAX_TASK_RETRIES = 3


def setup_logger():
    # Setting up loguru

    global logger
    logger = logger.patch(lambda record: record["extra"].update(
        cpu=f"{psutil.cpu_percent()}%",
        mem=f"{psutil.virtual_memory().percent}%",
        disk=f"{psutil.disk_usage('/').percent}%",
    ))

    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        # machine data purple
        "<fg #ff00ff>CPU {extra[cpu]: <5}</fg #ff00ff> | "
        "<fg #ff00ff>MEM {extra[mem]: <5}</fg #ff00ff> | "
        "<fg #ff00ff>DISK {extra[disk]: <5}</fg #ff00ff> | "
        # log level in brackets

        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        " - <level>{message}</level>"
    )

    # Default values
    logger.configure(extra={"cpu": "", "mem": "", "disk": ""})
    logger.remove()
    logger.add(
        "logs/{time:YYYY-MM-DD}.log",  # or sys.stdout
        rotation="1 day",
        retention="7 days",
        colorize=True,
        format=logger_format,
        enqueue=True
    )
    logger.add(sys.stdout, colorize=True, format=logger_format, level="DEBUG")


@setup
def setup(task: ITask):
    """ Setup for the task suite """
    assert workitems.inputs.current.payload, "No input data was provided"
    logger.debug(f"Workitem: {workitems.inputs.current.payload}")

    logger.debug("Setting up logger...")
    setup_logger()
    logger.debug("Logger setup complete")


@logger.catch
def search(browser: NewsBrowser, search_phrase: str, news_section: str, number_months: str) -> set[Article]:
    logger.info("Searching for news...")
    # search_phrase = "silvio santos"
    with browser.search(search_phrase) as result_page:
        if news_section and result_page.has_news_section:
            result_page.select_section(news_section)
            logger.info(f"Selected section: {news_section}")

        logger.info("Collecting articles...")
        articles = set(result_page.get_articles(month_threshold=number_months))
        while result_page.go_to_next_page():
            logger.info("Navigating to next page...")
            articles.update(result_page.get_articles())
        logger.info(f"Found {len(articles)} articles")
    logger.info("News search complete")
    return articles


@logger.catch
def download_picture(article: dict):
    file_name = ''.join(random.choices(string.ascii_lowercase, k=10)) + ".png"
    response = requests.get(article['picture_url'])
    if response.status_code == 200:
        with open(IMAGE_DIR / file_name, "wb") as file:
            file.write(response.content)
        article['image_path'] = str((IMAGE_DIR / file_name).absolute())
    else:
        logger.error(f"Failed to download image: {article['image_url']}")


@logger.catch
def download_pictures(articles: list[dict]):
    if not OUTPUT_DIR.exists():
        logger.info("Creating output directory...")
        OUTPUT_DIR.mkdir()

    if not IMAGE_DIR.exists():
        IMAGE_DIR.mkdir()

    pool = multiprocessing.pool.ThreadPool(5)
    result = pool.map_async(download_picture, articles)
    result.wait()  # Wait for the download to finish


def validate_payload(payload: dict, expected_keys: list[str]) -> None:
    missing_keys = set(expected_keys) - set(payload.keys())
    if missing_keys:
        raise exceptions.InvalidWorkItem(
            f"Missing keys in payload: {missing_keys}")


@logger.catch(reraise=True)
@retry_on_error(
    max_retries=MAX_TASK_RETRIES,
    execept=(exceptions.InvalidWorkItem, exceptions.BusinessException),
    logger=logger
)
def fetch_news(item: dict) -> None:
    logger.info("Validating workitem parameters...")
    # First lets validate the workitem
    # We need to make sure that the workitem has the required parameters
    expected_params = (
        "search_phrase", "news_section", "number_months")
    validate_payload(item, expected_params)
    logger.info("Workitem parameters validated")

    with Aljazeera(logger=logger, headless=True) as news_browser:
        articles: set[Article] = search(news_browser, **item)
        item["search_result"] = [article.to_dict()
                                 for article in articles]


@task()
def store_data():
    """ 
    5. Store in an Excel file:
    - title
    - date
    - description (if available)
    - picture filename
    - count of search phrases in the title and description
    - True or False, depending on whether the title or description contains any amount of money
        > Possible formats: $11.1 | $111,111.11 | 11 dollars | 11 USD
    """
    for item in workitems.inputs:
        # item is expected to be a dictionary
        # and already have the search result
        # with the articles and their information
        try:
            payload = item.payload
            logger.info("Validating payload...")
            validate_payload(payload, ["search_result"])
            logger.info("Payload validated")

            # Save articles
            logger.info("Saving articles to Excel...")
            articles = payload["search_result"]

            df = pd.DataFrame(articles)

            # Keep only the columns we need
            df = df[["title", "date", "description", "image_path",
                     "search_phrase_occurrences", "has_amount"]]

            # Format date
            # from unix timestamp to datetime
            df["date"] = pd.to_datetime(df["date"], unit="s")

            df.to_excel(
                OUTPUT_DIR / f"articles_{hash(item)}.xlsx", index=False)
            logger.info("Articles saved to Excel")
            item.done()
        except Exception as e:
            logger.error(f"Failed to process workitem: {e}")
            item.fail(**exceptions.UnexpectedError(str(e)))


@task()
def fetch_data():
    for item in workitems.inputs:
        try:
            # Search Phase Ocurrences count in title and description
            payload = item.payload
            logger.info("Validating payload...")
            validate_payload(payload, ["search_phrase", "search_result"])
            logger.info("Payload validated")

            search_phrase = payload["search_phrase"]
            regex = r"\$\d+\.?\d*|\d+ dollars|\d+ USD"
            logger.info("Processing articles...")
            for a in payload["search_result"]:
                # Search Phrase Ocurrences count in title and description
                a["search_phrase_occurrences"] = ''.join(
                    (a["title"].lower(), a["description"].lower())).count(search_phrase)
                # Money in title or description
                # - True or False, depending on whether the title or description contains any amount of money
                # Possible formats: $11.1 | $111,111.11 | 11 dollars | 11 USD
                a["has_amount"] = any(re.search(regex, text) for text in (
                    a["title"], a["description"]))
            # Save articles
            logger.info("Downloading pictures...")
            download_pictures(payload["search_result"])
            logger.info("Pictures downloaded")
            logger.info("Articles processed")
            workitems.outputs.create(payload)
            item.done()
        except Exception as e:
            logger.error(f"Failed to process workitem: {e}")
            item.fail(**exceptions.UnexpectedError(str(e)))


@task()
def capture_news():
    for item in workitems.inputs:
        fetch_news(item.payload)
        workitems.outputs.create(item.payload)
        item.done()
