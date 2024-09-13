# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import json
from common import asleep, mergeArray, getNewsAndDelsArray, getRandomLower, runBackground, EpException
from common import AuthDriverBase, AuthInfo, Org, Account, Role, Group, Reference
from driver.keyclock import KeyCloak
from driver.redis import RedisAuthn
from driver.minio import Minio

#===============================================================================
# Constants
#===============================================================================
REFRESH_AUTH_SEC = 30


#===============================================================================
# Implement
#===============================================================================
class KeycloakRedisMinio(AuthDriverBase):

    def __init__(self, config):
        AuthDriverBase.__init__(self, config)

        self._authKeyCloak = KeyCloak(config)
        self._authRedis = RedisAuthn(config)
        self._authMinio = Minio(config)

        self._authOrg = config['default']['tenant']
        self._authOrgDisplayName = config['default']['title']
        self._authOrgDomain = config['default']['domain']
        self._authEndpoint = config['default']['endpoint']

        self._authSystemUsername = config['default']['system_access_key']
        self._authSystemPassword = config['default']['system_secret_key']
        self._authAdminUsername = config['default']['admin_username']
        self._authAdminPassword = config['default']['admin_password']

        self._authRefresh = True
        self._authAuthMap = {}

        self._authDefaultUserRole = {}
        self._authDefaultUserGroup = {}

    async def connect(self):
        await self._authKeyCloak.connect()
        await self._authRedis.connect()

        if not await Org.searchModels(filter=f'name:{self._authOrg}', archive=True):
            await Org(
                org=self._authOrg,
                name=self._authOrg,
                displayName=self._authOrgDisplayName
            ).createModel()
        else:
            await Org.searchModels(archive=True)
            await Role.searchModels(archive=True)
            await Group.searchModels(archive=True)

        await runBackground(self.__refresh_auth_map__())
        return self

    async def disconnect(self):
        self._authRefresh = False
        await self._authRedis.disconnect()
        await self._authKeyCloak.disconnect()

    async def __refresh_auth_map__(self):
        while self._authRefresh:
            self._authAuthMap = {}
            await asleep(REFRESH_AUTH_SEC)

    async def getAuthInfo(self, org:str, token:str):
        if token in self._authAuthMap: return self._authAuthMap[token]
        authInfo = await self._authRedis.read(token)
        if authInfo:
            authInfo = AuthInfo(**authInfo)
            self._authAuthMap[token] = authInfo
            return authInfo
        else:
            if not org: org = self._authOrg
            userInfo = await self._authKeyCloak.getUserInfo(org, token)
            roles = userInfo['roles'] if 'roles' in userInfo else []
            groups = userInfo['groups'] if 'groups' in userInfo else []
            aclRead = []
            aclCreate = []
            aclUpdate = []
            aclDelete = []
            admin = False
            for role in roles:
                role = await Role.readModelByID(role)
                if role:
                    if role.type == 'admin': admin = True
                    aclRead = mergeArray(aclRead, role.aclRead)
                    aclCreate = mergeArray(aclCreate, role.aclCreate)
                    aclUpdate = mergeArray(aclUpdate, role.aclUpdate)
                    aclDelete = mergeArray(aclDelete, role.aclDelete)

            authInfoDict = {
                'org': org,
                'username': userInfo['preferred_username'],
                'admin': admin,
                'roles': roles,
                'groups': groups,
                'aclRead': aclRead,
                'aclCreate': aclCreate,
                'aclUpdate': aclUpdate,
                'aclDelete': aclDelete
            }

            await runBackground(self._authRedis.write(token, authInfoDict))
            authInfo = AuthInfo(**authInfoDict)
            self._authAuthMap[token] = authInfo
            return authInfo

    async def getClientSecret(self, org:str, client:str):
        return await self._authKeyCloak.getClientSecret(org, client)

    async def getDefaultUserRole(self, org:str):
        if org not in self._authDefaultUserRole:
            role = await Role.searchModels(filter=f'org:{org} AND type:default')
            if role: self._authDefaultUserRole[org] = str(role[0].id)
            else: raise EpException(503, 'Service Unavailable')
        return self._authDefaultUserRole[org]

    async def getDefaultUserGroup(self, org:str):
        if org not in self._authDefaultUserGroup:
            group = await Group.searchModels(filter=f'org:{org} AND type:default')
            if group: self._authDefaultUserGroup[org] = str(group[0].id)
            else: raise EpException(503, 'Service Unavailable')
        return self._authDefaultUserGroup[org]

    async def createBucket(self, bucket:dict):
        owner = bucket['owner']
        if owner == await self.getDefaultUserGroup(bucket['org']): raise EpException(403, 'Forbidden')
        externalId = f'{owner}.{getRandomLower(8)}'
        payload = {
            'name': externalId,
            'locking': False,
            'versioning': {
                'enabled': False,
                'excludePrefixes': [],
                'excludeForlders': False
            }
        }
        quota = bucket['quota']
        if quota:
            payload['quota'] = {
                'enabled': True,
                'quota_type': 'hard',
                'amount': quota * 1073741824
            }

        await self._authMinio.post('/api/v1/buckets', payload)
        bucket['externalId'] = externalId
        return bucket

    async def updateBucket(self, bucket:dict):
        externalId = bucket['externalId']
        quota = bucket['quota']
        if quota:
            await self._authMinio.put(f'/api/v1/buckets/{externalId}/quota', {
                'enabled': True,
                'quota_type': 'hard',
                'amount': quota * 1073741824
            })
        else:
            await self._authMinio.put(f'/api/v1/buckets/{externalId}/quota', {
                'enabled': False,
                'quota_type': 'hard',
                'amount': 1073741824
            })
        return bucket

    async def deleteBucket(self, bucket:dict):
        externalId = bucket['externalId']
        await self._authMinio.delete(f'/api/v1/buckets/{externalId}', {'name': externalId})
        return bucket

    async def createOrg(self, org:dict):
        if not org['name']: raise EpException(400, 'Bad Request')
        if not org['displayName']: raise EpException(400, 'Bad Request')
        realmId = org['name']
        kcRealm = await self._authKeyCloak.createRealm(realmId, org['displayName'])
        org['externalId'] = kcRealm['id']

        roleAdmin = await Role(org=realmId, name='admin', displayName='Admin', type='admin').createModel()
        roleAdminId = str(roleAdmin.id)

        defaultUserRole = await Role(org=realmId, name='user', displayName='User', type='default').createModel()
        self._authDefaultUserRole[realmId] = str(defaultUserRole.id)

        defaultUserGroup = await Group(org=realmId, name='users', displayName='Users', type='default', objectPolicy=False).createModel()
        defaultUserGroupId = str(defaultUserGroup.id)
        self._authDefaultUserGroup[realmId] = defaultUserGroupId

        await self._authMinio.post('/api/v1/policies', {
            'name': defaultUserGroupId,
            'policy': json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Effect': 'Allow',
                        'Action': ['s3:*'],
                        'Resource': ['arn:aws:s3:::${jwt:preferred_username}.*/*']
                    }
                ]
            })
        })

        systemUser = await Account(
            org=realmId,
            username=self._authSystemUsername,
            displayName=self._authSystemUsername,
            givenName=self._authSystemUsername,
            familyName=self._authSystemUsername,
            email=f'{self._authSystemUsername}@{self._authOrgDomain}',
            enabled=True,
            roles=[roleAdminId],
            groups=[],
            detail=Reference()
        ).createModel()
        await self.updatePassword(systemUser.model_dump(), self._authSystemPassword)

        adminUser = await Account(
            org=realmId,
            username=self._authAdminUsername,
            displayName=self._authAdminUsername,
            givenName=self._authAdminUsername,
            familyName=self._authAdminUsername,
            email=f'{self._authAdminUsername}@{self._authOrgDomain}',
            enabled=True,
            roles=[roleAdminId],
            groups=[],
            detail=Reference()
        ).createModel()
        await self.updatePassword(adminUser.model_dump(), self._authAdminPassword)

        minioSecret = await self._authKeyCloak.getClientSecret(realmId, 'minio')
        await self._authMinio.post('/api/v1/idp/openid', {
            'name': self._authOrgDisplayName,
            'input': f'config_url=http://{self._authKeyCloak._kcHostname}:{self._authKeyCloak._kcHostport}/auth/realms/{realmId}/.well-known/openid-configuration client_id=minio client_secret={minioSecret} display_name={self._authOrgDisplayName} scopes=openid redirect_uri=https://{self._authEndpoint}/minio/oauth/callback '
        })
        try: await self._authMinio.post('/api/v1/service/restart', {})
        except Exception as e:
            LOG.DEBUG(e)

        return org

    async def updateOrg(self, org:dict):
        kcRealm = await self._authKeyCloak.readRealm(org['name'])
        kcRealm['displayName'] = org['displayName']
        await self._authKeyCloak.updateRealm(kcRealm)
        return org

    async def deleteOrg(self, org:dict):
        orgName = org['name']

        for user in await Account.searchModels(filter=f'org:{orgName}'):
            try: await user.deleteModel()
            except: pass
        for group in await Group.searchModels(filter=f'org:{orgName}'):
            try: await group.deleteModel()
            except: pass
        for role in await Role.searchModels(filter=f'org:{orgName}'):
            try: await role.deleteModel()
            except: pass
        try: await self._authKeyCloak.deleteRealm(orgName)
        except: pass

        return org

    async def createRole(self, role:dict):
        roleId = role['id']
        kcRole = await self._authKeyCloak.createRole(
            realmId=role['org'],
            name=roleId,
            description=role['name'],
            attributes={'roles': [roleId]}
        )
        role['externalId'] = kcRole['id']
        return role

    async def updateRole(self, role:dict):
        realmId = role['org']
        kcRole = await self._authKeyCloak.readRole(realmId=realmId, roleId=role['externalId'])
        kcRole['description'] = role['name']
        await self._authKeyCloak.updateRole(realmId=realmId, role=kcRole)
        return role

    async def deleteRole(self, role:dict):
        if role['type'] == 'default': raise EpException(503, 'Service Unavailable')
        await self._authKeyCloak.deleteRole(realmId=role['org'], roleId=role['externalId'])
        return role

    async def createGroup(self, group:dict):
        groupId = group['id']
        kcGroup = await self._authKeyCloak.createGroup(
            realmId=group['org'],
            name=groupId,
            attributes={
                'policy': [groupId],
                'groups': [groupId]
            }
        )
        if group['objectPolicy']: await self._authMinio.createPolicy(groupId)
        group['externalId'] = kcGroup['id']
        return group

    async def updateGroup(self, group:dict):
        return group

    async def deleteGroup(self, group:dict):
        if group['type'] == 'default': raise EpException(503, 'Service Unavailable')
        if group['objectPolicy']: await self._authMinio.deletePolicy(group['id'])
        await self._authKeyCloak.deleteGroup(realmId=group['org'], groupId=group['externalId'])
        return group

    async def createAccount(self, account:dict):
        realmId = account['org']
        if not realmId: raise EpException(400, 'Bad Request')

        defaultUserRoleId = await self.getDefaultUserRole(realmId)
        defaultUserGroupId = await self.getDefaultUserGroup(realmId)

        username = account['username']
        kcUser = await self._authKeyCloak.createUser(
            realmId=realmId,
            username=username,
            email=account['email'],
            firstName=account['givenName'],
            lastName=account['familyName']
        )
        kcUserId = kcUser['id']
        account['externalId'] = kcUserId
        await self._authKeyCloak.updateUserEnabled(realmId=realmId, userId=kcUserId, enabled=account['enabled'])
        await self._authKeyCloak.updateUserPassword(realmId=realmId, userId=kcUserId, password=username)

        accountRoles = account['roles']
        if defaultUserRoleId not in accountRoles: accountRoles.append(defaultUserRoleId)
        kcRoleIds = []
        for role in accountRoles:
            role = await Role.readModelByID(role)
            if role: kcRoleIds.append(role.externalId)
        await self._authKeyCloak.insertUserRoles(
            realmId=realmId,
            userId=kcUserId,
            roleIds=kcRoleIds
        )

        accountGroups = account['groups']
        if defaultUserGroupId not in accountGroups: accountGroups.append(defaultUserGroupId)
        for group in accountGroups:
            group = await Group.readModelByID(group)
            if group:
                await self._authKeyCloak.registerUserToGroup(
                    realmId=realmId,
                    userId=kcUserId,
                    groupId=group.externalId
                )

        return account

    async def updateAccount(self, account:dict):
        current = await Account.readModelByID(account['id'])
        realmId = current.org
        kcUserId = current.externalId
        account['org'] = realmId
        account['externalId'] = kcUserId

        defaultUserRoleId = await self.getDefaultUserRole(realmId)
        defaultUserGroupId = await self.getDefaultUserGroup(realmId)

        kcUser = await self._authKeyCloak.readUser(realmId=realmId, userId=kcUserId)
        kcUser['email'] = account['email']
        kcUser['firstName'] = account['givenName']
        kcUser['lastName'] = account['familyName']
        await self._authKeyCloak.updateUser(realmId=realmId, user=kcUser)
        await self._authKeyCloak.updateUserEnabled(realmId=realmId, userId=kcUserId, enabled=account['enabled'])

        accountRoles = account['roles']
        if defaultUserRoleId not in accountRoles: accountRoles.append(defaultUserRoleId)
        newRoles, delRoles = getNewsAndDelsArray(accountRoles, current.roles)
        if newRoles:
            kcRoleIds = []
            for role in newRoles:
                role = await Role.readModelByID(role)
                if role: kcRoleIds.append(role.externalId)
            await self._authKeyCloak.insertUserRoles(
                realmId=realmId,
                userId=kcUserId,
                roleIds=kcRoleIds
            )
        if delRoles:
            kcRoleIds = []
            for role in delRoles:
                role = await Role.readModelByID(role)
                if role: kcRoleIds.append(role.externalId)
            await self._authKeyCloak.deleteUserRoles(
                realmId=realmId,
                userId=kcUserId,
                roleIds=kcRoleIds
            )

        accountGroups = account['groups']
        if defaultUserGroupId not in accountGroups: accountGroups.append(defaultUserGroupId)
        newGroups, delGroups = getNewsAndDelsArray(accountGroups, current.groups)
        if newGroups:
            for group in newGroups:
                group = await Group.readModelByID(group)
                if group:
                    await self._authKeyCloak.registerUserToGroup(
                        realmId=realmId,
                        userId=kcUserId,
                        groupId=group.externalId
                    )
        if delGroups:
            for group in delGroups:
                group = await Group.readModelByID(group)
                if group:
                    await self._authKeyCloak.unregisterUserFromGroup(
                        realmId=realmId,
                        userId=kcUserId,
                        groupId=group.externalId
                    )

        return account

    async def updatePassword(self, account:dict, password:str):
        await self._authKeyCloak.updateUserPassword(account['org'], account['externalId'], password)
        return account

    async def deleteAccount(self, account:dict):
        await self._authKeyCloak.deleteUser(account['org'], account['externalId'])
        return account
