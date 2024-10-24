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
import json
import inspect
from uuid import UUID
from pydantic import BaseModel
from stringcase import snakecase
from psycopg import AsyncConnection
from luqum.tree import Item, Term, SearchField, Group, FieldGroup, Range, From, To, AndOperation, OrOperation, Not, UnknownOperation
from common import asleep, runBackground, EpException, Search, ModelDriverBase, SchemaInfo


#===============================================================================
# Implement
#===============================================================================
class PostgreSql(ModelDriverBase):

    def __init__(self, control):
        ModelDriverBase.__init__(self, control)
        psqlConf = self.control.config['postgresql']
        self.psqlHostname = psqlConf['hostname']
        self.psqlHostport = int(psqlConf['hostport'])
        self.psqlDatabase = psqlConf['database']
        self.psqlConn = None
        self.psqlConnectionRestoreMutex = False

    async def connect(self, *args, **kargs):
        if not self.psqlConn:
            self.psqlConn = await AsyncConnection.connect(
                host=self.psqlHostname,
                port=self.psqlHostport,
                dbname=self.psqlDatabase,
                user=self.control.systemAccessKey,
                password=self.control.systemSecretKey
            )
        return self

    async def disconnect(self):
        if self.psqlConn:
            try: await self.psqlConn.close()
            except: pass
            self.psqlConn = None
        if self.psqlConn:
            try: await self.psqlConn.close()
            except: pass
            self.psqlConn = None

    async def reconnect(self):
        if not self.psqlConnectionRestoreMutex:
            self.psqlConnectionRestoreMutex = True
            await runBackground(self.__restore_background__())

    async def __restore_background__(self):
        while True:
            await asleep(1)
            await self.disconnect()
            try: await self.connect()
            except: continue
            break
        self.psqlConnectionRestoreMutex = False

    def __parseLuceneToTsquery__(self, node:Item):
        nodeType = type(node)
        if isinstance(node, Term):
            terms = filter(None, str(node.value).strip('"').lower().split(' '))
            return f"{'|'.join(terms)}"
        elif nodeType == SearchField:
            if '.' in node.name: fieldName = snakecase(node.name.split('.')[0])
            else: fieldName = snakecase(node.name)
            exprType = type(node.expr)
            if exprType in [Range, From, To]:
                if exprType == Range: return f'{fieldName} >= {node.expr.low} AND {fieldName} <= {node.expr.high}'
                elif exprType == From: return f"{fieldName} >{'=' if node.expr.include else ''} {node.expr.a}"
                elif exprType == To: return f"{fieldName} <{'=' if node.expr.include else ''} {node.expr.a}"
            else:
                result = self.__parseLuceneToTsquery__(node.expr)
                if result: return f"{fieldName}@@to_tsquery('{result}')"
            return None
        elif nodeType == Group:
            result = self.__parseLuceneToTsquery__(node.expr)
            if result: return f'({result})'
            return None
        elif nodeType == FieldGroup:
            return self.__parseLuceneToTsquery__(node.expr)
        elif nodeType == AndOperation:
            operand1 = node.operands[0]
            operand2 = node.operands[1]
            result1 = self.__parseLuceneToTsquery__(operand1)
            result2 = self.__parseLuceneToTsquery__(operand2)
            if result1 and result2:
                if (isinstance(operand1, Term) or type(operand1) == Not) and (isinstance(operand2, Term) or type(operand2) == Not): return f'{result1}&{result2}'
                else: return f'{result1} AND {result2}'
            return None
        elif nodeType == OrOperation:
            operand1 = node.operands[0]
            operand2 = node.operands[1]
            result1 = self.__parseLuceneToTsquery__(operand1)
            result2 = self.__parseLuceneToTsquery__(operand2)
            if result1 and result2:
                if (isinstance(operand1, Term) or type(operand1) == Not) and (isinstance(operand2, Term) or type(operand2) == Not): return f'{result1}|{result2}'
                else: return f'{result1} OR {result2}'
            return None
        elif nodeType == Not:
            result = self.__parseLuceneToTsquery__(node.a)
            if result:
                if isinstance(node.a, Term): return f'!{result}'
                else: return f'NOT {result}'
            return None
        elif nodeType == UnknownOperation:
            if hasattr(node, 'operands'):
                operand = str(node.operands[1]).upper()
                if operand == 'AND': opermrk = '&'
                elif operand == 'OR': opermrk = '|'
                elif operand == '&':
                    opermrk = operand
                    operand = 'AND'
                elif operand == '|':
                    opermrk = operand
                    operand = 'OR'
                else: raise EpException(400, f'Could Not Parse Filter: {node} >> {nodeType}{node.__dict__}')
                operand1 = node.operands[0]
                operand2 = node.operands[2]
                if (isinstance(operand1, Term) or type(operand1) == Not) and (isinstance(operand2, Term) or type(operand2) == Not):
                    return f"{self.__parseLuceneToTsquery__(operand1)}{opermrk}{self.__parseLuceneToTsquery__(operand2)}"
                else:
                    return f"{self.__parseLuceneToTsquery__(operand1)} {operand} {self.__parseLuceneToTsquery__(operand2)}"
        raise EpException(400, f'Could Not Parse Filter: {node} >> {nodeType}{node.__dict__}')

    def __json_dumper__(self, d): return "'" + json.dumps(d, separators=(',', ':')).replace("'", "\'") + "'"

    def __text_dumper__(self, d): return f"'{str(d)}'"

    def __data_dumper__(self, d): return str(d)

    def __json_loader__(self, d): return json.loads(d)

    def __data_loader__(self, d): return d

    async def registerModel(self, schemaInfo:SchemaInfo, *args, **kargs):
        schema = schemaInfo.ref
        fields = sorted(schema.model_fields.keys())
        snakes = [snakecase(field) for field in fields]

        index = 0
        columns = []
        dumpers = []
        loaders = []
        indices = {}
        for field in fields:
            fieldType = schema.model_fields[field].annotation
            if fieldType == str:
                columns.append(f'{snakes[index]} TEXT')
                dumpers.append(self.__text_dumper__)
                loaders.append(self.__data_loader__)
                indices[fields[index]] = index
            elif fieldType == int:
                columns.append(f'{snakes[index]} INTEGER')
                dumpers.append(self.__data_dumper__)
                loaders.append(self.__data_loader__)
                indices[fields[index]] = index
            elif fieldType == float:
                columns.append(f'{snakes[index]} DOUBLE PRECISION')
                dumpers.append(self.__data_dumper__)
                loaders.append(self.__data_loader__)
                indices[fields[index]] = index
            elif fieldType == bool:
                columns.append(f'{snakes[index]} BOOL')
                dumpers.append(self.__data_dumper__)
                loaders.append(self.__data_loader__)
                indices[fields[index]] = index
            elif fieldType == UUID:
                if field == 'id': columns.append(f'id TEXT PRIMARY KEY')
                else: columns.append(f'{snakes[index]} TEXT')
                dumpers.append(self.__text_dumper__)
                loaders.append(self.__data_loader__)
                indices[fields[index]] = index
            elif (inspect.isclass(fieldType) and issubclass(fieldType, BaseModel)):
                columns.append(f'{snakes[index]} TEXT')
                dumpers.append(self.__json_dumper__)
                loaders.append(self.__json_loader__)
                indices[fields[index]] = index
            elif fieldType in [list, dict]:
                columns.append(f'{snakes[index]} TEXT')
                dumpers.append(self.__json_dumper__)
                loaders.append(self.__json_loader__)
                indices[fields[index]] = index
            elif getattr(fieldType, '__origin__', None) in [list, dict]:
                columns.append(f'{snakes[index]} TEXT')
                dumpers.append(self.__json_dumper__)
                loaders.append(self.__json_loader__)
                indices[fields[index]] = index
            else: raise EpException(500, f'database.registerModel({schema}.{field}{fieldType}): could not parse schema')
            index += 1

        schemaInfo.database['fields'] = fields
        schemaInfo.database['snakes'] = snakes
        schemaInfo.database['dumpers'] = dumpers
        schemaInfo.database['loaders'] = loaders
        schemaInfo.database['indices'] = indices

        try: await self.connect()
        except: exit(1)
        async with self.psqlConn.cursor() as cursor:
            await cursor.execute(f"CREATE TABLE IF NOT EXISTS {schemaInfo.dref} ({','.join(columns)});")
            await self.psqlConn.commit()

    async def read(self, schemaInfo:SchemaInfo, id:str):
        query = f"SELECT * FROM {schemaInfo.dref} WHERE id='{id}' AND deleted=FALSE LIMIT 1;"
        cursor = self.psqlConn.cursor()
        try:
            await cursor.execute(query)
            record = await cursor.fetchone()
        except Exception as e:
            await cursor.close()
            await self.reconnect()
            raise e
        await cursor.close()

        if record:
            fields = schemaInfo.database['fields']
            loaders = schemaInfo.database['loaders']
            index = 0
            model = {}
            for column in record:
                model[fields[index]] = loaders[index](column)
                index += 1
            return model
        return None

    async def search(self, schemaInfo:SchemaInfo, search:Search):
        unique = False

        if search.filter:
            filter = self.__parseLuceneToTsquery__(search.filter)
            if filter: filter = [filter]
            else: filter = []
        else: filter = []
        condition = ' AND '.join(filter)
        if condition: condition = f' AND {condition}'
        if search.orderBy and search.order: condition = f'{condition} ORDER BY {snakecase(search.orderBy)} {search.order.upper()}'
        if search.size:
            if search.size == 1: unique = True
            condition = f'{condition} LIMIT {search.size}'
        if search.skip: condition = f'{condition} OFFSET {search.skip}'
        query = f'SELECT * FROM {schemaInfo.dref} WHERE deleted=FALSE{condition};'

        cursor = self.psqlConn.cursor()
        try:
            await cursor.execute(query)
            if unique:
                records = await cursor.fetchone()
                if records: records = [records]
                else: records = []
            else: records = await cursor.fetchall()
        except Exception as e:
            await cursor.close()
            await self.reconnect()
            raise e
        await cursor.close()

        fields = schemaInfo.database['fields']
        loaders = schemaInfo.database['loaders']
        models = []
        for record in records:
            index = 0
            model = {}
            for column in record:
                model[fields[index]] = loaders[index](column)
                index += 1
            models.append(model)
        return models

    async def count(self, schemaInfo:SchemaInfo, search:Search):

        if search.filter:
            filter = self.__parseLuceneToTsquery__(search.filter)
            if filter: filter = [filter]
            else: filter = []
        else: filter = []
        condition = ' AND '.join(filter)
        if condition: condition = f' AND {condition}'
        query = f'SELECT COUNT(*) FROM {schemaInfo.dref} WHERE deleted=FALSE{condition};'

        cursor = self.psqlConn.cursor()
        try:
            await cursor.execute(query)
            count = await cursor.fetchone()
        except Exception as e:
            await cursor.close()
            await self.reconnect()
            raise e
        await cursor.close()
        return count[0]

    async def create(self, schemaInfo:SchemaInfo, *models):
        if models:
            fields = schemaInfo.database['fields']
            dumpers = schemaInfo.database['dumpers']
            cursor = self.psqlConn.cursor()
            try:
                for model in models:
                    index = 0
                    values = []
                    for field in fields:
                        values.append(dumpers[index](model[field]))
                        index += 1
                    query = f"INSERT INTO {schemaInfo.dref} VALUES({','.join(values)});"
                    await cursor.execute(query)
                    await cursor.execute(f"SELECT COUNT(*) FROM {schemaInfo.dref} WHERE id='{model['id']}';")
                results = [bool(result) for result in await cursor.fetchall()]
                await self.psqlConn.commit()
            except Exception as e:
                await cursor.close()
                await self.reconnect()
                raise e
            await cursor.close()
            return results
        return []

    async def update(self, schemaInfo:SchemaInfo, *models):
        if models:
            fields = schemaInfo.database['fields']
            snakes = schemaInfo.database['snakes']
            dumpers = schemaInfo.database['dumpers']
            cursor = self.psqlConn.cursor()
            try:
                for model in models:
                    id = model['id']
                    index = 0
                    values = []
                    for field in fields:
                        value = dumpers[index](model[field])
                        values.append(f'{snakes[index]}={value}')
                        index += 1
                    query = f"UPDATE {schemaInfo.dref} SET {','.join(values)} WHERE id='{id}' AND deleted=FALSE;"
                    await cursor.execute(query)
                    await cursor.execute(f"SELECT COUNT(*) FROM {schemaInfo.dref} WHERE id='{id}' AND deleted=FALSE;")
                results = [bool(result) for result in await cursor.fetchall()]
                await self.psqlConn.commit()
            except Exception as e:
                await cursor.close()
                await self.reconnect()
                raise e
            await cursor.close()
            return results
        return []

    async def delete(self, schemaInfo:SchemaInfo, id:str):
        query = f"DELETE FROM {schemaInfo.dref} WHERE id='{id}';"
        cursor = self.psqlConn.cursor()
        try:
            await cursor.execute(query)
            await cursor.execute(f"SELECT COUNT(*) FROM {schemaInfo.dref} WHERE id='{id}';")
            result = [bool(not result[0]) for result in await cursor.fetchall()][0]
            await self.psqlConn.commit()
        except Exception as e:
            await cursor.close()
            await self.reconnect()
            raise e
        await cursor.close()
        return result
