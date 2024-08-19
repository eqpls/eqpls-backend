# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from common import MeshControl

from schema.secret.certification import Authority, Server
from schema.secret.access import OpenSsh


#===============================================================================
# Implement
#===============================================================================
class Control(MeshControl):

    def __init__(self, modPath):
        MeshControl.__init__(self, modPath)

    async def startup(self):
        await self.registerModel(Authority, 'uerp')
        await self.registerModel(Server, 'uerp')
        await self.registerModel(OpenSsh, 'uerp')

    async def shutdown(self): pass
