# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

try: import LOG  # @UnresolvedImport
except: pass
#===============================================================================
# Import
#===============================================================================
from common import mergeArray, runBackground, asleep, BaseControl, AuthInfo, EpException
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
        self.accountDefaultAcl = self.config[f'{self.module}:acl']
        self.accountRestrict = self.config[f'{self.module}:restrict']
        self.accountRestrictGroupCodes = [code.strip() for code in self.accountRestrict['group_codes'].split(',')]

    async def startup(self):
        await self.redis.initialize()
        await self.keycloak.initialize(
            defaultAcl=self.accountDefaultAcl
        )
        await self.minio.initialize(
            keycloak={
                'hostname': self.keycloak.kcHostname,
                'hostport': self.keycloak.kcHostport,
                'clientSecret': await self.keycloak.getClientSecret(self.tenant, 'minio')
            }
        )
        self.userGroupId = (await self.keycloak.readGroupByName(self.tenant, self.userGroupName))['id']
        await runBackground(self.__syncSystemToken__())

    async def shutdown(self):
        await self.minio.disconnect()
        await self.redis.disconnect()
        await self.keycloak.disconnect()

    async def __syncSystemToken__(self):
        tokens = None
        while True:
            try:
                if tokens:
                    try: tokens = await self.keycloak.loginByRefreshToken(self.tenant, self.tenant, tokens['refresh_token'])
                    except: tokens = await self.keycloak.login(self.tenant, self.tenant, self.systemAccessKey, self.systemSecretKey)
                else: tokens = await self.keycloak.login(self.tenant, self.tenant, self.systemAccessKey, self.systemSecretKey)
                await self.redis.setSystemToken(tokens['access_token'])
            except Exception as e: EpException(500, e)
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
