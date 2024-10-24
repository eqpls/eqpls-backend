# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

try: import LOG  # @UnresolvedImport
except: pass
#===============================================================================
# Import
#===============================================================================
from typing import Any
from .models import SchemaInfo, Search


#===============================================================================
# Implement
#===============================================================================
class DriverBase:

    def __init__(self, control): self.control = control

    async def connect(self, *args, **kargs): return self

    async def disconnect(self): pass


class KeyValueDriverBase(DriverBase):

    def __init__(self, control): DriverBase.__init__(self, control)

    async def read(self, key:str, *args, **kargs): pass

    async def write(self, key:str, val:Any, *args, **kargs): pass

    async def delete(self, key:str, *args, **kargs): pass


class NetworkDriverBase(DriverBase):

    def __init__(self, control): DriverBase.__init__(self, control)

    async def listen(self, address:str, handler, *args, **kargs): pass

    async def recv(self, *args, **kargs): pass

    async def send(self, address:str, key:str, val:Any, *args, **kargs): pass


class ModelDriverBase(DriverBase):

    def __init__(self, control): DriverBase.__init__(self, control)

    async def registerModel(self, schemaInfo:SchemaInfo, *args, **kargs): pass

    async def read(self, schemaInfo:SchemaInfo, id:str): pass

    async def search(self, schemaInfo:SchemaInfo, search:Search): pass

    async def count(self, schemaInfo:SchemaInfo, search:Search): pass

    async def create(self, schemaInfo:SchemaInfo, *models): pass

    async def update(self, schemaInfo:SchemaInfo, *models): pass

    async def delete(self, schemaInfo:SchemaInfo, id:str): pass
