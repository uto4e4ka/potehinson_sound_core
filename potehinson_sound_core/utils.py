import asyncio
from functools import wraps


def retry(count: int, delay: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = count

            while attempts > 0:
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    attempts -= 1

                    if attempts == 0:
                        raise

                    await asyncio.sleep(delay)

        return wrapper

    return decorator