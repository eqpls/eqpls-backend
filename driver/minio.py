# -*- coding: utf-8 -*-
'''
Created on 2024. 2. 8.
@author: Hye-Churn Jang
'''

try: import LOG  # @UnresolvedImport
except: pass
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

    def __init__(self, control):
        DriverBase.__init__(self, control)
        minConf = self.control.config['minio']
        self.minHostname = minConf['hostname']
        self.minHostport = int(minConf['hostport'])
        self.minBaseUrl = f'http://{self.minHostname}:{self.minHostport}'
        self.minSession = AsyncRest(self.minBaseUrl)
        self.minSession.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), raise_for_status=True)

    async def connect(self, *args, **kargs):
        await self.minSession.session.close()
        self.minSession.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), raise_for_status=True)
        await self.minSession.post('/api/v1/login', json={
            'accessKey': self.control.systemAccessKey,
            'secretKey': self.control.systemSecretKey
        })
        return self

    async def disconnect(self):
        await self.minSession.session.close()

    #===========================================================================
    # Basic Rest Methods
    #===========================================================================
    async def get(self, url):
        try: return await self.minSession.get(url)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).get(url)
            else: raise e

    async def post(self, url, payload):
        try: return await self.minSession.post(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).post(url, payload)
            else: raise e

    async def put(self, url, payload):
        try: return await self.minSession.put(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).put(url, payload)
            else: raise e

    async def patch(self, url, payload):
        try: return await self.minSession.patch(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).patch(url, payload)
            else: raise e

    async def delete(self, url, payload=None):
        try: return await self.minSession.delete(url, json=payload)
        except EpException as e:
            if e.status_code == 401 or e.status_code == 403: return await (await self.connect()).delete(url)
            else: raise e

    #===========================================================================
    # Master Interface
    #===========================================================================
    async def readPolicy(self, policy:str):
        return await self.get(f'/api/v1/policy/{encodeBase64(policy)}')

    async def createPolicy(self, policy:str, pattern:str):
        return await self.post('/api/v1/policies', {
            'name': policy,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['s3:*'],
                        'Resource': [f'arn:aws:s3:::{pattern}']
                    }
                ]
            })
        })

    async def createPolicyDetail(self, policy:str, statements:list):
        return await self.post('/api/v1/policies', {
            'name': policy,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': statements
            })
        })

    async def updatePolicy(self, policy:str, pattern:str):
        return await self.post('/api/v1/policies', {
            'name': policy,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['s3:*'],
                        'Resource': [f'arn:aws:s3:::{pattern}']
                    }
                ]
            })
        })

    async def updatePolicyDetail(self, policy:str, statements:list):
        return await self.post('/api/v1/policies', {
            'name': policy,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': statements
            })
        })

    async def deletePolicy(self, policy:str):
        await self.delete(f'/api/v1/policy/{encodeBase64(policy)}')
        return True

    async def createGroupBucket(self, owner:str, name:str, quota:int):
        bucketName = f'g.{owner}.{name}'
        payload = {
            'name': bucketName,
            'locking': False,
            'versioning': {
                'enabled': False,
                'excludePrefixes': [],
                'excludeForlders': False
            }
        }
        if quota:
            payload['quota'] = {
                'enabled': True,
                'quota_type': 'hard',
                'amount': quota * 1073741824
            }

        await self.post('/api/v1/buckets', payload)
        return bucketName

    async def createUserBucket(self, owner:str, name:str, quota:int):
        bucketName = f'u.{owner}.{name}'
        payload = {
            'name': bucketName,
            'locking': False,
            'versioning': {
                'enabled': False,
                'excludePrefixes': [],
                'excludeForlders': False
            }
        }
        if quota:
            payload['quota'] = {
                'enabled': True,
                'quota_type': 'hard',
                'amount': quota * 1073741824
            }

        await self.post('/api/v1/buckets', payload)
        return bucketName

    async def updateBucket(self, bucketName:str, quota:int):
        if quota:
            await self.put(f'/api/v1/buckets/{bucketName}/quota', {
                'enabled': True,
                'quota_type': 'hard',
                'amount': quota * 1073741824
            })
        else:
            await self.put(f'/api/v1/buckets/{bucketName}/quota', {
                'enabled': False,
                'quota_type': 'hard',
                'amount': 1073741824
            })
        return bucketName

    async def deleteBucket(self, bucketName:str):
        await self.delete(f'/api/v1/buckets/{bucketName}', {'name': bucketName})
        return bucketName
