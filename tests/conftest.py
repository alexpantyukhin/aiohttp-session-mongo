import asyncio
import gc
import pytest
import sys
import time
import uuid
from docker import from_env as docker_from_env
import socket
import motor.motor_asyncio as aiomotor
from pymongo.errors import ServerSelectionTimeoutError


@pytest.fixture(scope='session')
def unused_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope='session')
def loop(request):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    yield loop

    if not loop._closed:
        loop.call_soon(loop.stop)
        loop.run_forever()
        loop.close()
    gc.collect()
    asyncio.set_event_loop(None)


@pytest.fixture(scope='session')
def session_id():
    """Unique session identifier, random string."""
    return str(uuid.uuid4())


@pytest.fixture(scope='session')
def docker():
    client = docker_from_env(version='auto')
    return client


@pytest.fixture(scope='session')
def mongo_server(docker, session_id, loop, request):

    image = 'mongo:{}'.format('latest')

    if sys.platform.startswith('darwin'):
        port = unused_port()
    else:
        port = None

    container = docker.containers.run(
        image=image,
        detach=True,
        name='mongo-test-server-{}-{}'.format('latest', session_id),
        ports={
            '27017/tcp': port,
        },
        environment={
            'http.host': '0.0.0.0',
            'transport.host': '127.0.0.1',
        },
    )

    if sys.platform.startswith('darwin'):
        host = '0.0.0.0'
    else:
        inspection = docker.api.inspect_container(container.id)
        host = inspection['NetworkSettings']['IPAddress']
        port = 27017

    delay = 0.1
    for i in range(20):
        try:
            mongo_uri = "mongodb://{}:{}".format(host, port)
            conn = aiomotor.AsyncIOMotorClient(
                mongo_uri,
                io_loop=loop)
            loop.run_until_complete(conn.list_databases())
            break
        except ServerSelectionTimeoutError:
            time.sleep(delay)
            delay *= 2
    else:
        pytest.fail("Cannot start mongo server")

    yield {'host': host,
           'port': port,
           'container': container}

    container.kill(signal=9)
    container.remove(force=True)


@pytest.fixture
def mongo_params(mongo_server):
    return dict(host=mongo_server['host'],
                port=mongo_server['port'])


@pytest.fixture
def mongo(loop, mongo_params):

    async def init_mogo(loop):
        url = "mongodb://{}:{}".format(
            mongo_params['host'], mongo_params['port']
        )
        conn = aiomotor.AsyncIOMotorClient(
            url, maxPoolSize=2, io_loop=loop)
        return conn

    conn = loop.run_until_complete(init_mogo(loop))

    db = 'test_db'
    return conn[db]


@pytest.fixture
def mongo_collection(mongo):
    name = 'posts'
    return mongo[name]
