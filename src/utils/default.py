from functools import wraps
from .exceptions import *
from typing import List, Tuple


def retry_on_error(max_retries=3, execept: Tuple[Exception] | Exception = Exception, logger=None):
    """ 
    Decorator to retry a function in case of an error.

    Args:
        max_retries (int): Maximum number of retries.
        execept (List[Exception] | Exception): Exception or list of exceptions NOT to retry.

    """
    if not isinstance(execept, (list, tuple)):
        execept = (execept,)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except execept as e:
                    raise e
                except Exception as e:
                    if retries >= max_retries:
                        raise e
                    if logger:
                        logger.warning(
                            f"Retrying {func.__name__}... {retries} of {max_retries} ({e})")
                retries += 1
        return wrapper
    return decorator
