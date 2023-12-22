import os
import json
import uvicorn
import time
import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request

from aiomcache import Client

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

debug = os.environ.get('DEBUG', False)

memcached_host = os.environ.get('MEMCACHED_HOST', 'localhost')
memcached_port = int(os.environ.get('MEMCACHED_PORT', 11211))

shared_path = os.environ.get('SHARED_PATH') or '/shared_data'

mc = Client(memcached_host, memcached_port)

api_clients = {}
image_clients = {}
web_clients = {}


HTML_404_PAGE = '''page not found'''
HTML_500_PAGE = '''request error'''


async def not_found(request: Request, exc: HTTPException):
    logger.debug(f'Request time: {exc.args}')
    return HTMLResponse(content=HTML_404_PAGE)


async def server_error(request: Request, exc: HTTPException):
    logger.debug(f'Request time: {exc.args}')
    return HTMLResponse(content=HTML_500_PAGE)


exception_handlers = {
    404: not_found,
    500: server_error
}


async def main(request):
    response = '''
    <!DOCTYPE html>
    <html lang='en'>
    </html>
    '''
    return HTMLResponse(response)


async def list(request):
    filenames = sorted([file for file in os.listdir(shared_path) if os.path.isfile(os.path.join(shared_path, file))])
    return JSONResponse(filenames)


async def update(request):
    return FileResponse(f'{shared_path}/{request.path_params["filename"]}.bin')


app = Starlette(debug=debug, exception_handlers=exception_handlers, routes=[
    Route('/', main),
    Route('/list', list),
    Route('/{filename}.bin', update),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
