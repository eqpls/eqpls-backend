# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
try: import LOG  # @UnresolvedImport
except: pass

import os
import traceback
from typing import Annotated, Any, List, Literal
from fastapi import FastAPI, Request, Query
from pydantic import BaseModel
from luqum.parser import parser as parseLucene
from stringcase import pathcase

from .constants import CRUD, LAYER, AAA, ORG_HEADER, AUTH_HEADER
from .exceptions import EpException
from .schedules import asleep, runBackground
from .interfaces import AsyncRest
from .utils import getConfig, Logger
from .models import Search, ID, BaseSchema, ServiceHealth, ModelStatus, ModelCount
from .auth import AuthInfo, Org, Account, Role, Group


#===============================================================================
# Base Control
#===============================================================================
class BaseControl:

    def __init__(self, path:str, sessionChecker:str=None, background:bool=False):
        self.path = os.path.abspath(path)
        self.svcPath = os.path.dirname(self.path)
        self.modPath = os.path.dirname(self.svcPath)
        self.prjPath = os.path.dirname(self.modPath)
        self.background = background

        self.config = getConfig(f'{self.prjPath}/project.ini')
        Logger.register(self.config)

        self.module = os.path.basename(self.modPath)
        self.title = self.config['default']['title']
        self.version = int(self.config['default']['version'])
        self.uri = f'/{pathcase(self.module)}'

        if sessionChecker:
            checkerHostname = self.config[sessionChecker]['hostname']
            checkerHostport = self.config[sessionChecker]['hostport']
            self.sessionCheckerUrl = f'http://{checkerHostname}:{checkerHostport}'
            self.checkAuthInfo = self.__check_auth_info__

        self.api = FastAPI(
            title=self.module,
            docs_url=f'{self.uri}/docs',
            openapi_url=f'{self.uri}/openapi.json',
            separate_input_output_schemas=False
        )

        LOG.INFO(f'title    = {self.title}')
        LOG.INFO(f'module   = {self.module}')
        LOG.INFO(f'version  = {self.version}')
        LOG.INFO(f'uri      = {self.uri}')
        LOG.INFO(f'swagger  = {self.uri}/docs')
        LOG.INFO(f'prj path = {self.svcPath}')
        LOG.INFO(f'mod path = {self.svcPath}')
        LOG.INFO(f'svc path = {self.svcPath}')

        self.api.router.add_event_handler('startup', self.__startup__)
        self.api.router.add_event_handler('shutdown', self.__shutdown__)

    async def __startup__(self):
        LOG.INFO(f'{self.module} prepare controller')
        await self.startup()
        if self.background: await runBackground(self.__background__())
        self.api.add_api_route(
            tags=['Internal Only'],
            name='Health',
            methods=['GET'],
            path='/internal/health',
            endpoint=self.__health__,
            response_model=ServiceHealth
        )
        LOG.INFO(f'{self.module} controller is ready')

    async def __shutdown__(self):
        LOG.INFO(f'{self.module} stop controller')
        await self.shutdown()
        LOG.INFO(f'{self.module} controller is finished')

    async def __background__(self):
        LOG.INFO('run background')
        while self._background: await self.background()
        LOG.INFO('background finished')

    async def __health__(self) -> ServiceHealth:
        return await self.health()

    async def __check_auth_info__(self, org:str, token:str):
        async with AsyncRest(self.sessionCheckerUrl) as rest:
            authInfo = await rest.get(f'/internal/authinfo', headers={
                'Authorization': f'Bearer {token}',
                'Org': org
            })
        return AuthInfo(**authInfo)

    async def startup(self): pass

    async def shutdown(self): pass

    async def background(self):
        await asleep(1)

    async def health(self) -> ServiceHealth:
        return ServiceHealth(title=self.module, status='OK', healthy=True)


#===============================================================================
# Mesh Control
#===============================================================================
class MeshControl(BaseControl):

    def __init__(self, path:str, sessionChecker:str=None, background:bool=False):
        BaseControl.__init__(
            self,
            path=path,
            sessionChecker=sessionChecker,
            background=background
        )

    async def registerModel(self, schema:BaseSchema, uerp:str):
        if uerp not in self.config: raise Exception(f'{uerp} is not in configuration')
        config = self.config[uerp]
        hostname = config['hostname']
        hostport = config['hostport']
        schema.setSchemaInfo(
            f'http://{hostname}:{hostport}',
            uerp,
            self.version
        )
        return self


#===============================================================================
# Uerp Control
#===============================================================================
class UerpControl(BaseControl):

    def __init__(
        self,
        path:str,
        authDriver:Any,
        cacheDriver:Any,
        searchDriver:Any,
        databaseDriver:Any,
        background:bool=False
    ):
        BaseControl.__init__(
            self,
            path=path,
            background=background
        )

        self._uerpAuth = authDriver(self.config)
        self._uerpCache = cacheDriver(self.config)
        self._uerpSearch = searchDriver(self.config)
        self._uerpDatabase = databaseDriver(self.config)

        self._uerpSchemaList = []
        self._uerpPathToSchemaMap = {}

    async def __startup__(self):
        await self._uerpDatabase.connect()
        await self._uerpSearch.connect()
        await self._uerpCache.connect()

        await BaseControl.__startup__(self)

        self.api.add_api_route(methods=['GET'], path=f'{self.uri}/v{self.version}/schema', endpoint=self.__describe_schema__, response_model=dict, tags=['Schema'], name='Get Schema Map')

        await self.registerModel(
            schema=Org,
            createHandler=self._uerpAuth.createOrg,
            updateHandler=self._uerpAuth.updateOrg,
            deleteHandler=self._uerpAuth.deleteOrg
        )
        await self.registerModel(
            schema=Role,
            createHandler=self._uerpAuth.createRole,
            updateHandler=self._uerpAuth.updateRole,
            deleteHandler=self._uerpAuth.deleteRole
        )
        await self.registerModel(
            schema=Group,
            createHandler=self._uerpAuth.createGroup,
            updateHandler=self._uerpAuth.updateGroup,
            deleteHandler=self._uerpAuth.deleteGroup
        )
        await self.registerModel(
            schema=Account,
            createHandler=self._uerpAuth.createAccount,
            updateHandler=self._uerpAuth.updateAccount,
            deleteHandler=self._uerpAuth.deleteAccount
        )
        await self._uerpAuth.connect()

        self.api.add_api_route(methods=['GET'], path='/internal/authinfo', endpoint=self.__confirm_auth_info__, response_model=AuthInfo, tags=['Internal Only'], name='Check Auth Info')
        self.api.add_api_route(methods=['GET'], path='/internal/client/secret', endpoint=self.__get_client_secret__, response_model=str, tags=['Internal Only'], name='Get Client Secret')

    async def __shutdown__(self):
        await BaseControl.__shutdown__(self)
        if self._uerpDatabase: await self._uerpDatabase.disconnect()
        if self._uerpSearch: await self._uerpSearch.disconnect()
        if self._uerpCache: await self._uerpCache.disconnect()
        if self._uerpAuth: await self._uerpAuth.disconnect()

    async def registerModel(
        self,
        schema:BaseSchema,
        createHandler=None,
        updateHandler=None,
        deleteHandler=None
    ):
        schema.setSchemaInfo(
            self,
            self.module,
            self.version,
            createHandler=createHandler,
            updateHandler=updateHandler,
            deleteHandler=deleteHandler
        )
        schemaInfo = schema.getSchemaInfo()

        if LAYER.checkDatabase(schemaInfo.layer): await self._uerpDatabase.registerModel(schema)
        if LAYER.checkSearch(schemaInfo.layer): await self._uerpSearch.registerModel(schema)
        if LAYER.checkCache(schemaInfo.layer): await self._uerpCache.registerModel(schema)

        self._uerpSchemaList.append(schema)
        self._uerpPathToSchemaMap[schemaInfo.path] = schema

        if AAA.checkAuthorization(schemaInfo.aaa):
            if CRUD.checkRead(schemaInfo.rest):
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.__search_data_with_auth__, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.__count_data_with_auth__, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.__read_data_with_auth__, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
            if CRUD.checkCreate(schemaInfo.rest):
                if AAA.checkGroup(schemaInfo.aaa):
                    self.__create_data_with_auth_by_group__.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.__create_data_with_auth_by_group__, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                    self.__create_data_with_auth_by_group__.__annotations__['model'] = BaseModel
                else:
                    self.__create_data_with_auth__.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.__create_data_with_auth__, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                    self.__create_data_with_auth__.__annotations__['model'] = BaseModel
            if CRUD.checkUpdate(schemaInfo.rest):
                if AAA.checkGroup(schemaInfo.aaa):
                    self.__update_data_with_auth_by_group__.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.__update_data_with_auth_by_group__, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                    self.__update_data_with_auth_by_group__.__annotations__['model'] = BaseModel
                else:
                    self.__update_data_with_auth__.__annotations__['model'] = schema
                    self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.__update_data_with_auth__, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                    self.__update_data_with_auth__.__annotations__['model'] = BaseModel
            if CRUD.checkDelete(schemaInfo.rest):
                if AAA.checkGroup(schemaInfo.aaa):
                    self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.__delete_data_with_auth_by_group__, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
                else:
                    self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.__delete_data_with_auth__, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')
        else:
            if CRUD.checkRead(schemaInfo.rest):
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path, endpoint=self.__search_data_with_free__, response_model=List[schema], tags=schemaInfo.tags, name=f'Search {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/count', endpoint=self.__count_data_with_free__, response_model=ModelCount, tags=schemaInfo.tags, name=f'Count {schemaInfo.name}')
                self.api.add_api_route(methods=['GET'], path=schemaInfo.path + '/{id}', endpoint=self.__read_data_with_free__, response_model=schema, tags=schemaInfo.tags, name=f'Read {schemaInfo.name}')
            if CRUD.checkCreate(schemaInfo.rest):
                self.__create_data_with_free__.__annotations__['model'] = schema
                self.api.add_api_route(methods=['POST'], path=schemaInfo.path, endpoint=self.__create_data_with_free__, response_model=schema, tags=schemaInfo.tags, name=f'Create {schemaInfo.name}')
                self.__create_data_with_free__.__annotations__['model'] = BaseModel
            if CRUD.checkUpdate(schemaInfo.rest):
                self.__update_data_with_free__.__annotations__['model'] = schema
                self.api.add_api_route(methods=['PUT'], path=schemaInfo.path + '/{id}', endpoint=self.__update_data_with_free__, response_model=schema, tags=schemaInfo.tags, name=f'Update {schemaInfo.name}')
                self.__update_data_with_free__.__annotations__['model'] = BaseModel
            if CRUD.checkDelete(schemaInfo.rest):
                self.api.add_api_route(methods=['DELETE'], path=schemaInfo.path + '/{id}', endpoint=self.__delete_data_with_free__, response_model=ModelStatus, tags=schemaInfo.tags, name=f'Delete {schemaInfo.name}')

        return self

    async def __describe_schema__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER
    ) -> dict:
        await self._uerpAuth.getAuthInfo(org, token.credentials)

        desc = {}
        for schema in self._uerpSchemaList:
            schemaInfo = schema.getSchemaInfo()
            desc[schemaInfo.sref] = {
                'name': schemaInfo.name,
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

    async def __confirm_auth_info__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER
    ) -> AuthInfo:
        return await self._uerpAuth.getAuthInfo(org, token.credentials)

    async def __get_client_secret__(
        self,
        org:str,
        client:str
    ) -> str:
        return await self._uerpAuth._authKeyCloak.getClientSecret(realm=org, clientId=client)

    async def __read_data_with_auth__(
        self,
        request:Request,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        id:ID
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        id = str(id)
        schema = self._uerpPathToSchemaMap[request.scope['path'].replace(f'/{id}', '')]
        schemaInfo = schema.getSchemaInfo()

        if not authInfo.checkAdmin() and AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkReadACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
        model = await self.readModel(schema, id)
        if model.org and not authInfo.checkOrg(model.org): raise EpException(404, 'Not Found')
        if AAA.checkAccount(schemaInfo.aaa):
            if not authInfo.checkUsername(model.owner): raise EpException(403, 'Forbidden')
        elif AAA.checkGroup(schemaInfo.aaa):
            if not authInfo.checkGroup(model.owner): raise EpException(403, 'Forbidden')
        return model

    async def __read_data_with_free__(
        self,
        request:Request,
        id:ID
    ): return await self.readModel(self._uerpPathToSchemaMap[request.scope['path'].replace(f'/{id}', '')], str(id))

    async def readModel(
        self,
        schema,
        id
    ):
        schemaInfo = schema.getSchemaInfo()
        
        if LAYER.checkCache(schemaInfo.layer):
            try:
                model = await self._uerpCache.read(schema, id)
                if model: return schema(**model)
            except: pass
        if LAYER.checkSearch(schemaInfo.layer):
            try:
                model = await self._uerpSearch.read(schema, id)
                if model:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, model))
                    return schema(**model)
            except: pass
        if LAYER.checkDatabase(schemaInfo.layer):
            try:
                model = await self._uerpDatabase.read(schema, id)
                if model:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, model))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.create(schema, model))
                    return schema(**model)
            except: pass

        raise EpException(404, 'Not Found')

    async def __search_data_with_auth__(
        self,
        request:Request,
        org:ORG_HEADER,
        token:AUTH_HEADER,
        fields:Annotated[List[str] | None, Query(alias='$f', description='looking fields ex) $f=field1&$f=field2')]=None,
        filter:Annotated[str | None, Query(alias='$filter', description='lucene type filter ex) $filter=fieldName:yourSearchText')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count')]=None,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        query = request.query_params._dict
        if '$f' in query: query.pop('$f')
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        if size: size = int(size)
        if skip: skip = int(skip)
        if archive == '': archive = True
        elif archive: archive = bool(archive)

        schema = self._uerpPathToSchemaMap[request.scope['path']]
        schemaInfo = schema.getSchemaInfo()

        query['org'] = authInfo.org
        qFilter = [f'{key}:{val}' for key, val in query.items()]
        qFilter = ' AND '.join(qFilter)
        if filter: filter = f'{qFilter} AND ({filter})'
        else: filter = qFilter
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkReadACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if AAA.checkAccount(schemaInfo.aaa): filter = f'{filter} AND owner:{authInfo.username}'
            elif AAA.checkGroup(schemaInfo.aaa):
                gFilter = [f'owner:{group}' for group in authInfo.groups]
                gFilter = ' OR '.join(gFilter)
                if gFilter: filter = f'{filter} AND ({gFilter})'
        filter = parseLucene.parse(filter)

        return await self.searchModels(
            schema,
            Search(fields=fields, filter=filter, orderBy=orderBy, order=order, size=size, skip=skip),
            archive
        )

    async def __search_data_with_free__(
        self,
        request:Request,
        fields:Annotated[List[str] | None, Query(alias='$f', description='looking fields ex) $f=field1&$f=field2')]=None,
        filter:Annotated[str | None, Query(alias='$filter', description='lucene type filter ex) $filter=fieldName:yourSearchText')]=None,
        orderBy:Annotated[str | None, Query(alias='$orderby', description='ordered by specific field')]=None,
        order:Annotated[Literal['asc', 'desc'], Query(alias='$order', description='ordering type')]=None,
        size:Annotated[int | None, Query(alias='$size', description='retrieving model count')]=None,
        skip:Annotated[int | None, Query(alias='$skip', description='skipping model count')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        query = request.query_params._dict
        if '$f' in query: query.pop('$f')
        if '$filter' in query: query.pop('$filter')
        if '$orderby' in query: query.pop('$orderby')
        if '$order' in query: query.pop('$order')
        if '$size' in query: query.pop('$size')
        if '$skip' in query: query.pop('$skip')
        if '$archive' in query: query.pop('$archive')
        if orderBy and not order: order = 'desc'
        if size: size = int(size)
        if skip: skip = int(skip)
        if archive == '': archive = True
        elif archive: archive = bool(archive)

        if query:
            qFilter = [f'{key}:{val}' for key, val in query.items()]
            qFilter = ' AND '.join(qFilter)
            if filter: filter = f'{qFilter} AND ({filter})'
            else: filter = qFilter
        if filter: filter = parseLucene.parse(filter)

        return await self.searchModels(
            self._uerpPathToSchemaMap[request.scope['path']],
            Search(fields=fields, filter=filter, orderBy=orderBy, order=order, size=size, skip=skip),
            archive
        )

    async def searchModels(
        self,
        schema,
        search,
        archive
    ):
        schemaInfo = schema.getSchemaInfo()

        if archive and LAYER.checkDatabase(schemaInfo.layer):
            try: models = await self._uerpDatabase.search(schema, search)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except:
                if LAYER.checkSearch(schemaInfo.layer):
                    try: models = await self._uerpSearch(schema, search)
                    except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
                    except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
                    else:
                        if models and not search.fields and LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, *models))
                else: raise EpException(503, 'Service Unavailable')
            else:
                if models and not search.fields:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, *models))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.create(schema, *models))
            return [schema(**model) for model in models]
        elif LAYER.checkSearch(schemaInfo.layer):
            try: models = await self._uerpSearch(schema, search)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception:
                if LAYER.checkDatabase(schemaInfo.layer):
                    try: models = await self._uerpDatabase.search(schema, search)
                    except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
                    except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
                    else:
                        if models and not search.fields:
                            if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, *models))
                            if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.create(schema, *models))
                else: raise EpException(503, 'Service Unavailable')
            else:
                if models and not search.fields and LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, *models))
            return [schema(**model) for model in models]

        raise EpException(501, 'Not Implemented')

    async def __count_data_with_auth__(
        self,
        request:Request,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        filter:Annotated[str | None, Query(alias='$filter', description='lucene type filter ex) $filter=fieldName:yourSearchText')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        if archive == '': archive = True
        elif archive: archive = bool(archive)

        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']

        schema = self._uerpPathToSchemaMap[path]
        schemaInfo = schema.getSchemaInfo()

        query['org'] = authInfo.org
        qFilter = [f'{key}:{val}' for key, val in query.items()]
        qFilter = ' AND '.join(qFilter)
        if filter: filter = f'{qFilter} AND ({filter})'
        else: filter = qFilter
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkReadACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if AAA.checkAccount(schemaInfo.aaa): filter = f'{filter} AND owner:{authInfo.username}'
            elif AAA.checkGroup(schemaInfo.aaa):
                gFilter = [f'owner:{group}' for group in authInfo.groups]
                gFilter = ' OR '.join(gFilter)
                if gFilter: filter = f'{filter} AND ({gFilter})'
        filter = parseLucene.parse(filter)

        return ModelCount(sref=schema.sref, uref=uref, query=queryString, result=await self.countModels(
            schema,
            Search(filter=filter),
            archive
        ))

    async def __count_data_with_free__(
        self,
        request:Request,
        filter:Annotated[str | None, Query(alias='$filter', description='lucene type filter ex) $filter=fieldName:yourSearchText')]=None,
        archive:Annotated[Literal['true', 'false', ''], Query(alias='$archive', description='searching from archive aka database')]=None
    ):
        query = request.query_params._dict
        if '$filter' in query: query.pop('$filter')
        if '$archive' in query: query.pop('$archive')
        if archive == '': archive = True
        elif archive: archive = bool(archive)

        uref = request.scope['path']
        path = uref.replace('/count', '')
        queryString = request.scope['query_string']

        schema = self._uerpPathToSchemaMap[path]

        if query:
            qFilter = [f'{key}:{val}' for key, val in query.items()]
            qFilter = ' AND '.join(qFilter)
            if filter: filter = f'{qFilter} AND ({filter})'
            else: filter = qFilter
        if filter: filter = parseLucene.parse(filter)

        return ModelCount(sref=schema.sref, uref=uref, query=queryString, result=await self.countModels(
            schema,
            Search(filter=filter),
            archive
        ))

    async def countModels(
        self,
        schema,
        search,
        archive
    ):
        schemaInfo = schema.getSchemaInfo()

        if archive and LAYER.checkDatabase(schemaInfo.layer):
            try: return await self._uerpDatabase.count(schema, search)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except:
                if LAYER.checkSearch(schemaInfo.layer):
                    try: return await self._uerpSearch.count(schema, search)
                    except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
                    except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
                else: raise EpException(503, 'Service Unavailable')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: return await self._uerpSearch.count(schema, search)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except:
                if LAYER.checkDatabase(schemaInfo.layer):
                    try: return await self._uerpDatabase.count(schema, search)
                    except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
                    except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
                else: raise EpException(503, 'Service Unavailable')

        raise EpException(501, 'Not Implemented')

    async def __create_data_with_auth__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        model:BaseModel
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        schema = model.__class__
        schemaInfo = schema.getSchemaInfo()

        if not authInfo.checkAdmin() and AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkCreateACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
        await self.createModel(schema, model.setID().updateStatus(org=authInfo.org, owner=authInfo.username).model_dump())
        return model

    async def __create_data_with_auth_by_group__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        groupId:Annotated[ID, Query(alias='$group', description='group id for access control')],
        model:BaseModel
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        schema = model.__class__
        schemaInfo = schema.getSchemaInfo()

        groupId = str(groupId)
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkCreateACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if not authInfo.checkGroup(groupId): raise EpException(403, 'Forbidden')
        await self.createModel(schema, model.setID().updateStatus(org=authInfo.org, owner=groupId).model_dump())
        return model

    async def __create_data_with_free__(
        self,
        model:BaseModel
    ):
        await self.createModel(model.__class__, model.setID().updateStatus().model_dump())
        return model

    async def createModel(
        self,
        schema,
        data
    ):
        schemaInfo = schema.getSchemaInfo()
        if schemaInfo.createHandler: data = await schemaInfo.createHandler(data)
        if LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self._uerpDatabase.create(schema, data))[0]
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, data))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.create(schema, data))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self._uerpSearch.create(schema, data)
            except LookupError as e: LOG.ERROR(e); traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception as e: LOG.ERROR(e); traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.create(schema, data))
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self._uerpCache.create(schema, data)
            except LookupError as e: LOG.ERROR(e); traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception as e: LOG.ERROR(e); traceback.print_exc(); raise EpException(503, 'Service Unavailable')
        else: raise EpException(501, 'Not Implemented')

    async def __update_data_with_auth__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        id:ID,
        model:BaseModel
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        id = str(id)
        schema = model.__class__
        schemaInfo = schema.getSchemaInfo()

        origin = await self.readModel(schema, id)
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkUpdateACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if origin.org and not authInfo.checkOrg(origin.org): raise EpException(403, 'Forbidden')
            if AAA.checkAccount(schemaInfo.aaa) and not authInfo.checkUsername(origin.owner): raise EpException(403, 'Forbidden')

        await self.updateModel(schema, model.setID(id).updateStatus(org=authInfo.org, owner=authInfo.username).model_dump())
        return model

    async def __update_data_with_auth_by_group__(
        self,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        id:ID,
        model:BaseModel
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        id = str(id)
        schema = model.__class__
        schemaInfo = schema.getSchemaInfo()

        origin = await self.readModel(schema, id)
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkUpdateACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if origin.org and not authInfo.checkOrg(origin.org): raise EpException(403, 'Forbidden')
            if not authInfo.checkGroup(origin.owner): raise EpException(403, 'Forbidden')

        await self.updateModel(schema, model.setID(id).updateStatus(org=authInfo.org, owner=origin.owner).model_dump())
        return model

    async def __update_data_with_free__(
        self,
        id:ID,
        model:BaseModel
    ):
        schema = model.__class__
        await self.updateModel(schema, model.setID(str(id)).updateStatus().model_dump())
        return model

    async def updateModel(
        self,
        schema,
        data
    ):
        schemaInfo = schema.getSchemaInfo()
        if schemaInfo.updateHandler: data = await schemaInfo.updateHandler(data)
        if LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self._uerpDatabase.update(schema, data))[0]
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.update(schema, data))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.update(schema, data))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self._uerpSearch.update(schema, data)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.update(schema, data))
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self._uerpCache.update(schema, data)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
        else: raise EpException(501, 'Not Implemented')

    async def __delete_data_with_auth__(
        self,
        request:Request,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force')]=None
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        if force == '': force = True
        elif force: force = bool(force)

        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schema = self._uerpPathToSchemaMap[path]
        schemaInfo = schema.getSchemaInfo()

        origin = await self.readModel(schema, id)
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkDeleteACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if origin.org and not authInfo.checkOrg(origin.org): raise EpException(403, 'Forbidden')
            if AAA.checkAccount(schemaInfo.aaa) and not authInfo.checkUsername(origin.owner): raise EpException(403, 'Forbidden')

        await self.deleteModel(schema, id, origin.setID(id).updateStatus(org=authInfo.org, owner=authInfo.username, deleted=True).model_dump(), force)
        return ModelStatus(id=id, sref=schemaInfo.sref, uref=uref, status='deleted')

    async def __delete_data_with_auth_by_group__(
        self,
        request:Request,
        org: ORG_HEADER,
        token: AUTH_HEADER,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force')]=None
    ):
        authInfo = await self._uerpAuth.getAuthInfo(org, token.credentials)

        if force == '': force = True
        elif force: force = bool(force)

        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schema = self._uerpPathToSchemaMap[path]
        schemaInfo = schema.getSchemaInfo()

        origin = await self.readModel(schema, id)
        if not authInfo.checkAdmin():
            if AAA.checkAuthentication(schemaInfo.aaa) and not authInfo.checkDeleteACL(schemaInfo.sref): raise EpException(403, 'Forbidden')
            if origin.org and not authInfo.checkOrg(origin.org): raise EpException(403, 'Forbidden')
            if not authInfo.checkGroup(origin.owner): raise EpException(403, 'Forbidden')

        await self.deleteModel(schema, id, origin.setID(id).updateStatus(org=authInfo.org, owner=origin.owner, deleted=True).model_dump(), force)
        return ModelStatus(id=id, sref=schemaInfo.sref, uref=uref, status='deleted')

    async def __delete_data_with_free__(
        self,
        request:Request,
        id:ID,
        force:Annotated[Literal['true', 'false', ''], Query(alias='$force')]=None
    ):
        if force == '': force = True
        elif force: force = bool(force)

        id = str(id)
        uref = request.scope['path']
        path = uref.replace(f'/{id}', '')
        schema = self._uerpPathToSchemaMap[path]
        schemaInfo = schema.getSchemaInfo()
        model = await self.readModel(schema, id)
        await self.deleteModel(schema, id, model.setID(id).updateStatus(deleted=True).model_dump(), force)
        return ModelStatus(id=id, sref=schemaInfo.sref, uref=uref, status='deleted')

    async def deleteModel(
        self,
        schema,
        id,
        data,
        force
    ):
        schemaInfo = schema.getSchemaInfo()
        if schemaInfo.deleteHandler: data = await schemaInfo.deleteHandler(data)
        if force and LAYER.checkDatabase(schemaInfo.layer):
            try: result = await self._uerpDatabase.delete(schema, id)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.delete(schema, id))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.delete(schema, id))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkDatabase(schemaInfo.layer):
            try: result = (await self._uerpDatabase.update(schema, data))[0]
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if result:
                    if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.delete(schema, id))
                    if LAYER.checkSearch(schemaInfo.layer): await runBackground(self._uerpSearch.delete(schema, id))
                else: raise EpException(409, 'Conflict')
        elif LAYER.checkSearch(schemaInfo.layer):
            try: await self._uerpSearch.delete(schema, id)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
            else:
                if LAYER.checkCache(schemaInfo.layer): await runBackground(self._uerpCache.delete(schema, id))
        elif LAYER.checkCache(schemaInfo.layer):
            try: await self._uerpCache.delete(schema, id)
            except LookupError: traceback.print_exc(); raise EpException(400, 'Bad Request')
            except Exception: traceback.print_exc(); raise EpException(503, 'Service Unavailable')
        else: raise EpException(501, 'Not Implemented')
