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
from fastapi.responses import PlainTextResponse
from common import ID, AUTH_HEADER
from schema.secret.certification import Authority, Server
from schema.secret.access import OpenSsh
from .controls import Control

#===============================================================================
# SingleTone
#===============================================================================
ctrl = Control(__file__)
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.get(f'{ctrl.uriver}/certification/authority/{{id}}/key', tags=['Certification Secret'])
async def download_ca_certification_key(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await Authority.readModelByID(id, token)).key)


@api.get(f'{ctrl.uriver}/certification/authority/{{id}}/crt', tags=['Certification Secret'])
async def download_ca_certification_crt(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await Authority.readModelByID(id, token)).crt)


@api.get(f'{ctrl.uriver}/certification/server/{{id}}/key', tags=['Certification Secret'])
async def download_server_certification_key(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await Server.readModelByID(id, token)).key)


@api.get(f'{ctrl.uriver}/certification/server/{{id}}/crt', tags=['Certification Secret'])
async def download_server_certification_crt(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await Server.readModelByID(id, token)).crt)


@api.get(f'{ctrl.uriver}/access/openssh/{{id}}/privatekey', tags=['Access Secret'])
async def download_openssh_private_crt(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await OpenSsh.readModelByID(id, token)).pri)


@api.get(f'{ctrl.uriver}/access/openssh/{{id}}/publickey', tags=['Access Secret'])
async def download_openssh_public_key(token: AUTH_HEADER, id: ID) -> PlainTextResponse:
    return PlainTextResponse((await OpenSsh.readModelByID(id, token)).pub)
