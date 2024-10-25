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
from common import ModelControl, getRandomLower
from driver.redis import RedisAccount
from driver.minio import Minio
from schema.data import GroupBucket, UserBucket


#===============================================================================
# Implement
#===============================================================================
class Control(ModelControl):

    def __init__(self, path):
        ModelControl.__init__(self, path, RedisAccount)
        self.minio = Minio(self)
        self.srefGroupBucket = GroupBucket.getSchemaInfo().sref
        self.srefUserBucket = UserBucket.getSchemaInfo().sref

    async def startup(self):
        await self.minio.initialize()
        await self.registerModel(
            GroupBucket,
            'uerp',
            createHandler=self.createGroupBucket,
            updateHandler=self.updateBucket,
            deleteHandler=self.deleteBucket
        )
        await self.registerModel(
            UserBucket,
            'uerp',
            createHandler=self.createUserBucket,
            updateHandler=self.updateBucket,
            deleteHandler=self.deleteBucket
        )

    async def createGroupBucket(self, model, token=None):
        model.name = getRandomLower(12)
        model.externalId = await self.minio.createGroupBucket(model.owner, model.name, model.quota)

    async def createUserBucket(self, model, token=None):
        model.name = getRandomLower(12)
        model.externalId = await self.minio.createUserBucket(model.owner, model.name, model.quota)

    async def updateBucket(self, model, origin, token=None):
        model.owner = origin.owner
        model.externalId = origin.externalId
        await self.minio.updateBucket(model.externalId, model.quota)

    async def deleteBucket(self, model, token=None):
        await self.minio.deleteBucket(model.externalId)
