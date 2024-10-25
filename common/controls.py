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
import os
from typing import Annotated, Any, List, Literal
from pydantic import BaseModel
from stringcase import pathcase
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from aiohttp.client_exceptions import ClientResponseError
from luqum.parser import parser as parseLucene
from .auth import AuthInfo
from .constants import CRUD, LAYER, AAA, AUTH_HEADER
from .exceptions import EpException
from .interfaces import AsyncRest
from .models import ID, Search, BaseSchema, ServiceHealth, ModelStatus, ModelCount
from .schedules import runBackground
from .utils import setEnvironment, getConfig, Logger, getTStamp


#===============================================================================
# Base Control
#===============================================================================
class BaseControl:

    def __init__(self, path:str):
        self.path = os.path.abspath(path)
        self.svcPath = os.path.dirname(self.path)
        self.modPath = os.path.dirname(self.svcPath)
        self.prjPath = os.path.dirname(self.modPath)
        self.module = os.path.basename(self.modPath)

        self.config = getConfig(f'{self.prjPath}/project.ini')
        Logger.register(self.config)

        self.defConf = self.config['default']
        self.modCOnf = self.config[self.module]
        self.title = self.defConf['title']
        self.tenant = self.defConf['tenant']
        self.domain = self.defConf['domain']
        self.endpoint = self.defConf['endpoint']
        self.origins = [origin.strip() for origin in self.defConf['origins'].split(',')] if 'origins' in self.defConf and self.defConf['origins'] else []
        self.version = int(self.defConf['version'])
        self.uri = f'/{pathcase(self.module)}'
        self.uriver = f'{self.uri}/v{self.version}'
        self.stage = self.defConf['stage']

        self.systemAccessKey = self.defConf['system_access_key']
        self.systemSecretKey = self.defConf['system_secret_key']
        self.adminUsername = self.defConf['admin_username']
        self.adminPassword = self.defConf['admin_password']
        self.adminGroupName = self.defConf['admin_group']
        self.adminRoleName = self.defConf['admin_role']
        self.userGroupName = self.defConf['user_group']
        self.userRoleName = self.defConf['user_role']

        self.hostname = self.modCOnf['hostname']
        self.hostport = self.modCOnf['hostport']

        self.api = FastAPI(
            title=self.module,
            docs_url=f'{self.uri}/docs',
            openapi_url=f'{self.uri}/openapi.json',
            separate_input_output_schemas=False
        )
        if self.origins:
            self.api.add_middleware(
                CORSMiddleware,
                allow_origins=self.origins,
                allow_credentials=True,
                allow_methods=['*'],
                allow_headers=['*'],
            )

        LOG.INFO(f'title    = {self.title}')
        LOG.INFO(f'tenant   = {self.tenant}')
        LOG.INFO(f'domain   = {self.domain}')
        LOG.INFO(f'module   = {self.module}')
        LOG.INFO(f'version  = {self.version}')
        LOG.INFO(f'endpoint = {self.endpoint}')
        LOG.INFO(f'hostname = {self.hostname}')
        LOG.INFO(f'hostport = {self.hostport}')
        LOG.INFO(f'uri      = {self.uri}')
        LOG.INFO(f'api      = {self.uriver}')
        LOG.INFO(f'swagger  = {self.uri}/docs')
        LOG.INFO(f'openapi  = {self.uri}/openapi.json')
        LOG.INFO(f'prj path = {self.prjPath}')
        LOG.INFO(f'mod path = {self.modPath}')
        LOG.INFO(f'svc path = {self.svcPath}')

        self.api.router.add_event_handler('startup', self.__startup__)
        self.api.router.add_event_handler('shutdown', self.__shutdown__)

    async def __startup__(self):
        LOG.INFO(f'{self.module} start controller')
        await self.startup()
        LOG.INFO(f'{self.module} controller is started')
        self.api.add_api_route(
            tags=['Internal'],
            name='Health',
            methods=['GET'],
            path='/internal/health',
            endpoint=self.health,
            response_model=ServiceHealth
        )
        LOG.INFO('register health interface')

    async def __shutdown__(self):
        LOG.INFO(f'{self.module} stop controller')
        await self.shutdown()
        LOG.INFO(f'{self.module} controller is finished')

    async def startup(self): pass

    async def shutdown(self): pass

    async def health(self) -> ServiceHealth: return ServiceHealth(title=self.module, status='OK', healthy=True)


#===============================================================================
# Session Control
#===============================================================================
class SessionControl(BaseControl):

    def __init__(self, path:str, accountCacheDriver:Any):
        BaseControl.__init__(self, path)
        accConf = self.config[self.defConf['account_module']]
        accHostname = accConf['hostname']
        accHostport = accConf['hostport']
        self.accountBaseUrl = f'http://{accHostname}:{accHostport}/{accHostname}/v{self.version}'
        self.accountCache = accountCacheDriver(self)

    async def __startup__(self):
        await self.accountCache.connect()
        await BaseControl.__startup__(self)

    async def __shutdown__(self):
        await BaseControl.__shutdown__(self)
        await self.accountCache.disconnect()

    async def getSystemToken(self):
        systemToken = self.accountCache.read('systemToken')
        if systemToken: return systemToken
        raise EpException(500, 'Internal Server Error')

    async def getClientSecret(self, clientId:str) -> str:
        systemToken = await self.getSystemToken()
        async with AsyncRest(self.accountBaseUrl) as req: return await req.get(f'/client/{clientId}/secret', headers={'Authorization': f'Bearer {systemToken}'})

    async def checkBearerToken(self, bearerToken:str) -> AuthInfo:
        authInfo = await self.accountCache.read(bearerToken)
        if not authInfo:
            async with AsyncRest(self.accountBaseUrl) as req: authInfo = await req.get('/authinfo', headers={'Authorization': f'Bearer {bearerToken}'})
        return AuthInfo(**authInfo)

    async def checkAuthorization(self, token:HTTPAuthorizationCredentials) -> AuthInfo:
        return await self.checkBearerToken(token.credentials)

    async def checkCreatable(self, token:HTTPAuthorizationCredentials, sref:str) -> AuthInfo:
        return (await self.checkAuthorization(token)).checkCreate(sref)

    async def checkReadable(self, token:HTTPAuthorizationCredentials, sref:str) -> AuthInfo:
        return (await self.checkAuthorization(token)).checkRead(sref)

    async def checkUpdatable(self, token:HTTPAuthorizationCredentials, sref:str) -> AuthInfo:
        return (await self.checkAuthorization(token)).checkUpdate(sref)

    async def checkDeletable(self, token:HTTPAuthorizationCredentials, sref:str) -> AuthInfo:
        return (await self.checkAuthorization(token)).checkDelete(sref)


#===============================================================================
# Model Control
#===============================================================================
class ModelControl(SessionControl):

    def __init__(self, path:str, cacheAccountDriver:Any):
        SessionControl.__init__(self, path, cacheAccountDriver)
        self.schemaInfoList = []
        self.schemaInfoMap = {}

    async def __startup__(self):
        await SessionControl.__startup__(self)

    async def __shutdown__(self):
        await SessionControl.__shutdown__(self)

    async def registerModel(self, schema:BaseSchema, module:str, createHandler=None, updateHandler=None, deleteHandler=None):
        if module not in self.config: raise Exception(f'{module} is not in configuration')
        modConf = self.config[module]
        modHostname = modConf['hostname']
        modHostport = modConf['hostport']
        schema.setSchemaInfo(
            service=module,
            version=self.version,
            control=self,
            provider=f'http://{modHostname}:{modHostport}',
            createHandler=createHandler,
            updateHandler=updateHandler,
            deleteHandler=deleteHandler
        )
        schemaInfo = schema.getSchemaInfo()
        currPath = schemaInfo.path.replace(f'/{module}/v{self.version}', self.uriver)

        self.schemaInfoList.append(schemaInfo)
        self.schemaInfoMap[currPath] = schemaInfo
        setEnvironment(schemaInfo.sref, schema)

        if createHandler:
            if CRUD.checkCreate(schemaInfo.crud):
                if AAA.checkAuthorization(schemaInfo.aaa):
                    if AAA.checkGroup(schemaInfo.aaa):
                        self.createModelByAuthnGroup.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['POST'], path=currPath, endpoint=self.createModelByAuthnGroup, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                    else:
                        self.createModelByAuth.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['POST'], path=currPath, endpoint=self.createModelByAuth, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                else:
                    self.createModelByAnony.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['POST'], path=currPath, endpoint=self.createModelByAnony, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
            else: raise EpException(500, 'Internal Server Error')

        if updateHandler:
            if CRUD.checkUpdate(schemaInfo.crud):
                if AAA.checkAuthorization(schemaInfo.aaa):
                    self.updateModelByAuth.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['PUT'], path=currPath + '/{id}', endpoint=self.updateModelByAuth, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                else:
                    self.updateModelByAnony.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['PUT'], path=currPath + '/{id}', endpoint=self.updateModelByAnony, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
            else: raise EpException(500, 'Internal Server Error')

        if deleteHandler:
            if CRUD.checkDelete(schemaInfo.crud):
                if AAA.checkAuthorization(schemaInfo.aaa):
                    self.api.add_api_route(methods=['DELETE'], path=currPath + '/{id}', endpoint=self.deleteModelByAuth, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
                else:
                    self.api.add_api_route(methods=['DELETE'], path=currPath + '/{id}', endpoint=self.deleteModelByAnony, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
            else: raise EpException(500, 'Internal Server Error')

        return self

    async def createModelByAuth(
        self,
        request:Request,
        token:AUTH_HEADER,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path']]
            authInfo = await self.checkCreatable(token, schemaInfo.sref)
            model.owner = authInfo.username
            await schemaInfo.createHandler(model, token)
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.post(
                    f"{schemaInfo.path}{'?$publish=true' if publish == '' or publish == 'true' else ''}",
                    headers={'Authorization': f'Bearer {token.credentials}'},
                    json=model.model_dump()
                )
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def createModelByAuthnGroup(
        self,
        request:Request,
        token:AUTH_HEADER,
        model:BaseModel,
        group:Annotated[str, Query(alias='$group', description='group code for access control')],
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path']]
            authInfo = await self.checkCreatable(token, schemaInfo.sref)
            model.owner = authInfo.checkOnlyGroup(group)
            await schemaInfo.createHandler(model, token)
            query = f'?{request.scope["query_string"].decode("latin-1")}' if request.scope['query_string'] else ''
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.post(
                    f'{schemaInfo.path}{query}',
                    headers={'Authorization': f'Bearer {token.credentials}'},
                    json=model.model_dump()
                )
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def createModelByAnony(
        self,
        request:Request,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path']]
            await schemaInfo.createHandler(model)
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.post(
                    f"{schemaInfo.path}{'?$publish=true' if publish == '' or publish == 'true' else ''}",
                    json=model.model_dump()
                )
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def updateModelByAuth(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path'].replace(f'/{id}', '')]
            origin = await schemaInfo.ref.readModelByID(id, token)
            await schemaInfo.updateHandler(model, origin, token)
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.put(
                    f"{origin.uref}{'?$publish=true' if publish == '' or publish == 'true' else ''}",
                    headers={'Authorization': f'Bearer {token.credentials}'},
                    json=model.model_dump()
                )
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def updateModelByAnony(
        self,
        request:Request,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path'].replace(f'/{id}', '')]
            origin = await schemaInfo.ref.readModelByID(id)
            await schemaInfo.updateHandler(model, origin)
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.put(
                    f"{origin.uref}{'?$publish=true' if publish == '' or publish == 'true' else ''}",
                    json=model.model_dump()
                )
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def deleteModelByAuth(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path'].replace(f'/{id}', '')]
            model = await schemaInfo.ref.readModelByID(id, token)
            await schemaInfo.deleteHandler(model, token)
            query = f'?{request.scope["query_string"].decode("latin-1")}' if request.scope['query_string'] else ''
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.delete(f'{model.uref}{query}', headers={'Authorization': f'Bearer {token.credentials}'})
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')

    async def deleteModelByAnony(
        self,
        request:Request,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        try:
            schemaInfo = self.schemaInfoMap[request.scope['path'].replace(f'/{id}', '')]
            model = await schemaInfo.ref.readModelByID(id)
            await schemaInfo.deleteHandler(model)
            query = f'?{request.scope["query_string"].decode("latin-1")}' if request.scope['query_string'] else ''
            async with AsyncRest(schemaInfo.provider) as req:
                return await req.delete(f'{model.uref}{query}')
        except ClientResponseError as e: raise EpException(e.status, e.message)
        except: raise EpException(500, 'Internal Server Error')


#===============================================================================
# Uerp Control
#===============================================================================
class UerpControl(SessionControl):

    def __init__(
        self,
        path:str,
        sessionCacheDriver:Any,
        queueDriver:Any,
        cacheDriver:Any,
        searchDriver:Any,
        databaseDriver:Any,
    ):
        SessionControl.__init__(self, path, sessionCacheDriver)
        self.queue = queueDriver(self)
        self.cache = cacheDriver(self)
        self.search = searchDriver(self)
        self.database = databaseDriver(self)
        self.schemaInfoList = []
        self.schemaInfoMap = {}

    async def __startup__(self):
        await self.database.initialize()
        await self.search.initialize()
        await self.cache.initialize()
        await self.queue.initialize()
        self.api.add_api_route(
            methods=['GET'],
            path=f'{self.uriver}/schema',
            endpoint=self.getSchemaInfo, response_model=dict, tags=['Schema'], name='Get Schema Info'
        )
        await SessionControl.__startup__(self)

    async def __shutdown__(self):
        await SessionControl.__shutdown__(self)
        await self.database.disconnect()
        await self.search.disconnect()
        await self.cache.disconnect()
        await self.queue.disconnect()

    async def publishToRouter(self, publish, category, target, status, data):
        if True if publish == '' or publish == 'true' else False: await runBackground(self.__publishToRouter__(category, target, data['id'], data['sref'], data['uref'], status))

    async def __publishToRouter__(self, category, target, id, sref, uref, status):
        try: await self.queue.publish(category, target, 'mdstat', {'id': id, 'sref': sref, 'uref': uref, 'status': status})
        except: pass

    async def registerModel(self, schema:BaseSchema, createHandler=None, updateHandler=None, deleteHandler=None):
        schema.setSchemaInfo(
            service=self.module,
            version=self.version,
            control=self,
            createHandler=createHandler,
            updateHandler=updateHandler,
            deleteHandler=deleteHandler
        )
        schemaInfo = schema.getSchemaInfo()

        if LAYER.checkDatabase(schemaInfo.layer): await self.database.registerModel(schemaInfo)
        if LAYER.checkSearch(schemaInfo.layer): await self.search.registerModel(schemaInfo)
        if LAYER.checkCache(schemaInfo.layer): await self.cache.registerModel(schemaInfo)

        self.schemaInfoList.append(schemaInfo)
        self.schemaInfoMap[schemaInfo.path] = schemaInfo
        setEnvironment(schemaInfo.sref, schema)

        if CRUD.checkRead(schemaInfo.crud):
            if AAA.checkAuthorization(schemaInfo.aaa):
                if AAA.checkAuthentication(schemaInfo.aaa):
                    if AAA.checkAccount(schemaInfo.aaa):
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.searchModelsByAuthnUser, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.countModelsByAuthnUser, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.readModelByAuthnUser, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
                    elif AAA.checkGroup(schemaInfo.aaa):
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.searchModelsByAuthnGroup, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.countModelsByAuthnGroup, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.readModelByAuthnGroup, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
                    else:
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.searchModelsByAuthn, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.countModelsByAuthn, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                        self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.readModelByAuthn, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
                else:
                    self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.searchModelsByAuth, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                    self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.countModelsByAuth, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                    self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.readModelByAuth, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
            else:
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.searchModelsByAnony, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.countModelsByAnony, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.readModelByAnony, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')

        if CRUD.checkCreate(schemaInfo.crud):
            if AAA.checkAuthorization(schemaInfo.aaa):
                if AAA.checkAuthentication(schemaInfo.aaa):
                    if AAA.checkAccount(schemaInfo.aaa):
                        self.createModelByAuthnUser.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.createModelByAuthnUser, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                    elif AAA.checkGroup(schemaInfo.aaa):
                        self.createModelByAuthnGroup.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.createModelByAuthnGroup, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                    else:
                        self.createModelByAuthn.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.createModelByAuthn, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                else:
                    self.createModelByAuth.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.createModelByAuth, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
            else:
                self.createModelByAnony.__annotations__['model'] = schema
                self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.createModelByAnony, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')

        if CRUD.checkUpdate(schemaInfo.crud):
            if AAA.checkAuthorization(schemaInfo.aaa):
                if AAA.checkAuthentication(schemaInfo.aaa):
                    if AAA.checkAccount(schemaInfo.aaa):
                        self.updateModelByAuthnUser.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.updateModelByAuthnUser, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                    elif AAA.checkGroup(schemaInfo.aaa):
                        self.updateModelByAuthnGroup.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.updateModelByAuthnGroup, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                    else:
                        self.updateModelByAuthn.__annotations__['model'] = schema
                        self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.updateModelByAuthn, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                else:
                    self.updateModelByAuth.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.updateModelByAuth, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
            else:
                self.updateModelByAnony.__annotations__['model'] = schema
                self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.updateModelByAnony, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')

        if CRUD.checkDelete(schemaInfo.crud):
            if AAA.checkAuthorization(schemaInfo.aaa):
                if AAA.checkAuthentication(schemaInfo.aaa):
                    if AAA.checkAccount(schemaInfo.aaa):
                        self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.deleteModelByAuthnUser, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
                    elif AAA.checkGroup(schemaInfo.aaa):
                        self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.deleteModelByAuthnGroup, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
                    else:
                        self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.deleteModelByAuthn, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
                else:
                    self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.deleteModelByAuth, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
            else:
                self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.deleteModelByAnony, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')

        return self

    async def getSchemaInfo(self, token: AUTH_HEADER) -> dict:
        await self.checkAuthorization(token)
        desc = {}
        for schemaInfo in self.schemaInfoList:
            desc[schemaInfo.sref] = {
                'name': schemaInfo.name,
                'sref': schemaInfo.sref,
                'description': schemaInfo.description,
                'crud': {
                    'create': CRUD.checkCreate(schemaInfo.crud),
                    'read': CRUD.checkRead(schemaInfo.crud),
                    'update': CRUD.checkUpdate(schemaInfo.crud),
                    'delete': CRUD.checkDelete(schemaInfo.crud),
                },
                'aaa': {
                    'authorization': AAA.checkAuthorization(schemaInfo.aaa),
                    'authentication': AAA.checkAuthentication(schemaInfo.aaa),
                    'group': AAA.checkGroup(schemaInfo.aaa),
                    'account': AAA.checkAccount(schemaInfo.aaa)
                }
            }
        return desc

    async def readModelByAuthnUser(self, request:Request, token: AUTH_HEADER, id:ID):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)
        model = await self.readModel(schemaInfo, id)
        authInfo.checkUsername(model['owner'])
        return model

    async def readModelByAuthnGroup(self, request:Request, token: AUTH_HEADER, id:ID):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)
        model = await self.readModel(schemaInfo, id)
        authInfo.checkGroup(model['owner'])
        return model

    async def readModelByAuthn(self, request:Request, token: AUTH_HEADER, id:ID):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkReadable(token, sref)
        return await self.readModel(schemaInfo, id)

    async def readModelByAuth(self, request:Request, token: AUTH_HEADER, id:ID):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        await self.checkAuthorization(token)
        return await self.readModel(schemaInfo, id)

    async def readModelByAnony(self, request:Request, id:ID):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        return await self.readModel(schemaInfo, id)

    async def readModel(self, schemaInfo, id):
        if LAYER.checkCache(schemaInfo.layer):
            try:
                model = await self.cache.read(schemaInfo, id)
                if model: return model
            except: pass
        if LAYER.checkSearch(schemaInfo.layer):
            try:
                model = await self.search.read(schemaInfo, id)
                if model:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, model))
                    return model
            except: pass
        if LAYER.checkDatabase(schemaInfo.layer):
            try:
                model = await self.database.read(schemaInfo, id)
                if model:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, model))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.create(schemaInfo, model))
                    return model
            except: pass
        raise EpException(404, 'Not Found')

    async def searchModelsByAuthnUser(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count default) 100')]=100,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count default) 0')]=0,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        query['owner'] = authInfo.username
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if filter: filter = f"{query} AND ({' AND '.join(filter)})"
        else: filter = query

        return await self.searchModels(
            schemaInfo,
            Search(filter=parseLucene.parse(filter) if filter else None, orderBy=orderBy, order=order, size=size, skip=skip),
            True if archive == '' or archive == 'true' else False
        )

    async def searchModelsByAuthnGroup(
        self,
        request:Request,
        token: AUTH_HEADER,
        group:Annotated[List[str] | None, Query(alias='$group', description='group code for access control ex) $group=group1&$group=group2')]=None,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count default) 100')]=100,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count default) 0')]=0,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$group' in query: query.pop('$group')
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        if authInfo.checkAdmin(): groups = ''
        elif not authInfo.groups: raise EpException(403, 'Forbidden')
        elif group: groups = ' OR '.join([f'owner:{authInfo.checkOnlyGroup(gid)}' for gid in group])
        else: groups = ' OR '.join([f'owner:{gid}' for gid in authInfo.groups])
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if groups:
            if query:
                if filter: filter = f"({groups}) AND ({query}) AND ({' AND '.join(filter)})"
                else: filter = f'({groups}) AND ({query})'
            else:
                if filter: filter = f"({groups}) AND ({' AND '.join(filter)})"
                else: filter = groups
        else:
            if query:
                if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
                else: filter = query
            else:
                if filter: filter = ' AND '.join(filter)
                else: filter = ''

        return await self.searchModels(
            schemaInfo,
            Search(filter=parseLucene.parse(filter) if filter else None, orderBy=orderBy, order=order, size=size, skip=skip),
            True if archive == '' or archive == 'true' else False
        )

    async def searchModelsByAuthn(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count default) 100')]=100,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count default) 0')]=0,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return await self.searchModels(
            schemaInfo,
            Search(filter=parseLucene.parse(filter) if filter else None, orderBy=orderBy, order=order, size=size, skip=skip),
            True if archive == '' or archive == 'true' else False
        )

    async def searchModelsByAuth(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count default) 100')]=100,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count default) 0')]=0,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref
        schemaInfo = self.schemaInfoMap[path]
        await self.checkAuthorization(token)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return await self.searchModels(
            schemaInfo,
            Search(filter=parseLucene.parse(filter) if filter else None, orderBy=orderBy, order=order, size=size, skip=skip),
            True if archive == '' or archive == 'true' else False
        )

    async def searchModelsByAnony(
        self,
        request:Request,
        filter:Annotated[str | None, Query(alias='$filter', description='lucene type filter ex) $filter=fieldName:yourSearchText')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count default) 100')]=100,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count default) 0')]=0,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref
        schemaInfo = self.schemaInfoMap[path]

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return await self.searchModels(
            schemaInfo,
            Search(filter=parseLucene.parse(filter) if filter else None, orderBy=orderBy, order=order, size=size, skip=skip),
            True if archive == '' or archive == 'true' else False
        )

    async def searchModels(
        self,
        schemaInfo,
        search,
        archive
    ):
        if archive and LAYER.checkDatabase(schemaInfo.layer):
            try: models = await self.database.search(schemaInfo, search)
            except LookupError: raise EpException(400, 'Bad Request')
            except:
                if LAYER.checkSearch(schemaInfo.layer):
                    try: models = await self.search.search(schemaInfo, search)
                    except LookupError: raise EpException(400, 'Bad Request')
                    except Exception: raise EpException(503, 'Service Unavailable')
                    else:
                        if models and LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, *models))
                else: raise EpException(503, 'Service Unavailable')
            else:
                if models:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, *models))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.create(schemaInfo, *models))
            return models
        elif LAYER.checkSearch(schemaInfo.layer):
            try: models = await self.search.search(schemaInfo, search)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception:
                if LAYER.checkDatabase(schemaInfo.layer):
                    try: models = await self.database.search(schemaInfo, search)
                    except LookupError: raise EpException(400, 'Bad Request')
                    except Exception: raise EpException(503, 'Service Unavailable')
                    else:
                        if models:
                            if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, *models))
                            if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.create(schemaInfo, *models))
                else: raise EpException(503, 'Service Unavailable')
            else:
                if models and LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, *models))
            return models

        raise EpException(501, 'Not Implemented')

    async def countModelsByAuthnUser(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        query['owner'] = authInfo.username
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if filter: filter = f"{query} AND ({' AND '.join(filter)})"
        else: filter = query

        return ModelCount(
            sref=sref,
            uref=uref,
            query=queryString,
            result=await self.countModels(
                schemaInfo,
                Search(filter=parseLucene.parse(filter) if filter else None),
                True if archive == '' or archive == 'true' else False
            )
        )

    async def countModelsByAuthnGroup(
        self,
        request:Request,
        token: AUTH_HEADER,
        group:Annotated[List[str] | None, Query(alias='$group', description='group code for access control ex) $group=group1&$group=group2')]=None,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$group' in query: query.pop('$group')
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        if authInfo.checkAdmin(): groups = ''
        elif not authInfo.groups: raise EpException(403, 'Forbidden')
        elif group: groups = ' OR '.join([f'owner:{authInfo.checkOnlyGroup(gid)}' for gid in group])
        else: groups = ' OR '.join([f'owner:{gid}' for gid in authInfo.groups])
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if groups:
            if query:
                if filter: filter = f"({groups}) AND ({query}) AND ({' AND '.join(filter)})"
                else: filter = f'({groups}) AND ({query})'
            else:
                if filter: filter = f"({groups}) AND ({' AND '.join(filter)})"
                else: filter = groups
        else:
            if query:
                if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
                else: filter = query
            else:
                if filter: filter = ' AND '.join(filter)
                else: filter = ''

        return ModelCount(
            sref=sref,
            uref=uref,
            query=queryString,
            result=await self.countModels(
                schemaInfo,
                Search(filter=parseLucene.parse(filter) if filter else None),
                True if archive == '' or archive == 'true' else False
            )
        )

    async def countModelsByAuthn(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkReadable(token, sref)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return ModelCount(
            sref=sref,
            uref=uref,
            query=queryString,
            result=await self.countModels(
                schemaInfo,
                Search(filter=parseLucene.parse(filter) if filter else None),
                True if archive == '' or archive == 'true' else False
            )
        )

    async def countModelsByAuth(
        self,
        request:Request,
        token: AUTH_HEADER,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkAuthorization(token)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return ModelCount(
            sref=sref,
            uref=uref,
            query=queryString,
            result=await self.countModels(
                schemaInfo,
                Search(filter=parseLucene.parse(filter) if filter else None),
                True if archive == '' or archive == 'true' else False
            )
        )

    async def countModelsByAnony(
        self,
        request:Request,
        filter:Annotated[List[str] | None, Query(alias='$filter', description='lucene type filter ex) $filter=field1:data1&$filter=field2:data2')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        query = ' AND '.join([f'{key}:{val}' for key, val in query.items()])
        if query:
            if filter: filter = f"({query}) AND ({' AND '.join(filter)})"
            else: filter = query
        else:
            if filter: filter = ' AND '.join(filter)
            else: filter = ''

        return ModelCount(
            sref=sref,
            uref=uref,
            query=queryString,
            result=await self.countModels(
                schemaInfo,
                Search(filter=parseLucene.parse(filter) if filter else None),
                True if archive == '' or archive == 'true' else False
            )
        )

    async def countModels(
        self,
        schemaInfo,
        search,
        archive
    ):
        if archive and LAYER.checkDatabase(schemaInfo.layer):
            try: return await self.database.count(schemaInfo, search)
            except LookupError: raise EpException(400, 'Bad Request')
            except:
                if LAYER.checkSearch(schemaInfo.layer):
                    try: return await self.search.count(schemaInfo, search)
                    except LookupError: raise EpException(400, 'Bad Request')
                    except Exception: raise EpException(503, 'Service Unavailable')
                else: raise EpException(503, 'Service Unavailable')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: return await self.search.count(schemaInfo, search)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception as e:
                if LAYER.checkDatabase(schemaInfo.layer):
                    try: return await self.database.count(schemaInfo, search)
                    except LookupError: raise EpException(400, 'Bad Request')
                    except Exception as e: raise EpException(503, f'Service Unavailable {e}')
                else: raise EpException(503, 'Service Unavailable')

        raise EpException(501, 'Not Implemented')

    async def createModelByAuthnUser(
        self,
        token:AUTH_HEADER,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        schemaInfo = model.__class__.getSchemaInfo()
        authInfo = await self.checkCreatable(token, schemaInfo.sref)
        data = await self.createModel(schemaInfo, model.setID().updateStatus(authInfo.username).model_dump())
        await self.publishToRouter(publish, 'user', authInfo.username, 'created', data)
        return data

    async def createModelByAuthnGroup(
        self,
        token:AUTH_HEADER,
        group:Annotated[str, Query(alias='$group', description='group code for access control')],
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        schemaInfo = model.__class__.getSchemaInfo()
        await self.checkCreatable(token, schemaInfo.sref)
        data = await self.createModel(schemaInfo, model.setID().updateStatus(group).model_dump())
        await self.publishToRouter(publish, 'group', group, 'created', data)
        return data

    async def createModelByAuthn(
        self,
        token:AUTH_HEADER,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        schemaInfo = model.__class__.getSchemaInfo()
        authInfo = await self.checkCreatable(token, schemaInfo.sref)
        data = await self.createModel(schemaInfo, model.setID().updateStatus(authInfo.username).model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'created', data)
        return data

    async def createModelByAuth(
        self,
        token:AUTH_HEADER,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        schemaInfo = model.__class__.getSchemaInfo()
        authInfo = await self.checkAuthorization(token)
        data = await self.createModel(schemaInfo, model.setID().updateStatus(authInfo.username).model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'created', data)
        return data

    async def createModelByAnony(
        self,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        schemaInfo = model.__class__.getSchemaInfo()
        data = await self.createModel(schemaInfo, model.setID().updateStatus().model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'created', data)
        return data

    async def createModel(
        self,
        schemaInfo,
        data
    ):
        if schemaInfo.createHandler: data = await schemaInfo.createHandler(data)
        if LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self.database.create(schemaInfo, data))[0]
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, data))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.create(schemaInfo, data))
                    return data
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self.search.create(schemaInfo, data)
            except LookupError as e: LOG.ERROR(e); raise EpException(400, 'Bad Request')
            except Exception as e: LOG.ERROR(e); raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.create(schemaInfo, data))
                return data
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self.cache.create(schemaInfo, data)
            except LookupError as e: LOG.ERROR(e); raise EpException(400, 'Bad Request')
            except Exception as e: LOG.ERROR(e); raise EpException(503, 'Service Unavailable')
            else: return data
        else: raise EpException(501, 'Not Implemented')

    async def updateModelByAuthnUser(
        self,
        token:AUTH_HEADER,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        schemaInfo = model.__class__.getSchemaInfo()
        authInfo = await self.checkUpdatable(token, schemaInfo.sref)
        origin = await self.readModel(schemaInfo, id)
        owner = origin['owner']
        authInfo.checkUsername(owner)
        data = await self.updateModel(schemaInfo, model.setID(id).updateStatus(owner).model_dump())
        await self.publishToRouter(publish, 'user', owner, 'updated', data)
        return data

    async def updateModelByAuthnGroup(
        self,
        token:AUTH_HEADER,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        schemaInfo = model.__class__.getSchemaInfo()
        authInfo = await self.checkUpdatable(token, schemaInfo.sref)
        origin = await self.readModel(schemaInfo, id)
        owner = origin['owner']
        authInfo.checkGroup(owner)
        data = await self.updateModel(schemaInfo, model.setID(id).updateStatus(owner).model_dump())
        await self.publishToRouter(publish, 'group', owner, 'updated', data)
        return data

    async def updateModelByAuthn(
        self,
        token:AUTH_HEADER,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        schemaInfo = model.__class__.getSchemaInfo()
        await self.checkUpdatable(token, schemaInfo.sref)
        origin = await self.readModel(schemaInfo, id)
        data = await self.updateModel(schemaInfo, model.setID(id).updateStatus(origin['owner']).model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'updated', data)
        return data

    async def updateModelByAuth(
        self,
        token:AUTH_HEADER,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        schemaInfo = model.__class__.getSchemaInfo()
        await self.checkAuthorization(token)
        origin = await self.readModel(schemaInfo, id)
        data = await self.updateModel(schemaInfo, model.setID(id).updateStatus(origin['owner']).model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'updated', data)
        return data

    async def updateModelByAnony(
        self,
        id:ID,
        model:BaseModel,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        schemaInfo = model.__class__.getSchemaInfo()
        origin = await self.readModel(schemaInfo, id)
        data = await self.updateModel(schemaInfo, model.setID(id).updateStatus(origin['owner']).model_dump())
        await self.publishToRouter(publish, 'group', self.userRoleName, 'updated', data)
        return data

    async def updateModel(
        self,
        schemaInfo,
        data
    ):
        if schemaInfo.updateHandler: data = await schemaInfo.updateHandler(data)
        if LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self.database.update(schemaInfo, data))[0]
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.update(schemaInfo, data))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.update(schemaInfo, data))
                    return data
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self.search.update(schemaInfo, data)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.update(schemaInfo, data))
                return data
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self.cache.update(schemaInfo, data)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else: return data
        else: raise EpException(501, 'Not Implemented')

    async def deleteModelByAuthnUser(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkDeletable(token, sref)
        origin = await self.readModel(schemaInfo, id)
        owner = origin['owner']
        authInfo.checkUsername(owner)
        origin['deleted'] = True
        origin['tstamp'] = getTStamp()
        await self.deleteModel(schemaInfo, id, origin, True if force == '' or force == 'true' else False)
        await self.publishToRouter(publish, 'user', owner, 'deleted', origin)
        return ModelStatus(id=id, sref=sref, uref=uref, status='deleted')

    async def deleteModelByAuthnGroup(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        authInfo = await self.checkDeletable(token, sref)
        origin = await self.readModel(schemaInfo, id)
        owner = origin['owner']
        authInfo.checkGroup(owner)
        origin['deleted'] = True
        origin['tstamp'] = getTStamp()
        await self.deleteModel(schemaInfo, id, origin, True if force == '' or force == 'true' else False)
        await self.publishToRouter(publish, 'group', owner, 'deleted', origin)
        return ModelStatus(id=id, sref=sref, uref=uref, status='deleted')

    async def deleteModelByAuthn(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkDeletable(token, sref)
        origin = await self.readModel(schemaInfo, id)
        origin['deleted'] = True
        origin['tstamp'] = getTStamp()
        await self.deleteModel(schemaInfo, id, origin, True if force == '' or force == 'true' else False)
        await self.publishToRouter(publish, 'group', self.userRoleName, 'deleted', origin)
        return ModelStatus(id=id, sref=sref, uref=uref, status='deleted')

    async def deleteModelByAuth(
        self,
        request:Request,
        token:AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        await self.checkAuthorization(token)
        origin = await self.readModel(schemaInfo, id)
        origin['deleted'] = True
        origin['tstamp'] = getTStamp()
        await self.deleteModel(schemaInfo, id, origin, True if force == '' or force == 'true' else False)
        await self.publishToRouter(publish, 'group', self.userRoleName, 'deleted', origin)
        return ModelStatus(id=id, sref=sref, uref=uref, status='deleted')

    async def deleteModelByAnony(
        self,
        request:Request,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force', description='delete permanently')]=None,
        publish:Annotated[Literal['true', 'false', ''], Query(alias='$publish', description='publish to user notification')]=None
    ):
        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schemaInfo = self.schemaInfoMap[path]
        sref = schemaInfo.sref
        origin = await self.readModel(schemaInfo, id)
        origin['deleted'] = True
        origin['tstamp'] = getTStamp()
        await self.deleteModel(schemaInfo, id, origin, True if force == '' or force == 'true' else False)
        await self.publishToRouter(publish, 'group', self.userRoleName, 'deleted', origin)
        return ModelStatus(id=id, sref=sref, uref=uref, status='deleted')

    async def deleteModel(
        self,
        schemaInfo,
        id,
        data,
        force
    ):
        if schemaInfo.deleteHandler: data = await schemaInfo.deleteHandler(data)
        if force and LAYER.checkDatabase(schemaInfo.layer):
            try: result = await self.database.delete(schemaInfo, id)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.delete(schemaInfo, id))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.delete(schemaInfo, id))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self.database.update(schemaInfo, data))[0]
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.delete(schemaInfo, id))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self.search.delete(schemaInfo, id))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self.search.delete(schemaInfo, id)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self.cache.delete(schemaInfo, id))
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self.cache.delete(schemaInfo, id)
            except LookupError: raise EpException(400, 'Bad Request')
            except Exception: raise EpException(503, 'Service Unavailable')
        else: raise EpException(501, 'Not Implemented')
