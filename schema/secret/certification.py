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
    countryName:Key = ''
    stateOrProvinceName:Key = ''
    localityName:Key = ''
    organizationName:Key = ''
    organizationalUnitName:Key = ''
    commonName:Key = ''
    emailAddress:Key = ''


@SchemaConfig(
version=1,
aaa=AAA.AA,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Authority(BaseModel, ProfSchema, BaseSchema):
    csr: Csr
    key: Key
    crt: Key


class AuthorityRequest(BaseModel):
    displayName: str
    csr: Csr
    rsaBits: int = 4096
    expiry: int = 10


@SchemaConfig(
version=1,
aaa=AAA.AA,
cache=Option(expire=SECONDS.HOUR),
search=Option(expire=SECONDS.DAY))
class Server(BaseModel, ProfSchema, BaseSchema):
    csr: Csr
    ca: Reference
    key: Key
    crt: Key


class ServerRequest(BaseModel):
    authorityId: ID
    displayName: str
    distinguishedName: Key
    rsaBits: int = 4096
    expiry: int = 10
