import logging
import re
from html import escape
from pathlib import Path
from typing import Optional

from aiogram import Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InputMediaPhoto, Message
from aiogram.fsm.context import FSMContext

from app.services.audit import create_download_event, log_error, update_download_event
from app.services.limiter import (
    ensure_user_exists,
    check_limit,
    increment_usage,
)
from app.services.downloader import (
    cleanup_result,
    detect_platform,
    download_media,
    is_valid_url,
)
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

router = Router()


def extract_url(text: str) -> Optional[str]:
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в бота для скачивания Tiktok и Youtube видео!\n\n"
        "Отправь мне ссылку на видео с Youtube или Tiktok, и я скачаю его для тебя.\n\n"
        "📊 Дневной лимит: 5 загрузок в день\n\n"
        "Поддерживающие платформы:\n"
        "• TikTok (видео & фото)\n"
        "• YouTube"
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_link(message: Message, state: FSMContext):
    telegram_id = message.from_user.id

    async with async_session_maker() as db:
        try:
            user = await ensure_user_exists(db, telegram_id)
            url = extract_url(message.text or "")
            platform = detect_platform(url).value if url else "unknown"
            download_event = None

            if user.is_banned:
                await log_error(
                    db,
                    "bot",
                    "User attempted to download while banned",
                    telegram_id=telegram_id,
                    user=user,
                    details=message.text,
                )
                await message.answer("⛔ Вы забанены в данном боте.")
                return

            allowed, current, limit = await check_limit(db, user)
            if not allowed:
                await log_error(
                    db,
                    "limit",
                    f"Daily limit reached ({current}/{limit})",
                    telegram_id=telegram_id,
                    user=user,
                    details=message.text,
                )
                await message.answer(
                    f"❌ Исчерпан дневной лимит ({limit}/{limit}).\nВозвращайтесь завтра!!"
                )
                return

            if not url:
                await log_error(
                    db,
                    "validation",
                    "No valid URL found in message",
                    telegram_id=telegram_id,
                    user=user,
                    details=message.text,
                )
                await message.answer(
                    "❌ Неправильная ссылка.\nПожалуйста отправьте ссылку с TikTok или YouTube."
                )
                return

            if not is_valid_url(url):
                await log_error(
                    db,
                    "validation",
                    "Unsupported URL submitted",
                    telegram_id=telegram_id,
                    user=user,
                    details=url,
                )
                await message.answer(
                    "❌ Неправильная ссылка.\nПоддерживаются только ссылки на Tiktok и Youtube."
                )
                return

            download_event = await create_download_event(
                db,
                telegram_id,
                url,
                platform=platform,
                user=user,
                status="processing",
            )
            await message.answer("⏳ Обработка запроса...")

            result = await download_media(url, telegram_id)

            if not result.success:
                await update_download_event(
                    db,
                    download_event,
                    status="failed",
                    media_type=result.media_type.value if result.media_type else None,
                    title=result.title,
                    error_message=result.error,
                )
                await log_error(
                    db,
                    "download",
                    result.error or "Unknown download error",
                    telegram_id=telegram_id,
                    user=user,
                    details=url,
                )
                await message.answer(f"❌ Ошибка: {result.error} - отправьте разработчику")
                cleanup_result(result)
                return

            try:
                caption = escape(result.title or "Video")

                if result.media_type.value == "slideshow" and result.files:
                    media_group = []
                    for i, file_path in enumerate(result.files[:10]):
                        try:
                            media = InputMediaPhoto(
                                media=FSInputFile(file_path),
                                caption=caption if i == 0 else None,
                            )
                            media_group.append(media)
                        except Exception as e:
                            logger.error(f"Error preparing image {i}: {e}")
                            continue

                    if media_group:
                        await message.answer_media_group(media_group)
                        if not await increment_usage(db, user):
                            logger.warning(
                                "Usage limit exceeded immediately after slideshow send for user %s",
                                telegram_id,
                            )
                        await update_download_event(
                            db,
                            download_event,
                            status="success",
                            media_type=result.media_type.value,
                            title=result.title,
                            file_count=len(result.files),
                            file_size_bytes=sum(
                                Path(file_path).stat().st_size
                                for file_path in result.files
                                if Path(file_path).exists()
                            ),
                        )
                        await message.answer("✅ Фото отправлено!")
                    else:
                        await update_download_event(
                            db,
                            download_event,
                            status="failed",
                            media_type=result.media_type.value,
                            title=result.title,
                            error_message="Could not process slideshow images",
                        )
                        await message.answer("❌ Не удалось обработать изображения.")

                elif result.files:
                    for file_path in result.files:
                        try:
                            await message.answer_video(
                                video=FSInputFile(file_path),
                                caption=caption,
                            )
                        except Exception as e:
                            logger.error(f"Error sending video: {e}")
                            try:
                                await message.answer_document(
                                    document=FSInputFile(file_path),
                                    caption=caption,
                                )
                            except Exception as e2:
                                logger.error(f"Error sending document: {e2}")
                                await message.answer(f"❌ Ошибка отправления файлов: {e}")
                                await update_download_event(
                                    db,
                                    download_event,
                                    status="failed",
                                    media_type=result.media_type.value,
                                    title=result.title,
                                    error_message=str(e2),
                                )
                                await log_error(
                                    db,
                                    "telegram-send",
                                    str(e2),
                                    telegram_id=telegram_id,
                                    user=user,
                                    details=file_path,
                                )
                                return

                    if not await increment_usage(db, user):
                        logger.warning(
                            "Usage limit exceeded immediately after video send for user %s",
                            telegram_id,
                        )
                    await update_download_event(
                        db,
                        download_event,
                        status="success",
                        media_type=result.media_type.value,
                        title=result.title,
                        file_count=len(result.files),
                        file_size_bytes=sum(
                            Path(file_path).stat().st_size
                            for file_path in result.files
                            if Path(file_path).exists()
                        ),
                    )
                    await message.answer("✅ Видео отправлено!")
                else:
                    await update_download_event(
                        db,
                        download_event,
                        status="failed",
                        media_type=result.media_type.value,
                        title=result.title,
                        error_message="No files downloaded",
                    )
                    await message.answer("❌ Файлы не загружены.")

            except Exception as e:
                logger.error(f"Error sending media: {e}")
                if download_event:
                    await update_download_event(
                        db,
                        download_event,
                        status="failed",
                        media_type=result.media_type.value if result.media_type else None,
                        title=result.title,
                        error_message=str(e),
                    )
                await log_error(
                    db,
                    "send-media",
                    str(e),
                    telegram_id=telegram_id,
                    user=user,
                    details=url,
                )
                await message.answer(f"❌ Ошибка отправки фото: {e}")

            finally:
                cleanup_result(result)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await log_error(
                db,
                "bot",
                str(e),
                telegram_id=telegram_id,
                user=user if "user" in locals() else None,
                details=message.text,
            )
            await message.answer("❌ Произошла ошибка, попробуйте еще раз.")


def setup(dp: Dispatcher):
    dp.include_router(router)
