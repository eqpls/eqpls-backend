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
import random
from OpenSSL import crypto
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from common import SECONDS, ModelControl
from driver.redis import RedisAccount
from schema.secret.certification import Authority, Server
from schema.secret.access import OpenSsh


#===============================================================================
# Implement
#===============================================================================
class Control(ModelControl):

    def __init__(self, path): ModelControl.__init__(self, path, RedisAccount)

    async def startup(self):
        await self.registerModel(Authority, 'uerp', createHandler=self.createCaCertification)
        await self.registerModel(Server, 'uerp', createHandler=self.createServerCertification)
        await self.registerModel(OpenSsh, 'uerp', createHandler=self.createRsaKeys)

    async def createCaCertification(self, model, token):
        ca_key = crypto.PKey()
        ca_key.generate_key(crypto.TYPE_RSA, model.rsaBits)

        ca_cert = crypto.X509()
        ca_cert.set_version(2)
        ca_cert.set_serial_number(random.randint(50000000, 100000000))

        ca_sub = ca_cert.get_subject()
        ca_sub.countryName = model.csr.countryName
        ca_sub.stateOrProvinceName = model.csr.stateOrProvinceName
        ca_sub.localityName = model.csr.localityName
        ca_sub.organizationName = model.csr.organizationName
        ca_sub.organizationalUnitName = model.csr.organizationalUnitName
        ca_sub.commonName = model.csr.commonName
        if not model.emailAddress: model.emailAddress = (await self.checkAuthorization(token)).email
        ca_sub.emailAddress = model.emailAddress

        ca_cert.set_issuer(ca_sub)
        ca_cert.set_pubkey(ca_key)

        ca_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=ca_cert)])
        ca_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always,issuer', issuer=ca_cert)])
        ca_cert.add_extensions([crypto.X509Extension(b'basicConstraints', True, b'CA:TRUE')])

        ca_cert.gmtime_adj_notBefore(0)
        ca_cert.gmtime_adj_notAfter(model.expiry * SECONDS.YEAR)
        ca_cert.sign(ca_key, 'sha256')

        model.name = model.csr.commonName
        model.key = crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key).decode('utf-8')
        model.crt = crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert).decode('utf-8')

    async def createServerCertification(self, model, token):
        ca = await model.ca.readModel(token)
        serverCommonName = f'{model.distinguishedName}.{ca.csr.commonName}'

        server_key = crypto.PKey()
        server_key.generate_key(crypto.TYPE_RSA, model.rsaBits)

        server_cert = crypto.X509()
        server_cert.set_version(2)
        server_cert.set_serial_number(random.randint(50000000, 100000000))

        server_sub = server_cert.get_subject()
        server_sub.countryName = ca.csr.countryName
        server_sub.stateOrProvinceName = ca.csr.stateOrProvinceName
        server_sub.localityName = ca.csr.localityName
        server_sub.organizationName = ca.csr.organizationName
        server_sub.organizationalUnitName = ca.csr.organizationalUnitName
        server_sub.commonName = serverCommonName
        if not model.emailAddress: model.emailAddress = (await self.checkAuthorization(token)).email
        server_sub.emailAddress = model.emailAddress

        server_cert.set_issuer(server_sub)
        server_cert.set_pubkey(server_key)

        ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, ca.key)
        ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca.crt)

        server_cert.add_extensions([crypto.X509Extension(b'basicConstraints', False, b'CA:FALSE')])
        server_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid', issuer=ca_cert)])
        server_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=server_cert)])
        server_cert.add_extensions([crypto.X509Extension(b'keyUsage', False, b'nonRepudiation,digitalSignature,keyEncipherment')])
        server_cert.add_extensions([crypto.X509Extension(b'subjectAltName', False, f'DNS:{ca.csr.commonName},DNS:{serverCommonName}'.encode('ascii'))])

        server_cert.gmtime_adj_notBefore(0)
        server_cert.gmtime_adj_notAfter(model.expiry * SECONDS.YEAR)
        server_cert.sign(ca_key, 'sha256')

        model.name = serverCommonName
        model.key = crypto.dump_privatekey(crypto.FILETYPE_PEM, server_key).decode('utf-8')
        model.crt = crypto.dump_certificate(crypto.FILETYPE_PEM, server_cert).decode('utf-8')

    async def createRsaKeys(self, model, token):
        authInfo = await self.checkAuthorization(token)
        model.name = authInfo.username
        if not model.displayName: model.displayName = authInfo.email
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=model.rsaBits,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        model.pri = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        model.pub = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
