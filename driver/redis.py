# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import json
import redis.asyncio as redis

from typing import Any

from common import BaseSchema, KeyValueDriverBase, NetworkDriverBase, ModelDriverBase


#===============================================================================
# Implement
#===============================================================================
class RedisAuthn(KeyValueDriverBase):

    def __init__(self, config):
        ModelDriverBase.__init__(self, config)
        self._redisHostname = config['redis']['hostname']
        self._redisHostport = int(config['redis']['port'])
        self._redisDatabase = int(config['redis:authn']['database'])
        self._redisExpire = int(config['redis:authn']['expire'])
        self._redisConn = None

    async def connect(self, *args, **kargs):
        if not self._redisConn:
            self._redisConn = await redis.Redis(
                host=self._redisHostname,
                port=self._redisHostport,
                db=self._redisDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self._redisConn:
            try: await self._redisConn.aclose()
            except: pass
            self._redisConn = None

    async def read(self, key:str, *args, **kargs):
        async with self._redisConn.pipeline(transaction=True) as pipeline:
            result = (await pipeline.get(key).expire(key, self._redisExpire).execute())[0]
        if result: result = json.loads(result)
        return result

    async def write(self, key:str, val:Any, *args, **kargs):
        async with self._redisConn.pipeline(transaction=True) as pipeline:
            await pipeline.set(key, json.dumps(val, separators=(',', ':')), self._redisExpire).execute()

    async def delete(self, key:str, *args, **kargs):
        await self._redisConn.delete(key)


class RedisQueue(NetworkDriverBase):

    def __init__(self, config):
        ModelDriverBase.__init__(self, config)
        self._redisHostname = config['redis']['hostname']
        self._redisHostport = int(config['redis']['port'])
        self._redisDatabase = int(config['redis:queue']['database'])
        self._redisExpire = int(config['redis:queue']['expire'])
        self._redisConn = None

    async def connect(self, *args, **kargs):
        if not self._redisConn:
            self._redisConn = await redis.Redis(
                host=self._redisHostname,
                port=self._redisHostport,
                db=self._redisDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self._redisConn:
            try: await self._redisConn.aclose()
            except: pass
            self._redisConn = None

    async def listen(self, address:str, *args, **kargs): pass

    async def receive(self, *args, **kargs): pass

    async def send(self, address:str, data:Any, *args, **kargs): pass


class RedisModel(ModelDriverBase):

    def __init__(self, config):
        ModelDriverBase.__init__(self, config)
        self._redisHostname = config['redis']['hostname']
        self._redisHostport = int(config['redis']['port'])
        self._redisDatabase = int(config['redis:model']['database'])
        self._redisExpire = int(config['redis:model']['expire'])
        self._redisConn = None

    async def connect(self, *args, **kargs):
        if not self._redisConn:
            self._redisConn = await redis.Redis(
                host=self._redisHostname,
                port=self._redisHostport,
                db=self._redisDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self._redisConn:
            try: await self._redisConn.aclose()
            except: pass
            self._redisConn = None

    async def registerModel(self, schema:BaseSchema, *args, **kargs):
        info = schema.getSchemaInfo()
        if 'expire' not in info.cache or not info.cache['expire']: info.cache['expire'] = self._redisExpire

    async def read(self, schema:BaseSchema, id:str):
        info = schema.getSchemaInfo()
        async with self._redisConn.pipeline(transaction=True) as pipeline:
            model = (await pipeline.get(id).expire(id, info.cache['expire']).execute())[0]
        if model: model = json.loads(model)
        return model

    async def __set_redis_data__(self, schema, models):
        info = schema.getSchemaInfo()
        expire = info.cache['expire']
        async with self._redisConn.pipeline(transaction=True) as pipeline:
            for model in models: pipeline.set(model['id'], json.dumps(model, separators=(',', ':')), expire)
            await pipeline.execute()

    async def create(self, schema:BaseSchema, *models):
        if models: await self.__set_redis_data__(schema, models)

    async def update(self, schema:BaseSchema, *models):
        if models: await self.__set_redis_data__(schema, models)

    async def delete(self, schema:BaseSchema, id:str):
        await self._redisConn.delete(id)
