import asyncio
from functools import wraps


def retry(max_retries=3, delay=1, on_failure=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_retries:
                        if on_failure:
                            return await on_failure(*args, error=e, *kwargs)
                        raise e
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
