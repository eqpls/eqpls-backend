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
import inspect
import datetime
from uuid import UUID
from time import time as tstamp
from pydantic import BaseModel
from elasticsearch import AsyncElasticsearch, helpers
from luqum.elasticsearch import ElasticsearchQueryBuilder, SchemaAnalyzer
from common import EpException, Search, ModelDriverBase, SchemaInfo


#===============================================================================
# Implement
#===============================================================================
class ElasticSearch(ModelDriverBase):

    def __init__(self, control):
        ModelDriverBase.__init__(self, control)
        defConf = self.control.config['default']
        esConf = self.control.config['elasticsearch']
        self.esUsername = defConf['system_access_key']
        self.esPassword = defConf['system_secret_key']
        self.esHostname = esConf['hostname']
        self.esHostport = int(esConf['hostport'])
        self.esShards = int(esConf['shards'])
        self.esReplicas = int(esConf['replicas'])
        self.esExpire = int(esConf['expire'])
        self.esConn = None

    async def initialize(self, *args, **kargs): await self.connect()

    async def connect(self, *args, **kargs):
        await self.disconnect()
        if not self.esConn:
            self.esConn = AsyncElasticsearch(
                f'https://{self.esHostname}:{self.esHostport}',
                basic_auth=(self.esUsername, self.esPassword),
                verify_certs=False,
                ssl_show_warn=False
            )
        return self

    async def disconnect(self):
        if self.esConn:
            try: await self.esConn.close()
            except: pass
            self.esConn = None

    async def registerModel(self, schemaInfo:SchemaInfo, *args, **kargs):
        schema = schemaInfo.ref

        if 'shards' not in schemaInfo.search or not schemaInfo.search['shards']: schemaInfo.search['shards'] = self.esShards
        if 'replicas' not in schemaInfo.search or not schemaInfo.search['replicas']: schemaInfo.search['replicas'] = self.esReplicas
        if 'expire' not in schemaInfo.search or not schemaInfo.search['expire']: schemaInfo.search['expire'] = self.esExpire

        def parseModelToMapping(schema):

            def parseTermToMapping(fieldType, fieldMeta):
                if fieldType == str:
                    if 'keyword' in fieldMeta: return {'type': 'keyword'}
                    else: return {'type': 'text'}
                elif fieldType == int: return {'type': 'long'}
                elif fieldType == float: return {'type': 'double'}
                elif fieldType == bool: return {'type': 'boolean'}
                elif fieldType == UUID: return {'type': 'keyword'}
                elif fieldType == datetime: return {'type': 'date'}
                return None

            def parseTermsToMapping(fieldType):
                if fieldType == str: return {'type': 'keyword'}
                elif fieldType == int: return {'type': 'long'}
                elif fieldType == float: return {'type': 'double'}
                elif fieldType == bool: return {'type': 'boolean'}
                elif fieldType == UUID: return {'type': 'keyword'}
                elif fieldType == datetime: return {'type': 'date'}
                return None

            mapping = {}
            for field in schema.model_fields.keys():
                fieldData = schema.model_fields[field]
                fieldType = fieldData.annotation
                fieldMeta = fieldData.metadata
                esFieldType = parseTermToMapping(fieldType, fieldMeta)
                if not esFieldType:
                    if inspect.isclass(fieldType) and issubclass(fieldType, BaseModel):
                        esFieldType = {'properties': parseModelToMapping(fieldType)}
                    elif getattr(fieldType, '__origin__', None) == list:
                        fieldType = fieldType.__args__[0]
                        esFieldType = parseTermsToMapping(fieldType)
                        if not esFieldType:
                            esFieldType = {'type': 'nested', 'properties': parseModelToMapping(fieldType)}
                    else: raise EpException(500, f'search.registerModel({schema}.{field}{fieldType}): could not parse schema')
                mapping[field] = esFieldType
            return mapping

        mapping = parseModelToMapping(schema)
        mapping['_expireAt'] = {'type': 'long'}
        indexSchema = {
            'settings': {
                'number_of_shards': schemaInfo.search['shards'],
                'number_of_replicas': schemaInfo.search['replicas']
            },
            'mappings': {
                'properties': mapping
            }
        }
        if not await self.esConn.indices.exists(index=schemaInfo.dref): await self.esConn.indices.create(index=schemaInfo.dref, body=indexSchema)
        schemaInfo.search['filter'] = ElasticsearchQueryBuilder(**SchemaAnalyzer(indexSchema).query_builder_options())

    async def read(self, schemaInfo:SchemaInfo, id:str):
        try: model = (await self.esConn.get(index=schemaInfo.dref, id=id, source_excludes=['_expireAt'])).body['_source']
        except: model = None
        return model

    async def search(self, schemaInfo:SchemaInfo, search:Search):
        if search.filter: filter = schemaInfo.search['filter'](search.filter)
        else: filter = {'match_all': {}}
        if search.orderBy and search.order: sort = [{search.orderBy: search.order}]
        else: sort = None
        models = await self.esConn.search(index=schemaInfo.dref, source_excludes=['_expireAt'], query=filter, sort=sort, from_=search.skip, size=search.size)
        return [model['_source'] for model in models['hits']['hits']]

    async def count(self, schemaInfo:SchemaInfo, search:Search):
        if search.filter: filter = schemaInfo.search['filter'](search.filter)
        else: filter = {'match_all': {}}
        return (await self.esConn.count(index=schemaInfo.dref, query=filter))['count']

    def __set_search_expire__(self, model, expire):
        model['_expireAt'] = expire
        return model

    async def __generate_bulk_data__(self, schemaInfo:SchemaInfo, models):
        expire = int(tstamp()) + schemaInfo.search['expire']
        for model in models:
            yield {
                '_op_type': 'update',
                '_index': schemaInfo.dref,
                '_id': model['id'],
                'doc': self.__set_search_expire__(model, expire),
                'doc_as_upsert': True
            }

    async def create(self, schemaInfo:SchemaInfo, *models):
        if models:
            try: await helpers.async_bulk(self.esConn, self.__generate_bulk_data__(schemaInfo, models))
            except helpers.BulkIndexError as e: await self.create(schemaInfo, *models)
            except Exception as e: raise e

    async def update(self, schemaInfo:SchemaInfo, *models):
        if models:
            try: await helpers.async_bulk(self.esConn, self.__generate_bulk_data__(schemaInfo, models))
            except helpers.BulkIndexError as e: await self.update(schemaInfo, *models)
            except Exception as e: raise e

    async def delete(self, schemaInfo:SchemaInfo, id:str): await self.esConn.delete(index=schemaInfo.dref, id=id)
