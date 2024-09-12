# -*- coding: utf-8 -*-
'''
Created on 2024. 2. 8.
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import json
import aiohttp

from common import EpException, AsyncRest, DriverBase, encodeBase64


#===============================================================================
# Implement
#===============================================================================
class Minio(DriverBase):

    def __init__(self, config):
        DriverBase.__init__(self, config)

        self._mioAccessKey = config['default']['system_access_key']
        self._mioSecretKey = config['default']['system_secret_key']

        self._mioHostname = config['minio']['hostname']
        self._mioHostport = int(config['minio']['hostport'])

        self._mioBaseUrl = f'http://{self._mioHostname}:{self._mioHostport}'
        self._mioSession = AsyncRest(self._mioBaseUrl)
        self._mioSession.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), raise_for_status=True)

    async def connect(self, *args, **kargs):
        await self._mioSession.session.close()
        self._mioSession.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), raise_for_status=True)
        await self._mioSession.post('/api/v1/login', json={
            'accessKey': self._mioAccessKey,
            'secretKey': self._mioSecretKey
        })
        return self

    async def disconnect(self):
        await self._mioSession.session.close()

        async with AsyncRest(self._kcBaseUrl) as rest:
            await rest.post(f'/realms/master/protocol/openid-connect/logout',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'client_id=admin-cli&refresh_token={self._kcRefreshToken}'
            )

    #===========================================================================
    # Basic Rest Methods
    #===========================================================================
    async def get(self, url):
        try: return await self._mioSession.get(url)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).get(url)
            else: raise e

    async def post(self, url, payload):
        try: return await self._mioSession.post(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).post(url, payload)
            else: raise e

    async def put(self, url, payload):
        try: return await self._mioSession.put(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).put(url, payload)
            else: raise e

    async def patch(self, url, payload):
        try: return await self._mioSession.patch(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).patch(url, payload)
            else: raise e

    async def delete(self, url, payload=None):
        try: return await self._mioSession.delete(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).delete(url)
            else: raise e

    #===========================================================================
    # Master Interface
    #===========================================================================
    async def createPolicy(self, groupId:str):
        return await self.post('/api/v1/policies', {
            'name': groupId,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['s3:*'],
                        'Resource': [f'arn:aws:s3:::{groupId}.*/*']
                    }
                ]
            })
        })

    async def deletePolicy(self, groupId:str):
        await self.delete(f'/api/v1/policy/{encodeBase64(groupId)}')
        return True
