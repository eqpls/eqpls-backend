# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import random

from OpenSSL import crypto
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fastapi.responses import PlainTextResponse

from common import EpException, ID, AUTH_HEADER, ORG_HEADER

from .controls import Control

from schema.secret.certification import Csr, Authority, AuthorityRequest, Server, ServerRequest
from schema.secret.access import OpenSsh, OpenSsshRequest

#===============================================================================
# SingleTone
#===============================================================================
ctrl = Control(__file__)
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.post(f'{ctrl.uri}/certification/authority', tags=['Certification'])
async def create_ca_certification(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    req: AuthorityRequest
) -> Authority:
    if not req.displayName: raise EpException(400, 'displayName is required')
    if not req.csr.countryName: raise Exception('countryName is required')
    if not req.csr.stateOrProvinceName: raise Exception('stateOrProvinceName is required')
    if not req.csr.localityName: raise Exception('localityName is required')
    if not req.csr.organizationName: raise Exception('organizationName is required')
    if not req.csr.organizationalUnitName: raise Exception('organizationalUnitName is required')
    if not req.csr.commonName: raise Exception('commonName is required')
    if not req.csr.emailAddress: raise Exception('emailAddress is required')
    if not req.rsaBits: req.rsaBits = 4096
    if not req.expiry: req.expiry = 10

    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, req.rsaBits)

    ca_cert = crypto.X509()
    ca_cert.set_version(2)
    ca_cert.set_serial_number(random.randint(50000000, 100000000))

    ca_sub = ca_cert.get_subject()
    ca_sub.countryName = req.csr.countryName
    ca_sub.stateOrProvinceName = req.csr.stateOrProvinceName
    ca_sub.localityName = req.csr.localityName
    ca_sub.organizationName = req.csr.organizationName
    ca_sub.organizationalUnitName = req.csr.organizationalUnitName
    ca_sub.commonName = req.csr.commonName
    ca_sub.emailAddress = req.csr.emailAddress

    ca_cert.set_issuer(ca_sub)
    ca_cert.set_pubkey(ca_key)

    ca_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=ca_cert)])
    ca_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always,issuer', issuer=ca_cert)])
    ca_cert.add_extensions([crypto.X509Extension(b'basicConstraints', True, b'CA:TRUE')])

    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(req.expiry * 365 * 24 * 60 * 60)
    ca_cert.sign(ca_key, 'sha256')

    return await Authority(
        name=f'{req.csr.commonName}',
        displayName=req.displayName,
        csr=req.csr,
        key=crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key).decode('utf-8'),
        crt=crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert).decode('utf-8')
    ).createModel(org=org, token=token.credentials)


@api.get(f'{ctrl.uri}/certification/authority/{{id}}/key', tags=['Certification'])
async def download_ca_certification_key(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    cert = await Authority.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(cert.key)


@api.get(f'{ctrl.uri}/certification/authority/{{id}}/crt', tags=['Certification'])
async def download_ca_certification_crt(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    cert = await Authority.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(cert.crt)


@api.post(f'{ctrl.uri}/certification/server', tags=['Certification'])
async def create_server_certification(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    req: ServerRequest
) -> Server:
    if not req.authorityId: raise EpException(400, 'authorityId is required')
    if not req.displayName: raise EpException(400, 'displayName is required')
    if not req.distinguishedName: raise EpException(400, 'distinguishedName is required')
    if not req.rsaBits: req.rsaBits = 4096
    if not req.expiry: req.expiry = 10

    caCert = await Authority.readModelByID(req.authorityId)
    serverCommonName = f'{req.distinguishedName}.{caCert.csr.commonName}'

    server_key = crypto.PKey()
    server_key.generate_key(crypto.TYPE_RSA, req.rsaBits)

    server_cert = crypto.X509()
    server_cert.set_version(2)
    server_cert.set_serial_number(random.randint(50000000, 100000000))

    server_sub = server_cert.get_subject()
    server_sub.countryName = caCert.csr.countryName
    server_sub.stateOrProvinceName = caCert.csr.stateOrProvinceName
    server_sub.localityName = caCert.csr.localityName
    server_sub.organizationName = caCert.csr.organizationName
    server_sub.organizationalUnitName = caCert.csr.organizationalUnitName
    server_sub.commonName = serverCommonName
    server_sub.emailAddress = caCert.csr.emailAddress

    server_cert.set_issuer(server_sub)
    server_cert.set_pubkey(server_key)

    ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, caCert.crt)
    ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, caCert.key)

    server_cert.add_extensions([crypto.X509Extension(b'basicConstraints', False, b'CA:FALSE')])
    server_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid', issuer=ca_cert)])
    server_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=server_cert)])
    server_cert.add_extensions([crypto.X509Extension(b'keyUsage', False, b'nonRepudiation,digitalSignature,keyEncipherment')])
    server_cert.add_extensions([crypto.X509Extension(b'subjectAltName', False, f'DNS:{caCert.csr.commonName},DNS:{serverCommonName}'.encode('ascii'))])

    server_cert.gmtime_adj_notBefore(0)
    server_cert.gmtime_adj_notAfter(req.expiry * 365 * 24 * 60 * 60)
    server_cert.sign(ca_key, 'sha256')

    return await Server(
        name=serverCommonName,
        displayName=req.displayName,
        csr=Csr(
            countryName=caCert.csr.countryName,
            stateOrProvinceName=caCert.csr.stateOrProvinceName,
            localityName=caCert.csr.localityName,
            organizationName=caCert.csr.organizationName,
            organizationalUnitName=caCert.csr.organizationalUnitName,
            commonName=serverCommonName,
            emailAddress=caCert.csr.emailAddress
        ),
        ca=caCert.getReference(),
        key=crypto.dump_privatekey(crypto.FILETYPE_PEM, server_key).decode('utf-8'),
        crt=crypto.dump_certificate(crypto.FILETYPE_PEM, server_cert).decode('utf-8')
    ).createModel(org=org, token=token.credentials)


@api.get(f'{ctrl.uri}/certification/server/{{id}}/key', tags=['Certification'])
async def download_server_certification_key(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    cert = await Authority.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(cert.key)


@api.get(f'{ctrl.uri}/certification/server/{{id}}/crt', tags=['Certification'])
async def download_server_certification_crt(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    cert = await Authority.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(cert.crt)


@api.post(f'{ctrl.uri}/access/openssh', tags=['Remote Access'])
async def create_rsa(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    req: OpenSsshRequest
) -> OpenSsh:
    if not req.displayName: raise EpException(400, 'displayName is required')
    if not req.rsaBits: req.rsaBits = 4096

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=req.rsaBits,
        backend=default_backend()
    )
    public_key = private_key.public_key()

    return await OpenSsh(
        name='OpenSSH RSA Key',
        displayName=req.displayName,
        pri=private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8'),
        pub=public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
    ).createModel(org=org, token=token.credentials)


@api.get(f'{ctrl.uri}/access/openssh/{{id}}/privatekey', tags=['Remote Access'])
async def download_openssh_private_crt(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    keys = await OpenSsh.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(keys.pri)


@api.get(f'{ctrl.uri}/access/openssh/{{id}}/publickey', tags=['Remote Access'])
async def download_openssh_public_key(
    org: ORG_HEADER,
    token: AUTH_HEADER,
    id: ID
) -> PlainTextResponse:
    keys = await OpenSsh.readModelByID(id, org=org, token=token.credentials)
    return PlainTextResponse(keys.pub)
