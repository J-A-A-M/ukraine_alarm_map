import os
import uvicorn
import logging
import json
import asyncio

from aiomcache import Client

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route
from starlette.exceptions import HTTPException
from starlette.requests import Request

debug_level = os.environ.get("LOGGING") or "INFO"
debug = os.environ.get("DEBUG") or False
port = int(os.environ.get("PORT")) or 8090
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
memcached_port = int(os.environ.get("MEMCACHED_PORT") or 11211)
shared_path = os.environ.get("SHARED_PATH") or "/shared_data"
shared_beta_path = os.environ.get("SHARED_BETA_PATH") or "/shared_beta_data"

if not shared_path or not os.path.isdir(shared_path):
    raise ValueError(f"SHARED_PATH має вказувати на існуючу директорію: {shared_path}")

if not shared_beta_path or not os.path.isdir(shared_beta_path):
    raise ValueError(f"SHARED_BETA_PATH має вказувати на існуючу директорію: {shared_beta_path}")

if not isinstance(port, int) or not (1024 <= port <= 65535):
    raise ValueError(f"PORT має бути цілим числом між 1024 та 65535: {port}")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)

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


async def main(request):
    response = """
    <!DOCTYPE html>
    <html lang='en'>
    </html>
    """
    return HTMLResponse(response)


async def list(request):
    filenames = sorted(
        [
            file
            for file in os.listdir(shared_path)
            if (os.path.isfile(os.path.join(shared_path, file)) and file.endswith(".bin"))
        ]
    )
    return JSONResponse(filenames)


async def list_beta(request):
    filenames = sorted(
        [
            file
            for file in os.listdir(shared_beta_path)
            if (os.path.isfile(os.path.join(shared_beta_path, file)) and file.endswith(".bin"))
        ]
    )
    return JSONResponse(filenames)


async def update(request):
    if request.path_params["filename"] == "latest":
        filenames = sorted(
            [
                file
                for file in os.listdir(shared_path)
                if (os.path.isfile(os.path.join(shared_path, file)) and file.endswith(".bin"))
            ],
            key=bin_sort,
            reverse=True,
        )
        filenames = [filename for filename in filenames if not filename.startswith("4.")]
        return FileResponse(f"{shared_path}/{filenames[0]}")
    if request.path_params["filename"] == "jaam":
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
    return FileResponse(f'{shared_path}/{request.path_params["filename"]}.bin')


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
    mc = Client(memcached_host, memcached_port)
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
    await mc.set(b"bins", json.dumps(filenames).encode("utf-8"))
    await mc.set(b"test_bins", json.dumps(beta_filenames).encode("utf-8"))
    # await mc.set(b"s3_bins", json.dumps(s3_filenames).encode("utf-8"))
    await mc.set(b"s3_test_bins", json.dumps(s3_beta_filenames).encode("utf-8"))
    # await mc.set(b"c3_bins", json.dumps(c3_filenames).encode("utf-8"))
    await mc.set(b"c3_test_bins", json.dumps(c3_beta_filenames).encode("utf-8"))


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
    asyncio.run(update_cache())
    uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips=["*"])
