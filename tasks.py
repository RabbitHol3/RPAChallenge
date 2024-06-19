from robocorp.tasks import task
from robocorp import browser

@task
def minimal_task():
    message = "Hello"
    message = message + " World!"
    browser.goto("https://robocorp.com")

    
    