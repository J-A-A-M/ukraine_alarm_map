import os
import uvicorn
import logging
import json
import asyncio
import httpx
from datetime import datetime, timedelta

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route
from starlette.exceptions import HTTPException
from starlette.requests import Request

debug_level = os.environ.get("LOGGING") or "INFO"
debug = os.environ.get("DEBUG") or False
port = int(os.environ.get("PORT") or 8090)
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
memcached_port = int(os.environ.get("MEMCACHED_PORT") or 11211)
shared_path = os.environ.get("SHARED_PATH") or "/shared_data"
shared_beta_path = os.environ.get("SHARED_BETA_PATH") or "/shared_beta_data"
github_token = os.environ.get("GITHUB_TOKEN")  # Optional: для підвищення ліміту API

if not shared_path or not os.path.isdir(shared_path):
    raise ValueError(f"SHARED_PATH має вказувати на існуючу директорію: {shared_path}")

if not shared_beta_path or not os.path.isdir(shared_beta_path):
    raise ValueError(f"SHARED_BETA_PATH має вказувати на існуючу директорію: {shared_beta_path}")

if not isinstance(port, int) or not (1024 <= port <= 65535):
    raise ValueError(f"PORT має бути цілим числом між 1024 та 65535: {port}")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

# Кеш для списку релізів
releases_cache = {
    "data": None,
    "timestamp": None,
    "ttl": timedelta(minutes=60)  # Кешуємо на 60 хвилин
}

# Кеш для списку бета-версій
beta_releases_cache = {
    "data": None,
    "timestamp": None,
    "ttl": timedelta(minutes=60)  # Кешуємо на 60 хвилин
}

HTML_404_PAGE = """page not found"""
HTML_500_PAGE = """request error"""


async def not_found(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_404_PAGE, status_code=404)


async def server_error(request: Request, exc: HTTPException):
    logger.debug(f"Request time: {exc.args}")
    return HTMLResponse(content=HTML_500_PAGE, status_code=500)


exception_handlers = {404: not_found, 500: server_error}


def bin_sort(bin):
    try:
        if bin.startswith("latest"):
            return (100, 0, 0, 0)
        version = bin.removesuffix(".bin")
        fw_beta = version.split("-")
        fw = fw_beta[0]
        if len(fw_beta) == 1:
            beta = 10000
        else:
            beta = int(fw_beta[1].removeprefix("b"))

        major_minor_patch = fw.split(".")
        major = int(major_minor_patch[0])
        if len(major_minor_patch) == 1:
            minor = 0
            patch = 0
        elif len(major_minor_patch) == 2:
            minor = int(major_minor_patch[1])
            patch = 0
        else:
            minor = int(major_minor_patch[1])
            patch = int(major_minor_patch[2])

        return (major, minor, patch, beta)
    except (ValueError, AttributeError, IndexError) as e:
        # Якщо не вдається розпарсити версію, повертаємо мінімальний пріоритет
        logger.debug(f"Cannot parse version from '{bin}': {e}")
        return (0, 0, 0, 0)


async def main(request):
    response = """
    <!DOCTYPE html>
    <html lang='en'>
    </html>
    """
    return HTMLResponse(response)


async def fetch_github_releases(filter_func):
    """Отримує релізи з GitHub та фільтрує .bin файли згідно filter_func. Повертає список (filename, download_url)"""
    try:
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
            
        async with httpx.AsyncClient() as client:
            # Отримуємо всі релізи з пагінацією (до 100 на сторінку)
            response = await client.get(
                "https://api.github.com/repos/J-A-A-M/ukraine_alarm_map/releases",
                headers=headers,
                params={"per_page": 100},  # Максимум релізів на запит
                timeout=10.0
            )
            response.raise_for_status()
            releases = response.json()
            
            # Логуємо інформацію про ліміти та кількість релізів
            if "X-RateLimit-Remaining" in response.headers:
                logger.info(f"GitHub API rate limit remaining: {response.headers['X-RateLimit-Remaining']}/{response.headers.get('X-RateLimit-Limit', 'unknown')}")
            logger.info(f"Fetched {len(releases)} releases from GitHub")
            
            files_with_urls = []
            for release in releases:
                if "assets" in release:
                    for asset in release["assets"]:
                        name = asset["name"]
                        if name.endswith(".bin") and filter_func(name):
                            files_with_urls.append({
                                "name": name,
                                "url": asset["browser_download_url"]
                            })
            
            logger.info(f"Filtered {len(files_with_urls)} .bin files")
            # Сортуємо за версією у зворотному порядку (новіші спочатку)
            return sorted(files_with_urls, key=lambda x: bin_sort(x["name"]), reverse=True)
    except Exception as e:
        logger.error(f"Error fetching releases from GitHub: {e}")
        return None


async def list(request):
    # Перевіряємо кеш
    now = datetime.now()
    if (releases_cache["data"] is not None and 
        releases_cache["timestamp"] is not None and 
        now - releases_cache["timestamp"] < releases_cache["ttl"]):
        logger.debug("Returning cached releases list")
        return JSONResponse(releases_cache["data"])
    
    # Фільтр для релізних версій (без бета та спеціальних білдів)
    def release_filter(name):
        return ("JAAM" in name and
                "-b" not in name and 
                "C3" not in name and 
                "S3" not in name and 
                "lite" not in name.lower())
    
    files_data = await fetch_github_releases(release_filter)
    
    # Обмежуємо до 5 найновіших релізів
    files_data = files_data[:5]
    
    # Зберігаємо повну інформацію в кеш
    releases_cache["data"] = files_data
    releases_cache["timestamp"] = now
    
    # Повертаємо тільки назви файлів
    return JSONResponse([f["name"] for f in files_data])


async def list_beta(request):
    # Перевіряємо кеш
    now = datetime.now()
    if (beta_releases_cache["data"] is not None and 
        beta_releases_cache["timestamp"] is not None and 
        now - beta_releases_cache["timestamp"] < beta_releases_cache["ttl"]):
        logger.debug("Returning cached beta releases list")
        return JSONResponse(beta_releases_cache["data"])
    
    # Фільтр для бета-версій (лише з -b)
    def beta_filter(name):
        return ("JAAM" in name and 
                "-b" in name and 
                "C3" not in name and 
                "S3" not in name and 
                "lite" not in name.lower())
    
    files_data = await fetch_github_releases(beta_filter)

    # Обмежуємо до 10 найновіших бета-версій
    files_data = files_data[:10]

    # Зберігаємо повну інформацію в кеш
    beta_releases_cache["data"] = files_data
    beta_releases_cache["timestamp"] = now
    
    # Повертаємо тільки назви файлів
    return JSONResponse([f["name"] for f in files_data])


async def update(request):
    from starlette.responses import RedirectResponse
    
    filename = request.path_params["filename"]
    
    # Перевіряємо кеш релізів
    if releases_cache["data"] is None:
        # Якщо кеш порожній, отримуємо дані
        def release_filter(name):
            return ("JAAM" in name and
                    "-b" not in name and 
                    "C3" not in name and 
                    "S3" not in name and 
                    "lite" not in name.lower())
        
        files_data = await fetch_github_releases(release_filter)
        if files_data:
            releases_cache["data"] = files_data[:5]
            releases_cache["timestamp"] = datetime.now()
    
    files_data = releases_cache["data"] or []
    
    if filename == "latest" or filename == "jaam":
        # Повертаємо перший (найновіший) файл
        if files_data:
            return RedirectResponse(url=files_data[0]["url"])
        raise HTTPException(status_code=404, detail="No releases found")
    else:
        # Шукаємо конкретний файл в кеші
        target_filename = f"{filename}.bin"
        for file_info in files_data:
            if file_info["name"] == target_filename:
                return RedirectResponse(url=file_info["url"])
        raise HTTPException(status_code=404, detail=f"File {target_filename} not found")


async def update_board(request):
    return FileResponse(f'{shared_path}/{request.path_params["board"]}/{request.path_params["filename"]}.bin')


async def update_beta(request):
    if request.path_params["filename"] == "latest_beta":
        filenames = sorted(
            [
                file
                for file in os.listdir(shared_beta_path)
                if (os.path.isfile(os.path.join(shared_beta_path, file)) and file.endswith(".bin"))
            ],
            key=bin_sort,
            reverse=True,
        )
        filenames = [filename for filename in filenames if not filename.startswith("4.")]
        return FileResponse(f"{shared_beta_path}/{filenames[0]}")
    if request.path_params["filename"] == "jaam_beta":
        filenames = sorted(
            [
                file
                for file in os.listdir(shared_path)
                if (os.path.isfile(os.path.join(shared_path, file)) and file.endswith(".bin"))
            ],
            key=bin_sort,
            reverse=True,
        )
        return FileResponse(f"{shared_path}/{filenames[0]}")
    return FileResponse(f'{shared_beta_path}/{request.path_params["filename"]}.bin')


async def update_beta_board(request):
    return FileResponse(f'{shared_beta_path}/{request.path_params["board"]}/{request.path_params["filename"]}.bin')


async def update_cache():
    filenames = sorted(
        [
            file
            for file in os.listdir(shared_path)
            if (os.path.isfile(os.path.join(shared_path, file)) and file.endswith(".bin"))
        ]
    )
    beta_filenames = sorted(
        [
            file
            for file in os.listdir(shared_beta_path)
            if (os.path.isfile(os.path.join(shared_beta_path, file)) and file.endswith(".bin"))
        ]
    )
    # s3_filenames = sorted(
    #     [
    #         file
    #         for file in os.listdir(f"{shared_path}/s3/")
    #         if (os.path.isfile(os.path.join(f"{shared_path}/s3/", file)) and file.endswith(".bin"))
    #     ],
    #     key=bin_sort,
    #     reverse=True,
    # )
    s3_beta_filenames = sorted(
        [
            file
            for file in os.listdir(f"{shared_beta_path}/s3/")
            if (os.path.isfile(os.path.join(f"{shared_beta_path}/s3/", file)) and file.endswith(".bin"))
        ],
        key=bin_sort,
        reverse=True,
    )
    # c3_filenames = sorted(
    #     [
    #         file
    #         for file in os.listdir(f"{shared_path}/c3/")
    #         if (os.path.isfile(os.path.join(f"{shared_path}/c3/", file)) and file.endswith(".bin"))
    #     ],
    #     key=bin_sort,
    #     reverse=True,
    # )
    c3_beta_filenames = sorted(
        [
            file
            for file in os.listdir(f"{shared_beta_path}/c3/")
            if (os.path.isfile(os.path.join(f"{shared_beta_path}/c3/", file)) and file.endswith(".bin"))
        ],
        key=bin_sort,
        reverse=True,
    )
    #await mc.set(b"bins", json.dumps(filenames).encode("utf-8"))
    #await mc.set(b"test_bins", json.dumps(beta_filenames).encode("utf-8"))
    # await mc.set(b"s3_bins", json.dumps(s3_filenames).encode("utf-8"))
    #await mc.set(b"s3_test_bins", json.dumps(s3_beta_filenames).encode("utf-8"))
    # await mc.set(b"c3_bins", json.dumps(c3_filenames).encode("utf-8"))
    #await mc.set(b"c3_test_bins", json.dumps(c3_beta_filenames).encode("utf-8"))


app = Starlette(
    debug=debug,
    exception_handlers=exception_handlers,
    routes=[
        Route("/", main),
        Route("/list", list),
        Route("/betalist", list_beta),
        Route("/{filename}.bin", update),
        Route("/beta/{filename}.bin", update_beta),
        Route("/{board}/{filename}.bin", update_board),
        Route("/beta/{board}/{filename}.bin", update_beta_board),
    ],
)


if __name__ == "__main__":
    #asyncio.run(update_cache())
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips=["*"])
