# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from pydantic import BaseModel
from common import SECONDS, AAA, SchemaConfig, Option, Reference, ID, Key, BaseSchema, ProfSchema


#===============================================================================
# Implement
#===============================================================================
class Csr(BaseModel):
    countryName:Key
    stateOrProvinceName:Key
    localityName:Key
    organizationName:Key
    organizationalUnitName:Key
    commonName:Key


@SchemaConfig(
version=1,
aaa=AAA.AAG,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Authority(BaseModel, ProfSchema, BaseSchema):
    csr: Csr
    emailAddress:Key = ''
    rsaBits: int = 4096
    expiry: int = 10
    key: Key = ''
    crt: Key = ''


@SchemaConfig(
version=1,
aaa=AAA.AAG,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Server(BaseModel, ProfSchema, BaseSchema):
    ca: Reference
    distinguishedName:Key
    emailAddress:Key = ''
    rsaBits: int = 4096
    expiry: int = 10
    key:Key = ''
    crt:Key = ''
