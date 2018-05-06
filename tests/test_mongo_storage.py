import uuid
import time

from aiohttp import web
from aiohttp_session import Session, session_middleware, get_session
from aiohttp_session_mongo import MongoStorage


def create_app(handler, mongo, max_age=None,
               key_factory=lambda: uuid.uuid4().hex):
    middleware = session_middleware(
        MongoStorage(mongo, max_age=max_age, key_factory=key_factory))
    app = web.Application(middlewares=[middleware])
    app.router.add_route('GET', '/', handler)
    return app


async def make_cookie(client, mongo_collection, data):
    session_data = {
        'session': data,
        'created': int(time.time())
    }
    key = uuid.uuid4().hex
    storage_key = ('AIOHTTP_SESSION_' + key).encode('utf-8')

    await mongo_collection.update_one(
        {'key': storage_key},
        {"$set":
            {
                'key': storage_key,
                'data': session_data
            }},
        upsert=True)
    client.session.cookie_jar.update_cookies({'AIOHTTP_SESSION': key})


async def make_cookie_with_bad_value(client, mongo_collection):
    key = uuid.uuid4().hex
    storage_key = ('AIOHTTP_SESSION_' + key).encode('utf-8')
    await mongo_collection.update_one(
        {'key': storage_key},
        {"$set": {'key': storage_key}},
        upsert=True)
    client.session.cookie_jar.update_cookies({'AIOHTTP_SESSION': key})


async def load_cookie(client, mongo_collection):
    cookies = client.session.cookie_jar.filter_cookies(client.make_url('/'))
    key = cookies['AIOHTTP_SESSION']
    storage_key = ('AIOHTTP_SESSION_' + key.value).encode('utf-8')
    data_row = await mongo_collection.find_one(
        filter={'key': storage_key}
    )

    return data_row['data']


async def test_create_new_session(aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        assert isinstance(session, Session)
        assert session.new
        assert not session._changed
        assert {} == session
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    resp = await client.get('/')
    assert resp.status == 200


async def test_load_existing_session(aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        assert isinstance(session, Session)
        assert not session.new
        assert not session._changed
        assert {'a': 1, 'b': 12} == session
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    await make_cookie(client, mongo_collection, {'a': 1, 'b': 12})
    resp = await client.get('/')
    assert resp.status == 200


async def test_load_bad_session(aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        assert isinstance(session, Session)
        assert not session.new
        assert not session._changed
        assert {} == session
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    await make_cookie_with_bad_value(client, mongo_collection)
    resp = await client.get('/')
    assert resp.status == 200


async def test_change_session(aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        session['c'] = 3
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    await make_cookie(client, mongo_collection, {'a': 1, 'b': 2})
    resp = await client.get('/')
    assert resp.status == 200

    value = await load_cookie(client, mongo_collection)
    assert 'session' in value
    assert 'a' in value['session']
    assert 'b' in value['session']
    assert 'c' in value['session']
    assert 'created' in value
    assert value['session']['a'] == 1
    assert value['session']['b'] == 2
    assert value['session']['c'] == 3
    morsel = resp.cookies['AIOHTTP_SESSION']
    assert morsel['httponly']
    assert '/' == morsel['path']


async def test_clear_cookie_on_session_invalidation(
        aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        session.invalidate()
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    await make_cookie(client, mongo_collection, {'a': 1, 'b': 2})
    resp = await client.get('/')
    assert resp.status == 200

    value = await load_cookie(client, mongo_collection)
    assert {} == value
    morsel = resp.cookies['AIOHTTP_SESSION']
    assert morsel['path'] == '/'
    assert morsel['expires'] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert morsel['max-age'] == "0"


async def test_create_cookie_in_handler(aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        session['a'] = 1
        session['b'] = 2
        return web.Response(body=b'OK', headers={'HOST': 'example.com'})

    client = await aiohttp_client(create_app(handler, mongo_collection))
    resp = await client.get('/')
    assert resp.status == 200

    value = await load_cookie(client, mongo_collection)
    assert 'session' in value
    assert 'a' in value['session']
    assert 'b' in value['session']
    assert 'created' in value
    assert value['session']['a'] == 1
    assert value['session']['b'] == 2
    morsel = resp.cookies['AIOHTTP_SESSION']
    assert morsel['httponly']
    assert morsel['path'] == '/'

    count = await mongo_collection.count(
        {'key': 'AIOHTTP_SESSION_' + morsel.value}
    )
    assert count > 0


async def test_create_new_session_if_key_doesnt_exists_in_redis(
        aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        assert session.new
        return web.Response(body=b'OK')

    client = await aiohttp_client(create_app(handler, mongo_collection))
    client.session.cookie_jar.update_cookies(
        {'AIOHTTP_SESSION': 'invalid_key'})
    resp = await client.get('/')
    assert resp.status == 200


async def test_create_storate_with_custom_key_factory(
        aiohttp_client, mongo_collection):
    async def handler(request):
        session = await get_session(request)
        session['key'] = 'value'
        assert session.new
        return web.Response(body=b'OK')

    def key_factory():
        return 'test-key'

    client = await aiohttp_client(
        create_app(handler, mongo_collection, 8, key_factory)
    )
    resp = await client.get('/')
    assert resp.status == 200

    assert resp.cookies['AIOHTTP_SESSION'].value == 'test-key'

    value = await load_cookie(client, mongo_collection)
    assert 'key' in value['session']
    assert value['session']['key'] == 'value'
