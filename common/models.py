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
from uuid import UUID, uuid4
from time import time as tstamp
from urllib.parse import urlencode
from typing import Annotated, Callable, TypeVar, Any, Literal
from pydantic import BaseModel, PlainSerializer, ConfigDict
from luqum.parser import parser as parseLucene
from stringcase import snakecase, pathcase, titlecase
from .constants import CRUD, LAYER, AAA
from .exceptions import EpException
from .interfaces import AsyncRest
from .utils import getEnvironment


#===============================================================================
# Interfaces
#===============================================================================
class Search:

    def __init__(
        self,
        filter:Any | None=None,
        orderBy:str | None=None,
        order:str | None=None,
        size:int | None=None,
        skip:int | None=None,
    ):
        self.filter = filter
        self.orderBy = orderBy
        self.order = order
        self.size = size
        self.skip = skip


class Option(dict):

    def __init__(self, **kargs): dict.__init__(self, **kargs)


#===============================================================================
# Fields
#===============================================================================
ID = Annotated[UUID, PlainSerializer(lambda x: str(x), return_type=str)]
Key = Annotated[str, 'keyword']


#===============================================================================
# Pre-Defined Models
#===============================================================================
class ServiceHealth(BaseModel):

    title:str = ''
    status:str = ''
    healthy:bool = False
    detail:dict = {}


class Reference(BaseModel):

    id:Key = ''
    sref:Key = ''
    uref:Key = ''

    async def readModel(self, token=None):
        try: schema = getEnvironment(self.sref)
        except: raise EpException(500, 'Internal Server Error')
        schemaInfo = schema.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkRead(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                async with AsyncRest(schemaInfo.provider) as req: return schema(**(await req.get(f'{schemaInfo.path}/{self.id}', headers=headers)))
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            model = await schemaInfo.control.readModel(schemaInfo, self.id)
            if model: return cls(**model)
            else: raise EpException(404, 'Not Found')
        else: raise EpException(501, 'Not Implemented')


class ModelStatus(BaseModel):

    id:Key = ''
    sref:Key = ''
    uref:Key = ''
    status:str = ''


class ModelCount(BaseModel):

    sref:Key = ''
    uref:Key = ''
    query:str = ''
    result:int = 0


#===============================================================================
# Schema Info
#===============================================================================
class SchemaInfo(BaseModel):

    ref:Any
    name:str
    description:str
    module:str
    tags:list[str]

    service:str = ''
    major:int = 1
    minor:int = 1
    control:Any | None = None
    provider:str | None = None

    sref:str = ''
    dref:str = ''
    path:str = ''

    aaa:int = AAA.FREE
    crud:int = CRUD.CRUD
    layer:int = LAYER.CSD

    cache:Any | None = None
    search:Any | None = None
    database:Any | None = None

    createHandler:Any | None = None
    updateHandler:Any | None = None
    deleteHandler:Any | None = None


_TypeT = TypeVar('_TypeT', bound=type)


def SchemaConfig(
    version:int,
    description:str='',
    aaa:int=AAA.FREE,
    crud:int=CRUD.CRUD,
    layer:int=LAYER.CSD,
    cache:Option | None=None,
    search:Option | None=None,
    database:Option | None=None
) -> Callable[[_TypeT], _TypeT]:

    def inner(TypedDictClass: _TypeT, /) -> _TypeT:
        if not issubclass(TypedDictClass, BaseSchema): raise Exception(f'{TypedDictClass} is not a BaseSchema')
        ref = TypedDictClass
        name = TypedDictClass.__name__
        module = TypedDictClass.__module__
        modsrt = module.replace('schema.', '')
        sref = f'{modsrt}.{name}'
        tags = [titlecase('.'.join(reversed(modsrt.lower().split('.'))))]
        TypedDictClass.__pydantic_config__ = ConfigDict(
            schemaInfo=SchemaInfo(
                ref=ref,
                name=name,
                description=description,
                module=module,
                tags=tags,
                minor=version,
                sref=sref,
                aaa=aaa,
                crud=crud,
                layer=layer,
                cache=cache if cache else Option(),
                search=search if search else Option(),
                database=database if database else Option()
            )
        )
        return TypedDictClass

    return inner


#===============================================================================
# Schema Abstraction
#===============================================================================
class IdentSchema:

    id:Key = ''
    sref:Key = ''
    uref:Key = ''

    def setID(self, id:Key | None=None):
        schemaInfo = self.__class__.getSchemaInfo()
        self.id = id if id else str(uuid4())
        self.sref = schemaInfo.sref
        self.uref = f'{schemaInfo.path}/{self.id}'
        return self

    def getReference(self):
        return Reference(id=self.id, sref=self.sref, uref=self.uref)


class StatusSchema:

    owner:Key = ''
    deleted:bool = False
    tstamp:int = 0

    def updateStatus(self, owner=None):
        if owner: self.owner = owner
        self.tstamp = int(tstamp())
        return self

    def setDeleted(self):
        self.deleted = True
        self.tstamp = int(tstamp())
        return self


class BaseSchema(StatusSchema, IdentSchema):

    #===========================================================================
    # schema info
    #===========================================================================
    @classmethod
    def setSchemaInfo(cls, service, version, control=None, provider=None, createHandler=None, updateHandler=None, deleteHandler=None):
        schemaInfo = cls.getSchemaInfo()
        schemaInfo.service = service
        schemaInfo.major = version
        schemaInfo.control = control
        schemaInfo.provider = provider
        lowerSchemaRef = schemaInfo.sref.lower()
        schemaInfo.dref = snakecase(f'{lowerSchemaRef}.{version}.{schemaInfo.minor}')
        schemaInfo.path = f'/{service}/v{version}/{pathcase(lowerSchemaRef)}'
        if createHandler: schemaInfo.createHandler = createHandler
        if updateHandler: schemaInfo.updateHandler = updateHandler
        if deleteHandler: schemaInfo.deleteHandler = deleteHandler
        if '__pydantic_config__' not in Reference.__dict__: Reference.__pydantic_config__ = ConfigDict(schemaMap={})
        Reference.__pydantic_config__['schemaMap'][schemaInfo.sref] = cls

    @classmethod
    def getSchemaInfo(cls): return cls.__pydantic_config__['schemaInfo']

    #===========================================================================
    # crud
    #===========================================================================
    async def readModel(
        self,
        token=None
    ):
        id = str(self.id)
        if not self.id: raise EpException(400, 'Bad Request')
        schemaInfo = self.__class__.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkRead(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                async with AsyncRest(schemaInfo.provider) as req: return schemaInfo.ref(**(await req.get(self.uref, headers=headers)))
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            model = await schemaInfo.control.readModel(schemaInfo, id)
            if model: return schemaInfo.ref(**model)
            else: raise EpException(404, 'Not Found')
        else: raise EpException(501, 'Not Implemented')

    @classmethod
    async def readModelByID(
        cls,
        id:Key,
        token=None
    ):
        id = str(id)
        schemaInfo = cls.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkRead(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                async with AsyncRest(schemaInfo.provider) as req: return cls(**(await req.get(f'{schemaInfo.path}/{id}', headers=headers)))
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            model = await schemaInfo.control.readModel(schemaInfo, id)
            if model: return cls(**model)
            else: raise EpException(404, 'Not Found')
        else: raise EpException(501, 'Not Implemented')

    @classmethod
    async def searchModels(cls,
        filter:str | None=None,
        orderBy:str | None=None,
        order:Literal['asc', 'desc']=None,
        size:int | None=None,
        skip:int | None=None,
        archive:bool | None=None,
        token=None
    ):
        schemaInfo = cls.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkRead(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                query = {}
                if filter: query['$filter'] = filter
                if orderBy and order:
                    query['$orderby'] = orderBy
                    query['$order'] = order
                if size: query['$size'] = size
                if skip: query['$skip'] = skip
                if archive: query['$archive'] = archive
                url = f'{schemaInfo.path}?{urlencode(query)}' if query else schemaInfo.path
                async with AsyncRest(schemaInfo.provider) as req: models = await req.get(url, headers=headers)
                return [cls(**model) for model in models]
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            if filter: filter = parseLucene.parse(filter)
            models = await schemaInfo.control.searchModels(schemaInfo, Search(filter=filter, orderBy=orderBy, order=order, size=size, skip=skip), archive)
            return [cls(**model) for model in models]
        else: raise EpException(501, 'Not Implemented')

    @classmethod
    async def countModels(cls,
        filter:str | None=None,
        archive:bool | None=None,
        token=None
    ):
        schemaInfo = cls.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkRead(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                query = {}
                if filter: query['$filter'] = filter
                if archive: query['$archive'] = archive
                url = f'{schemaInfo.path}/count?{urlencode(query)}' if query else f'{schemaInfo.path}/count'
                async with AsyncRest(schemaInfo.provider) as req: count = await req.get(url, headers=headers)
                return ModelCount(**count)
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            if filter: filter = parseLucene.parse(filter)
            return await schemaInfo.control.countModels(schemaInfo, Search(filter=filter), archive)
        else: raise EpException(501, 'Not Implemented')

    async def createModel(
        self,
        token=None
    ):
        schemaInfo = self.__class__.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkCreate(schemaInfo.crud):
                if schemaInfo.createHandler: await schemaInfo.createHandler(self)
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                async with AsyncRest(schemaInfo.provider) as req: model = await req.post(schemaInfo.path, headers=headers, json=self.model_dump())
                return self.__class__(**model)
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            await schemaInfo.control.createModel(schemaInfo, self.setID().updateStatus().model_dump())
            model = await schemaInfo.control.readModel(schemaInfo, str(self.id))
            if model: return schemaInfo.ref(**model)
            else: raise EpException(409, 'Conflict')
        else: raise EpException(501, 'Not Implemented')

    async def updateModel(
        self,
        token=None
    ):
        if not self.id: raise EpException(400, 'Bad Request')
        id = str(self.id)
        schemaInfo = self.__class__.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkUpdate(schemaInfo.crud):
                if schemaInfo.updateHandler: await schemaInfo.updateHandler(self)
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                async with AsyncRest(schemaInfo.provider) as req: model = await req.put(f'{schemaInfo.path}/{id}', headers=headers, json=self.model_dump())
                return self.__class__(**model)
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            await schemaInfo.control.updateModel(schemaInfo, self.updateStatus().model_dump())
            model = await schemaInfo.control.readModel(schemaInfo, id)
            if model: return schemaInfo.ref(**model)
            else: raise EpException(409, 'Conflict')
        else: raise EpException(501, 'Not Implemented')

    async def deleteModel(
        self,
        token=None,
        force=False
    ):
        if not self.id: raise EpException(400, 'Bad Request')
        id = str(self.id)
        schemaInfo = self.__class__.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkDelete(schemaInfo.crud):
                if schemaInfo.deleteHandler: await schemaInfo.deleteHandler(self)
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                force = '?$force=true' if force else ''
                async with AsyncRest(schemaInfo.provider) as req: status = await req.delete(f'{schemaInfo.path}/{id}{force}', headers=headers)
                return ModelStatus(**status)
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            await schemaInfo.control.deleteModel(schemaInfo, id, self.setDeleted().model_dump(), force)
            return ModelStatus(id=id, sref=schemaInfo.sref, uref=f'{schemaInfo.path}/{id}', status='deleted')
        else: raise EpException(501, 'Not Implemented')

    @classmethod
    async def deleteModelByID(
        cls,
        id:Key,
        token=None,
        force=False
    ):
        id = str(id)
        schemaInfo = cls.getSchemaInfo()
        if schemaInfo.provider:
            if CRUD.checkDelete(schemaInfo.crud):
                headers = {'Authorization': f'{token.scheme} {token.credentials}' if token else f'Bearer {schemaInfo.control.getSystemToken()}'}
                force = '?$force=true' if force else ''
                async with AsyncRest(schemaInfo.provider) as req: status = await req.delete(f'{schemaInfo.path}/{id}{force}', headers=headers)
                return ModelStatus(**status)
            else: raise EpException(405, 'Method Not Allowed')
        elif schemaInfo.control:
            await schemaInfo.control.deleteModel(schemaInfo, id, (await schemaInfo.control.readModel(schemaInfo, id)).setDeleted().model_dump(), force)
            return ModelStatus(id=id, sref=schemaInfo.sref, uref=f'{schemaInfo.path}/{id}', status='deleted')
        else: raise EpException(501, 'Not Implemented')


class ProfSchema:

    name:Key = ''
    displayName:str = ''
    description:str = ''


class TagSchema:

    tags:list[str] = []

    def setTag(self, tag):
        if tag not in self.tags: self.tags.append(tag)
        return self

    def delTag(self, tag):
        if tag in self.tags: self.tags.pop(tag)
        return self


class MetaSchema:

    metadata:str = '{}'

    def getMeta(self, key):
        metadata = self.getMetadata()
        if key in metadata: return metadata[key]
        else: None

    def setMeta(self, key, value):
        metadata = self.getMetadata()
        if key in metadata:
            preval = metadata[key]
            if isinstance(preval, list): preval.append(value)
            else: preval = [preval, value]
            metadata[key] = preval
        else: metadata[key] = value
        self.setMetadata(**metadata)
        return self

    def getMetadata(self): return json.loads(self.metadata)

    def setMetadata(self, **metadata):
        self.metadata = json.dumps(metadata, separators=(',', ':'))
        return self
