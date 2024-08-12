# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from common import UerpControl

from driver.auth_kc_redis import AuthKeyCloakRedis
from driver.redis import RedisModel
from driver.elasticsearch import ElasticSearch
from driver.postgresql import PostgreSql

from schema.secret.certification import Authority, Server
from schema.secret.access import OpenSsh


#===============================================================================
# Implement
#===============================================================================
class Control(UerpControl):

    def __init__(self, modPath):
        UerpControl.__init__(
            self,
            modPath=modPath,
            authDriver=AuthKeyCloakRedis,
            cacheDriver=RedisModel,
            searchDriver=ElasticSearch,
            databaseDriver=PostgreSql
        )

    async def startup(self):
        await self.registerModel(Authority)
        await self.registerModel(Server)
        await self.registerModel(OpenSsh)

    async def shutdown(self): pass
