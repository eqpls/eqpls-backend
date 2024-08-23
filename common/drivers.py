# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from typing import Any
from pydantic import BaseModel


#===============================================================================
# Implement
#===============================================================================
class DriverBase:

    def __init__(self, config):
        self.config = config

    async def connect(self, *args, **kargs): return self

    async def disconnect(self): pass


class AuthDriverBase(DriverBase):

    def __init__(self, config): DriverBase.__init__(self, config)

    async def getAuthInfo(self, org:str, token:str): pass

    async def createOrg(self, org:dict): return org

    async def updateOrg(self, org:dict): return org

    async def deleteOrg(self, org:dict): return org

    async def createRole(self, role:dict): return role

    async def updateRole(self, role:dict): return role

    async def deleteRole(self, role:dict): return role

    async def createGroup(self, group:dict): return group

    async def updateGroup(self, group:dict): return group

    async def deleteGroup(self, group:dict): return group

    async def createAccount(self, account:dict): return account

    async def updateAccount(self, account:dict): return account

    async def updatePassword(self, account:dict, password:str): return account

    async def deleteAccount(self, account:dict): return account


class KeyValueDriverBase(DriverBase):

    def __init__(self, config): DriverBase.__init__(self, config)

    async def read(self, key:str, *args, **kargs): pass

    async def write(self, key:str, val:Any, *args, **kargs): pass

    async def delete(self, key:str, *args, **kargs): pass


class NetworkDriverBase(DriverBase):

    def __init__(self, config): DriverBase.__init__(self, config)

    async def listen(self, address:str, *args, **kargs): pass

    async def receive(self, *args, **kargs): pass

    async def send(self, address:str, data:Any, *args, **kargs): pass


class ModelDriverBase(DriverBase):

    def __init__(self, config): DriverBase.__init__(self, config)

    async def registerModel(self, schema:BaseModel, *args, **kargs): pass

    async def read(self, schema:BaseModel, id:str): pass

    async def create(self, schema:BaseModel, *models): pass

    async def update(self, schema:BaseModel, *models): pass

    async def delete(self, schema:BaseModel, id:str): pass
