=====================
aiohttp_session_mongo
=====================

.. image:: https://travis-ci.org/alexpantyukhin/aiohttp-session-mongo.svg?branch=master
    :target: https://travis-ci.org/alexpantyukhin/aiohttp-session-mongo

.. image:: https://codecov.io/github/alexpantyukhin/aiohttp-session-mongo/coverage.svg?branch=master
    :target: https://codecov.io/github/alexpantyukhin/aiohttp-session-mongo

The library provides mongo sessions store for `aiohttp.web`__.

.. _aiohttp_web: https://aiohttp.readthedocs.io/en/latest/web.html

__ aiohttp_web_

Usage
-----

A trivial usage example:

.. code:: python

    import time
    from aiohttp import web
    from aiohttp_session import setup, get_session
    from aiohttp_session_mongo import MongoStorage
    import motor.motor_asyncio as aiomotor
    import asyncio


    async def handler(request):
        session = await get_session(request)
        last_visit = session['last_visit'] if 'last_visit' in session else None
        session['last_visit'] = time.time()
        text = 'Last visited: {}'.format(last_visit)
        return web.Response(text=text)


    async def init_mongo(loop):
        url = "mongodb://localhost:27017"
        conn = aiomotor.AsyncIOMotorClient(
            url, maxPoolSize=2, io_loop=loop)
        db = 'my_db'
        return conn[db]


    async def setup_mongo(app, loop):
        db = await init_mongo(loop)

        async def close_mongo(app):
            db.client.close()

        app.on_cleanup.append(close_mongo)
        return db


    async def make_app():
        app = web.Application()
        loop = asyncio.get_event_loop()

        db = await setup_mongo(app, loop)
        session_collection = db['sessions']

        max_age = 3600 * 24 * 365 # 1 year
        setup(app, MongoStorage(session_collection, max_age=max_age))

        app.router.add_get('/', handler)
        return app


    web.run_app(make_app())
