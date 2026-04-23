from aiogram import Dispatcher
from aiogram.types import Update


class UserMiddleware:
    async def __call__(self, handler, event: Update, data: dict):
        if hasattr(event, "message") and event.message:
            user = event.message.from_user
            if user:
                data["user"] = user
        return await handler(event, data)


def setup(dp: Dispatcher):
    dp.message.middleware(UserMiddleware())
