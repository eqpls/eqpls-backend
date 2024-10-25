# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

try: import LOG  # @UnresolvedImport
except: pass
#===============================================================================
# Import
#===============================================================================
import json
import traceback
import redis.asyncio as redis
from typing import Any
from common import runBackground, DriverBase, KeyValueDriverBase, ModelDriverBase, SchemaInfo


#===============================================================================
# Implement
#===============================================================================
class RedisAccount(KeyValueDriverBase):

    def __init__(self, control):
        KeyValueDriverBase.__init__(self, control)
        rdConf = self.control.config['redis']
        raConf = self.control.config['redis:account']
        self.raHostname = rdConf['hostname']
        self.raHostport = rdConf['hostport']
        self.raDatabase = int(raConf['database'])
        self.raExpire = int(raConf['expire'])
        self.raConn = None

    async def initialize(self, *args, **kargs): await self.connect()

    async def connect(self, *args, **kargs):
        await self.disconnect()
        if not self.raConn:
            self.raConn = await redis.Redis(
                host=self.raHostname,
                port=self.raHostport,
                db=self.raDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self.raConn:
            try: await self.raConn.aclose()
            except: pass
            self.raConn = None

    async def read(self, key:str, *args, **kargs):
        async with self.raConn.pipeline(transaction=True) as pipeline:
            result = (await pipeline.get(key).expire(key, self.raExpire).execute())[0]
        if result: result = json.loads(result)
        return result

    async def write(self, key:str, val:Any, *args, **kargs):
        async with self.raConn.pipeline(transaction=True) as pipeline:
            await pipeline.set(key, json.dumps(val, separators=(',', ':')), self.raExpire).execute()

    async def delete(self, key:str, *args, **kargs):
        await self.raConn.delete(key)


class RedisModel(ModelDriverBase):

    def __init__(self, control):
        ModelDriverBase.__init__(self, control)
        rdConf = self.control.config['redis']
        rmConf = self.control.config['redis:model']
        self.rmHostname = rdConf['hostname']
        self.rmHostport = rdConf['hostport']
        self.rmDatabase = int(rmConf['database'])
        self.rmExpire = int(rmConf['expire'])
        self.rmConn = None

    async def initialize(self, *args, **kargs): await self.connect()

    async def connect(self, *args, **kargs):
        await self.disconnect()
        if not self.rmConn:
            self.rmConn = await redis.Redis(
                host=self.rmHostname,
                port=self.rmHostport,
                db=self.rmDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self.rmConn:
            try: await self.rmConn.aclose()
            except: pass
            self.rmConn = None

    async def registerModel(self, schemaInfo:SchemaInfo, *args, **kargs):
        if 'expire' not in schemaInfo.cache or not schemaInfo.cache['expire']: schemaInfo.cache['expire'] = self.rmExpire

    async def read(self, schemaInfo:SchemaInfo, id:str):
        async with self.rmConn.pipeline(transaction=True) as pipeline:
            model = (await pipeline.get(id).expire(id, schemaInfo.cache['expire']).execute())[0]
        if model: model = json.loads(model)
        return model

    async def __set_redis_data__(self, schemaInfo:SchemaInfo, models):
        expire = schemaInfo.cache['expire']
        async with self.rmConn.pipeline(transaction=True) as pipeline:
            for model in models: pipeline.set(model['id'], json.dumps(model, separators=(',', ':')), expire)
            await pipeline.execute()

    async def create(self, schemaInfo:SchemaInfo, *models):
        if models: await self.__set_redis_data__(schemaInfo, models)

    async def update(self, schemaInfo:SchemaInfo, *models):
        if models: await self.__set_redis_data__(schemaInfo, models)

    async def delete(self, schemaInfo:SchemaInfo, id:str):
        await self.rmConn.delete(id)


class RedisQueue(DriverBase):

    def __init__(self, control):
        DriverBase.__init__(self, control)
        rdConf = self.control.config['redis']
        rqConf = self.control.config['redis:queue']
        self.rqTenant = self.control.tenant
        self.rqPattern = f'{self.rqTenant}:*:*'
        self.rqHostname = rdConf['hostname']
        self.rqHostport = rdConf['hostport']
        self.rqDatabase = int(rqConf['database'])
        self.rqExpire = int(rqConf['expire'])
        self.rqConn = None

    async def initialize(self, *args, **kargs): await self.connect()

    async def connect(self, *args, **kargs):
        await self.disconnect()
        if not self.rqConn:
            self.rqConn = await redis.Redis(
                host=self.rqHostname,
                port=self.rqHostport,
                db=self.rqDatabase,
                decode_responses=True
            )
        return self

    async def disconnect(self):
        if self.rqConn:
            try: await self.rqConn.aclose()
            except: pass
            self.rqConn = None

    async def subscribe(self, handler):
        await runBackground(self.__subscribe__(handler))

    async def __subscribe__(self, handler):
        async with self.rqConn.pubsub() as pubsub:
            await pubsub.psubscribe(self.rqPattern)
            while True:
                try: message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10)
                except Exception as e: LOG.DEBUG(e)
                else:
                    if message is not None:
                        try:
                            _, category, target = message['channel'].split(':')
                            key, val = json.loads(message['data'])
                            await handler(category, target, key, val)
                        except Exception as e:
                            LOG.ERROR(e)
                            if LOG.isDebugMode(): LOG.DEBUG(traceback.extract_stack()[:-1])

    async def publish(self, category:str, target:str, key:str, val:Any):
        await self.rqConn.publish(f'{self.rqTenant}:{category}:{target}', json.dumps([key, val], separators=(',', ':')))
