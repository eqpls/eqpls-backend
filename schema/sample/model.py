# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from typing import List
from pydantic import BaseModel
from common import SECONDS, SchemaConfig, Option, Key, BaseSchema, ProfSchema, TagSchema, MetaSchema


#===============================================================================
# Implement
#===============================================================================
class User(BaseModel, ProfSchema): pass


@SchemaConfig(
version=1,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Blog(BaseModel, MetaSchema, TagSchema, BaseSchema):
    title:Key = ''
    text:str = ''
    owner:User
    subscriptions:List[User] = []


@SchemaConfig(
version=1,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Message(BaseModel, BaseSchema):
    text:str = ''
    owner:User
