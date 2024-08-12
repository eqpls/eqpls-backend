# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os
import random
from OpenSSL import crypto
from stringcase import titlecase


#===============================================================================
# API Interfaces
#===============================================================================
def main(
    countryName:str,
    stateOrProvinceName:str,
    localityName:str,
    organizationName:str,
    organizationalUnitName:str,
    commonName:str,
    serverName:str,
    emailAddress:str,
    rsaBits:int,
    expiry:int
):
    curdir = os.path.dirname(os.path.realpath(__file__))

    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, rsaBits)

    ca_cert = crypto.X509()
    ca_cert.set_version(2)
    ca_cert.set_serial_number(random.randint(50000000, 100000000))

    ca_sub = ca_cert.get_subject()
    ca_sub.countryName = countryName
    ca_sub.stateOrProvinceName = stateOrProvinceName
    ca_sub.localityName = localityName
    ca_sub.organizationName = organizationName
    ca_sub.organizationalUnitName = organizationalUnitName
    ca_sub.commonName = commonName
    ca_sub.emailAddress = emailAddress

    ca_cert.set_issuer(ca_sub)
    ca_cert.set_pubkey(ca_key)

    ca_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=ca_cert)])
    ca_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always,issuer', issuer=ca_cert)])
    ca_cert.add_extensions([crypto.X509Extension(b'basicConstraints', True, b'CA:TRUE')])

    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(expiry * 365 * 24 * 60 * 60)
    ca_cert.sign(ca_key, 'sha256')

    with open(f'{curdir}/ca.key', 'w') as fd:
        fd.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key).decode('utf-8'))

    with open(f'{curdir}/ca.crt', 'w') as fd:
        fd.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert).decode('utf-8'))

    serverCommonName = f'{serverName}.{commonName}'

    server_key = crypto.PKey()
    server_key.generate_key(crypto.TYPE_RSA, rsaBits)

    server_cert = crypto.X509()
    server_cert.set_version(2)
    server_cert.set_serial_number(random.randint(50000000, 100000000))

    server_sub = server_cert.get_subject()
    server_sub.countryName = countryName
    server_sub.stateOrProvinceName = stateOrProvinceName
    server_sub.localityName = localityName
    server_sub.organizationName = organizationName
    server_sub.organizationalUnitName = organizationalUnitName
    server_sub.commonName = serverCommonName
    server_sub.emailAddress = emailAddress

    server_cert.set_issuer(server_sub)
    server_cert.set_pubkey(server_key)

    server_cert.add_extensions([crypto.X509Extension(b'basicConstraints', False, b'CA:FALSE')])
    server_cert.add_extensions([crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid', issuer=ca_cert)])
    server_cert.add_extensions([crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=server_cert)])
    server_cert.add_extensions([crypto.X509Extension(b'keyUsage', False, b'nonRepudiation,digitalSignature,keyEncipherment')])
    server_cert.add_extensions([crypto.X509Extension(b'subjectAltName', False, f'DNS:{commonName},DNS:{serverCommonName}'.encode('ascii'))])

    server_cert.gmtime_adj_notBefore(0)
    server_cert.gmtime_adj_notAfter(expiry * 365 * 24 * 60 * 60)
    server_cert.sign(ca_key, 'sha256')

    with open(f'{curdir}/server.key', 'w') as fd:
        fd.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, server_key).decode('utf-8'))

    with open(f'{curdir}/server.crt', 'w') as fd:
        fd.write(crypto.dump_certificate(crypto.FILETYPE_PEM, server_cert).decode('utf-8'))


if __name__ == '__main__':

    while True:
        countryName = input('Country Name (2 letter code) [XX]: ')
        if len(countryName):
            countryName = countryName.upper()
            break

    while True:
        stateOrProvinceName = input('State or Province Name (full name): ')
        if stateOrProvinceName:
            stateOrProvinceName = titlecase(stateOrProvinceName)
            break

    while True:
        localityName = input('Locality Name (eg, city): ')
        if localityName:
            localityName = titlecase(localityName)
            break

    while True:
        organizationName = input('Organization Name (eg, company): ')
        if organizationName:
            organizationName = titlecase(organizationName)
            break

    while True:
        organizationalUnitName = input('Organizational Unit Name (eg, section): ')
        if organizationalUnitName:
            organizationalUnitName = titlecase(organizationalUnitName)
            break

    while True:
        commonName = input('Domain Name (eg, your domain name): ')
        if commonName:
            commonName = commonName.lower()
            break

    while True:
        serverName = input("Server Name (eg, your name or your server's hostname): ")
        if serverName:
            serverName = serverName.lower()
            break

    while True:
        emailAddress = input('Email Address: ')
        if emailAddress:
            emailAddress = emailAddress.lower()
            break

    while True:
        rsaBits = input('RSA Bit Mask: ')
        try:
            rsaBits = int(rsaBits)
            if rsaBits % 1024 == 0 and rsaBits >= 1024: break
        except: pass

    while True:
        expiry = input('Expiry Years After [1~10]: ')
        try:
            expiry = int(expiry)
            if expiry > 0 and expiry <= 10: break
        except: pass

    main(
        countryName,
        stateOrProvinceName,
        localityName,
        organizationName,
        organizationalUnitName,
        commonName,
        serverName,
        emailAddress,
        rsaBits,
        expiry
    )
