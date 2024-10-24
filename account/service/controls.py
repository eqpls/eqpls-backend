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
from common import mergeArray, runBackground, asleep, EpException, BaseControl, AuthInfo
from driver.keyclock import KeyCloak
from driver.redis import RedisAccount
from driver.minio import Minio


#===============================================================================
# Implement
#===============================================================================
class Control(BaseControl):

    def __init__(self, path):
        BaseControl.__init__(self, path)
        self.keycloak = KeyCloak(self)
        self.redis = RedisAccount(self)
        self.minio = Minio(self)

    async def startup(self):
        await self.keycloak.connect()
        await self.redis.connect()
        await self.minio.connect()
        try: await self.keycloak.readRealm(self.tenant)
        except EpException as e:
            if e.status_code != 404: raise e
            await self.keycloak.createRealm(self.tenant, self.title)
            await self.minio.updatePolicy(self.adminRoleName, '*/*')
            await self.minio.updatePolicyDetail(
                self.userRoleName,
                [{
                    'Effect': 'Allow',
                    'Action': ['s3:*'],
                    'Resource': [
                        'arn:aws:s3:::g.user.*/*',
                        'arn:aws:s3:::u.${jwt:preferred_username}.*/*'
                    ]
                }]
            )
            await self.minio.post('/api/v1/idp/openid', {
                'name': self.tenant,
                'input': f'config_url=http://{self.keycloak.kcHostname}:{self.keycloak.kcHostport}/auth/realms/{self.tenant}/.well-known/openid-configuration client_id=minio client_secret={await self.keycloak.getClientSecret(self.tenant, "minio")} claim_name=groups display_name={self.title} scopes=openid redirect_uri=https://{self.endpoint}/minio/oauth/callback '
            })
            try: await self.minio.post('/api/v1/service/restart', {})
            except Exception as e: LOG.DEBUG(e)
        except Exception as e: raise e
        self.userGroupId = (await self.keycloak.readGroupByName(self.tenant, self.userGroupName))['id']
        await runBackground(self.__syncSystemToken__())

    async def shutdown(self):
        await self.minio.disconnect()
        await self.redis.disconnect()
        await self.keycloak.disconnect()

    async def __syncSystemToken__(self):
        tokens = None
        while True:
            if tokens:
                try: tokens = await self.keycloak.loginByRefreshToken(self.tenant, self.tenant, tokens['refresh_token'])
                except: tokens = await self.keycloak.login(self.tenant, self.tenant, self.systemAccessKey, self.systemSecretKey)
            else: tokens = await self.keycloak.login(self.tenant, self.tenant, self.systemAccessKey, self.systemSecretKey)
            await self.redis.write('systemToken', tokens['access_token'])
            await asleep(600)

    async def login(self, username:str, password:str):
        return await self.keycloak.login(self.tenant, self.tenant, username, password)

    async def logout(self, refreshToken:str):
        return await self.keycloak.logout(self.tenant, self.tenant, refreshToken)

    async def getUserInfo(self, token):
        userInfo = await self.keycloak.getUserInfo(self.tenant, token.credentials)
        userId = userInfo['sub']
        return {
            'id': userId,
            'username': userInfo['preferred_username'],
            'email': userInfo['email'],
            'admin': True if self.adminRoleName in userInfo['groups'] else False,
            'firstName': userInfo['given_name'],
            'lastName': userInfo['family_name'],
            'groups': userInfo['groups']
        }

    async def getAuthInfo(self, token):
        authInfo = await self.redis.read(token.credentials)
        if not authInfo:
            userInfo = await self.getUserInfo(token)
            groups = userInfo['groups']
            aclRead = []
            aclCreate = []
            aclUpdate = []
            aclDelete = []
            if self.adminRoleName in groups: admin = True
            else:
                admin = False
                for roleName in groups:
                    role = await self.keycloak.readRoleByName(self.tenant, roleName)
                    rAclRead = []
                    rAclCreate = []
                    rAclUpdate = []
                    rAclDelete = []
                    for sref, crud in role['attributes'].items():
                        crud = crud[0]
                        if 'c' in crud: rAclCreate.append(sref)
                        if 'r' in crud: rAclRead.append(sref)
                        if 'u' in crud: rAclUpdate.append(sref)
                        if 'd' in crud: rAclDelete.append(sref)
                    aclRead = mergeArray(aclRead, rAclRead)
                    aclCreate = mergeArray(aclCreate, rAclCreate)
                    aclUpdate = mergeArray(aclUpdate, rAclUpdate)
                    aclDelete = mergeArray(aclDelete, rAclDelete)
            authInfo = {
                'id': userInfo['id'],
                'username': userInfo['username'],
                'email': userInfo['email'],
                'admin': admin,
                'groups': groups,
                'aclRead': aclRead,
                'aclCreate': aclCreate,
                'aclUpdate': aclUpdate,
                'aclDelete': aclDelete
            }
            await self.redis.write(token.credentials, authInfo)
        return AuthInfo(**authInfo)
