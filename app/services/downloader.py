import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from enum import Enum
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen, urlretrieve
import re

import yt_dlp
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class Platform(Enum):
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class MediaType(Enum):
    VIDEO = "video"
    SLIDESHOW = "slideshow"


class DownloadResult:
    def __init__(
        self,
        success: bool,
        platform: Platform = Platform.UNKNOWN,
        media_type: MediaType = MediaType.VIDEO,
        file_path: Optional[str] = None,
        files: list[str] = None,
        error: Optional[str] = None,
        title: Optional[str] = None,
    ):
        self.success = success
        self.platform = platform
        self.media_type = media_type
        self.file_path = file_path
        self.files = files or []
        self.error = error
        self.title = title


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def classify_youtube_error(error: Exception | str) -> str:
    text = str(error).lower()

    if "sign in to confirm your age" in text or "age-restricted" in text:
        return "This YouTube video is age-restricted. Add a valid cookies.txt file to download it."

    if "cookies-from-browser" in text or "cookies" in text:
        return "This YouTube video requires authentication. Add a valid cookies.txt file and try again."

    if "no supported javascript runtime" in text:
        return (
            "YouTube extraction needs a JavaScript runtime for this video. "
            "Install Node.js or provide Deno, then try again."
        )

    if "requested format is not available" in text:
        return "Could not find a Telegram-compatible format for this YouTube video."

    return str(error)


def detect_platform(url: str) -> Platform:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "tiktok.com" in domain or "vm.tiktok.com" in domain:
        return Platform.TIKTOK
    elif (
        "youtube.com" in domain
        or "youtu.be" in domain
        or "youtube.googleapis.com" in domain
    ):
        return Platform.YOUTUBE

    return Platform.UNKNOWN


def normalize_tiktok_url(url: str) -> str:
    parsed = urlparse(url)
    if "tiktok.com" not in parsed.netloc.lower():
        return url

    clean_path = parsed.path.rstrip("/")
    if not clean_path:
        return url

    return f"{parsed.scheme}://{parsed.netloc}{clean_path}"


def get_tiktok_item_id(url: str) -> str | None:
    match = re.search(r"/(?:video|photo)/(\d+)", url)
    return match.group(1) if match else None


def is_valid_url(url: str) -> bool:
    platform = detect_platform(url)
    return platform != Platform.UNKNOWN


async def download_media(url: str, user_id: int) -> DownloadResult:
    if not is_valid_url(url):
        return DownloadResult(
            success=False, error="Invalid URL. Only TikTok and YouTube are supported."
        )

    platform = detect_platform(url)

    import uuid

    temp_dir = Path(tempfile.gettempdir()) / f"bot_{uuid.uuid4().hex[:8]}"
    temp_dir.mkdir(exist_ok=True)

    try:
        if platform == Platform.TIKTOK:
            result = await _download_tiktok(url, temp_dir)
        elif platform == Platform.YOUTUBE:
            result = await _download_youtube(url, temp_dir)
        else:
            result = DownloadResult(success=False, error="Unsupported platform")

        result.platform = platform
        result._temp_dir = temp_dir
        return result

    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return DownloadResult(success=False, error=str(e))


async def probe_media(url: str) -> DownloadResult:
    if not is_valid_url(url):
        return DownloadResult(
            success=False, error="Invalid URL. Only TikTok and YouTube are supported."
        )

    platform = detect_platform(url)
    temp_dir = Path(tempfile.gettempdir()) / "bot_probe"
    temp_dir.mkdir(exist_ok=True)

    try:
        if platform == Platform.TIKTOK:
            normalized_url = normalize_tiktok_url(url)
            ydl_opts = {
                "quiet": True,
                "nowarnings": True,
                "extract_flat": False,
                "js_runtimes": {"node": {}},
                "remote_components": ["ejs:github"],
            }
            loop = asyncio.get_event_loop()

            def _extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(normalized_url, download=False)

            info = await loop.run_in_executor(None, _extract)
            if "entries" in info:
                info = info["entries"][0]

            media_type = (
                MediaType.SLIDESHOW
                if info.get("is_slideshow", False) or info.get("type") == "photo"
                else MediaType.VIDEO
            )
            return DownloadResult(
                success=True,
                platform=platform,
                media_type=media_type,
                title=info.get("title", "TikTok media"),
            )

        ydl_opts = {
            "quiet": True,
            "nowarnings": True,
            "noplaylist": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
        }
        if os.path.exists(settings.YTDLP_COOKIES_PATH):
            ydl_opts["cookiefile"] = settings.YTDLP_COOKIES_PATH

        loop = asyncio.get_event_loop()

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, _extract)
        return DownloadResult(
            success=True,
            platform=platform,
            media_type=MediaType.VIDEO,
            title=info.get("title", "YouTube video"),
        )
    except Exception as e:
        return DownloadResult(success=False, platform=platform, error=classify_youtube_error(e))


def cleanup_result(result: DownloadResult):
    if hasattr(result, "_temp_dir") and result._temp_dir.exists():
        import shutil

        try:
            shutil.rmtree(result._temp_dir)
        except:
            pass


async def _download_tiktok(url: str, temp_dir: Path) -> DownloadResult:
    url = normalize_tiktok_url(url)
    cookies_path = settings.YTDLP_COOKIES_PATH

    ydl_opts = {
        "format": "best",
        "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "nowarnings": True,
        "extract_flat": False,
        "fragment_retries": 3,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }

    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    loop = asyncio.get_event_loop()

    def _extract_info():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info

    try:
        info = await loop.run_in_executor(None, _extract_info)
    except Exception as e:
        error_text = str(e)
        if "/photo/" in url or "Unsupported URL" in error_text:
            logger.info("Falling back to HTML extraction for TikTok photo post: %s", url)
            return await _download_tiktok_photo_post(url, temp_dir)
        raise

    if not info:
        return DownloadResult(success=False, error="Could not extract video info")

    title = info.get("title", "tiktok_video")

    if "entries" in info:
        info = info["entries"][0]

    is_slideshow = info.get("is_slideshow", False) or info.get("type") == "photo"

    if is_slideshow:
        images = info.get("slideshow_images", []) or info.get("images", [])
        if images:
            downloaded_images = []
            for i, img_url in enumerate(images[:10]):
                try:
                    if isinstance(img_url, dict):
                        img_url = img_url.get("url", "")
                    if not img_url:
                        continue
                    ext = Path(unquote(urlparse(img_url).path)).suffix or ".jpg"
                    img_path = temp_dir / f"img_{i}{ext}"
                    await loop.run_in_executor(
                        None, lambda: urlretrieve(img_url, str(img_path))
                    )
                    if img_path.exists() and img_path.stat().st_size > 0:
                        downloaded_images.append(str(img_path))
                except Exception as e:
                    logger.warning(f"Failed to download image {i}: {e}")
                    continue

            if downloaded_images:
                return DownloadResult(
                    success=True,
                    media_type=MediaType.SLIDESHOW,
                    files=downloaded_images,
                    title=title,
                )

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    await loop.run_in_executor(None, _download)

    downloaded_files = list(temp_dir.glob("*"))
    video_files = [
        f
        for f in downloaded_files
        if f.is_file()
        and f.stat().st_size > 0
        and f.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not video_files:
        return DownloadResult(success=False, error="No files were downloaded")

    return DownloadResult(
        success=True,
        media_type=MediaType.VIDEO,
        files=[str(f) for f in video_files],
        title=title,
    )


def _find_json_block(html: str) -> dict | None:
    patterns = [
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">([^<]+)</script>',
        r'<script id="SIGI_STATE" type="application/json">([^<]+)</script>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue

        raw_json = unescape(match.group(1))
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            continue

    return None


def _extract_title_from_page_data(data: object) -> str | None:
    if isinstance(data, dict):
        for key in ("desc", "title"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        share_meta = data.get("shareMeta")
        if isinstance(share_meta, dict):
            desc = share_meta.get("desc")
            if isinstance(desc, str) and desc.strip():
                return desc.strip()

        for value in data.values():
            title = _extract_title_from_page_data(value)
            if title:
                return title

    elif isinstance(data, list):
        for item in data:
            title = _extract_title_from_page_data(item)
            if title:
                return title

    return None


def _extract_image_urls_from_page_data(data: object) -> list[str]:
    urls: list[str] = []

    def visit(node: object):
        if isinstance(node, dict):
            image_url = node.get("imageURL")
            if isinstance(image_url, dict):
                url_list = image_url.get("urlList")
                if isinstance(url_list, list):
                    for item in url_list:
                        if isinstance(item, str) and item.startswith("http"):
                            urls.append(item)

            for key in ("urlList", "originUrlList"):
                value = node.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.startswith("http"):
                            urls.append(item)

            direct_url = node.get("url")
            if isinstance(direct_url, str) and direct_url.startswith("http"):
                urls.append(direct_url)

            for value in node.values():
                visit(value)

        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data)

    unique_urls: list[str] = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)

    return unique_urls


async def _download_tiktok_photo_post(url: str, temp_dir: Path) -> DownloadResult:
    loop = asyncio.get_event_loop()
    item_id = get_tiktok_item_id(url)
    mobile_url = f"https://m.tiktok.com/v/{item_id}.html" if item_id else url
    logger.info("Starting TikTok photo fallback extraction for %s", mobile_url)

    def _fetch_page() -> str:
        request = Request(
            mobile_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Mobile/15E148 Safari/604.1"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")

    try:
        html = await loop.run_in_executor(None, _fetch_page)
    except Exception as e:
        logger.error("TikTok photo fallback failed to load page %s: %s", mobile_url, e)
        return DownloadResult(
            success=False,
            error=f"Could not load TikTok photo page: {e}",
        )

    logger.info("Loaded TikTok photo page HTML, size=%s bytes", len(html))
    page_data = _find_json_block(html)
    if not page_data:
        logger.error("TikTok photo fallback could not find JSON hydration block for %s", mobile_url)
        return DownloadResult(
            success=False,
            error="Could not parse TikTok photo post page.",
        )

    detail_data = page_data
    if "__DEFAULT_SCOPE__" in page_data:
        detail_data = page_data["__DEFAULT_SCOPE__"].get("webapp.reflow.video.detail") or page_data

    item_struct = (
        detail_data.get("itemInfo", {}).get("itemStruct", {})
        if isinstance(detail_data, dict)
        else {}
    )

    image_post = item_struct.get("imagePost", {}) if isinstance(item_struct, dict) else {}
    images = image_post.get("images", []) if isinstance(image_post, dict) else []

    image_urls = []
    for image in images:
        if not isinstance(image, dict):
            continue
        image_url = image.get("imageURL", {})
        if not isinstance(image_url, dict):
            continue
        for candidate in image_url.get("urlList", []):
            if isinstance(candidate, str) and candidate.startswith("http"):
                image_urls.append(candidate)
                break

    if not image_urls:
        preload_urls = re.findall(r'<link rel="preload" as="image" href="([^"]+)"', html)
        image_urls.extend(preload_urls)

    logger.info("TikTok photo fallback extracted %s candidate image URLs", len(image_urls))
    if not image_urls:
        logger.error("TikTok photo fallback found no image URLs for %s", mobile_url)
        return DownloadResult(
            success=False,
            error="Could not find images in TikTok photo post.",
        )

    title = (
        item_struct.get("desc")
        or _extract_title_from_page_data(detail_data)
        or _extract_title_from_page_data(page_data)
        or "tiktok_slideshow"
    )
    downloaded_images = []

    for i, img_url in enumerate(image_urls[:10]):
        try:
            ext = Path(unquote(urlparse(img_url).path)).suffix or ".jpg"
            img_path = temp_dir / f"img_{i}{ext}"
            await loop.run_in_executor(
                None, lambda url=img_url, path=img_path: urlretrieve(url, str(path))
            )
            if img_path.exists() and img_path.stat().st_size > 0:
                downloaded_images.append(str(img_path))
        except Exception as e:
            logger.warning("Failed to download TikTok slideshow image %s: %s", i, e)

    if not downloaded_images:
        logger.error("TikTok photo fallback downloaded 0 images for %s", mobile_url)
        return DownloadResult(
            success=False,
            error="Could not download images from TikTok photo post.",
        )

    logger.info(
        "TikTok photo fallback downloaded %s images successfully for %s",
        len(downloaded_images),
        mobile_url,
    )
    return DownloadResult(
        success=True,
        media_type=MediaType.SLIDESHOW,
        files=downloaded_images,
        title=title,
    )


async def _download_youtube(url: str, temp_dir: Path) -> DownloadResult:
    try:
        info = await _run_ytdlp_cli_json(url)
    except Exception as e:
        return DownloadResult(success=False, error=classify_youtube_error(e))

    if not info:
        return DownloadResult(success=False, error="Could not extract video info")

    title = info.get("title", "youtube_video")

    try:
        file_path = await download_best_quality(url, temp_dir, settings.TELEGRAM_MAX_SIZE)
    except Exception as e:
        return DownloadResult(success=False, error=classify_youtube_error(e))

    return DownloadResult(
        success=True,
        media_type=MediaType.VIDEO,
        files=[file_path],
        title=title,
    )


async def download_best_quality(url: str, temp_dir: Path, max_size: int) -> str:
    formats = [
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "best[height<=720]",
        "best[height<=480]",
    ]

    for fmt in formats:
        try:
            await _run_ytdlp_cli_download(url, temp_dir, fmt)
            downloaded_files = list(temp_dir.glob("*"))
            video_files = [
                f
                for f in downloaded_files
                if f.is_file()
                and f.stat().st_size > 0
                and f.suffix.lower() in VIDEO_EXTENSIONS
                and f.stat().st_size <= max_size
            ]
            if video_files:
                return str(video_files[0])
        except Exception as e:
            logger.warning("YouTube fallback format %s failed: %s", fmt, e)
            continue

    raise Exception("Could not download video within size limit")


def _get_ytdlp_binary() -> str:
    return shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"


def _build_ytdlp_base_command() -> list[str]:
    command = [_get_ytdlp_binary(), "--no-playlist", "--no-warnings"]
    if os.path.exists(settings.YTDLP_COOKIES_PATH):
        command.extend(["--cookies", settings.YTDLP_COOKIES_PATH])
    return command


async def _run_ytdlp_cli_json(url: str) -> dict:
    command = _build_ytdlp_base_command() + ["--dump-single-json", "--skip-download", url]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(stderr.decode("utf-8", errors="ignore").strip() or "yt-dlp failed")

    return json.loads(stdout.decode("utf-8", errors="ignore"))


async def _run_ytdlp_cli_download(url: str, temp_dir: Path, fmt: str) -> None:
    output_template = str(temp_dir / "%(id)s.%(ext)s")
    command = _build_ytdlp_base_command() + [
        "-f",
        fmt,
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
        url,
    ]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(
            stderr.decode("utf-8", errors="ignore").strip()
            or stdout.decode("utf-8", errors="ignore").strip()
            or "yt-dlp download failed"
        )
