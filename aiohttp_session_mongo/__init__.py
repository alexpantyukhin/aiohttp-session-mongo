from aiohttp_session import AbstractStorage, Session
from datetime import datetime, timedelta
import uuid
import asyncio

__version__ = '0.0.1'


class MongoStorage(AbstractStorage):
    def __init__(self, collection, *, cookie_name="AIOHTTP_SESSION",
                 domain=None, max_age=None, path='/',
                 delete_expired_every=None, secure=None, httponly=True,
                 key_factory=lambda: uuid.uuid4().hex,
                 encoder=lambda x: x, decoder=lambda x: x):
        super().__init__(cookie_name=cookie_name, domain=domain,
                         max_age=max_age, path=path, secure=secure,
                         httponly=httponly,
                         encoder=encoder, decoder=decoder)

        self._delete_expired_every = delete_expired_every
        self._collection = collection
        self._key_factory = key_factory
        self._task_delete_expired = None

        if self._delete_expired_every is not None:
            self._call_later_delete_expired_sessions()

    async def load_session(self, request):
        cookie = self.load_cookie(request)
        if cookie is None:
            return Session(None, data=None, new=True, max_age=self.max_age)
        else:
            key = str(cookie)
            stored_key = (self.cookie_name + '_' + key).encode('utf-8')
            data_row = await self._collection.find_one(
                filter={
                    '$and': [
                        {'key': stored_key},
                        {
                            '$or': [
                                {'expire': {'$exists': False}},
                                {'expire': {'$lt': datetime.utcnow()}}]
                        }]
                })

            if data_row is None:
                return Session(None, data=None,
                               new=True, max_age=self.max_age)

            try:
                data = self._decoder(data_row['data'])
            except ValueError:
                data = None
            return Session(key, data=data, new=False, max_age=self.max_age)

    def _delete_expired_sessions(self):
        asyncio.get_event_loop().call_soon(self._collection.delete_many(
            {'expire': {'$lt': datetime.utcnow()}}
        ))

        self._call_later_delete_expired_sessions()

    def _call_later_delete_expired_sessions(self):
        self._task_delete_expired = asyncio.get_event_loop().call_later(
            self._delete_expired_every,
            self._delete_expired_sessions
        )

    def finalize(self):
        if self._task_delete_expired is not None:
            self._task_delete_expired.cancel()

    async def save_session(self, request, response, session):
        key = session.identity
        if key is None:
            key = self._key_factory()
            self.save_cookie(response, key,
                             max_age=session.max_age)
        else:
            if session.empty:
                self.save_cookie(response, '',
                                 max_age=session.max_age)
            else:
                key = str(key)
                self.save_cookie(response, key,
                                 max_age=session.max_age)

        data = self._encoder(self._get_session_data(session))
        expire = datetime.utcnow() + timedelta(seconds=session.max_age) \
            if session.max_age is not None else 0
        stored_key = (self.cookie_name + '_' + key).encode('utf-8')
        await self._collection.update_one(
            {'key': stored_key},
            {
                "$set":
                    {
                        'key': stored_key,
                        'data': data,
                        'expire': expire
                    }
            },
            upsert=True)
