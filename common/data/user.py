# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from pydantic import BaseModel
from common import SECONDS, AAA, SchemaConfig, Option, Key, BaseSchema, ProfSchema


#===============================================================================
# Implement
#===============================================================================
@SchemaConfig(
version=1,
aaa=AAA.AAA,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Bucket(BaseModel, ProfSchema, BaseSchema):

    externalId: Key = ''
    quota: int = 0

