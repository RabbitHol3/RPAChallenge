from loguru import logger

class Logger(logger.__class__):
    def __init__(self):
        super().__init__()
        self.add("logs/{time:YYYY-MM-DD}.log", rotation="1 day")
