# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from common import UerpControl

from driver.redis import RedisAccount, RedisModel, RedisQueue
from driver.elasticsearch import ElasticSearch
from driver.postgresql import PostgreSql

from schema.data import GroupBucket, UserBucket
from schema.secret.certification import Authority, Server
from schema.secret.access import OpenSsh


#===============================================================================
# Implement
#===============================================================================
class Control(UerpControl):

    def __init__(self, path):
        UerpControl.__init__(
            self,
            path=path,
            sessionCacheDriver=RedisAccount,
            queueDriver=RedisQueue,
            cacheDriver=RedisModel,
            searchDriver=ElasticSearch,
            databaseDriver=PostgreSql
        )

    async def startup(self):
        await self.registerModel(GroupBucket)
        await self.registerModel(UserBucket)
        await self.registerModel(Authority)
        await self.registerModel(Server)
        await self.registerModel(OpenSsh)

    async def shutdown(self): pass
