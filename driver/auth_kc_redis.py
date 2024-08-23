# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
try: import LOG  # @UnresolvedImport
except: pass

from common import asleep, mergeArray, getNewsAndDelsArray, getSharesArray, runBackground, EpException
from common import AuthDriverBase, AuthInfo, Org, Account, Role, Group
from driver.keyclock import KeyCloak
from driver.redis import RedisAuthn


#===============================================================================
# Implement
#===============================================================================
class AuthKeyCloakRedis(AuthDriverBase):

    def __init__(self, config):
        AuthDriverBase.__init__(self, config)
        self._authKeyCloak = KeyCloak(config)
        self._authRedis = RedisAuthn(config)

        self._authSystemUsername = config['default']['system_access_key']
        self._authSystemPassword = config['default']['system_secret_key']

        self._authDefaultOrg = config['default']['tenant']
        self._authDefaultOrgName = config['default']['title']
        self._authDefaultOrgDomain = config['default']['endpoint']
        self._authDefaultUsername = config['default']['admin_username']

        self._authRoleRoot = config['keycloak']['role_root']
        self._authRoleAttr = config['keycloak']['role_attr']
        self._authRoleAdmin = config['keycloak']['role_admin']
        self._authRoleUser = config['keycloak']['role_user']

        self._authGroupRoot = config['keycloak']['group_root']
        self._authGroupAttr = config['keycloak']['group_attr']
        self._authGroupAdmin = config['keycloak']['group_admin']
        self._authGroupUser = config['keycloak']['group_user']

        self._authRefreshAuth = int(config['keycloak']['refresh_auth'])
        self._authRefreshRole = int(config['keycloak']['refresh_role'])

        self._authRefresh = True
        self._authAuthMap = {}
        self._authRoleMap = {}
        self._authAdminList = {}

    async def connect(self):
        await self._authKeyCloak.connect()
        await self._authRedis.connect()

        if not await Org.searchModels(filter=f'name:{self._authDefaultOrg}', archive=True):
            await Org(
                org=self._authDefaultOrg,
                name=self._authDefaultOrg,
                displayName=self._authDefaultOrgName
            ).createModel()

        await runBackground(self.__refresh_auth_map__())
        await runBackground(self.__refresh_role_map__())
        return self

    async def disconnect(self):
        self._authRefresh = False
        await self._authRedis.disconnect()
        await self._authKeyCloak.disconnect()

    async def __refresh_auth_map__(self):
        while self._authRefresh:
            await asleep(self._authRefreshAuth)
            self._authAuthMap = {}

    async def __refresh_role_map__(self):
        while self._authRefresh:
            await asleep(self._authRefreshRole)
            await self.refreshRoleMap()

    async def refreshRoleMap(self):
        adminList = []
        roleMap = {}
        for role in await Role.searchModels(archive=True):
            if role.org not in roleMap: roleMap[role.org] = {}
            if role.admin: adminList.append(role.id)
            roleMap[role.org][role.name] = role
        self._authAdminList = adminList
        self._authRoleMap = roleMap

    async def getAuthInfo(self, org:str, token:str):
        if token in self._authAuthMap: return self._authAuthMap[token]
        authInfo = await self._authRedis.read(token)
        if authInfo:
            authInfo = AuthInfo(**authInfo)
            self._authAuthMap[token] = authInfo
            return authInfo
        else:
            roleMap = self._authRoleMap
            if not org: org = self._authDefaultOrg
            userInfo = await self._authKeyCloak.getUserInfo(org, token)
            roles = userInfo[self._authRoleAttr] if self._authRoleAttr in userInfo else []
            admin = False
            for role in self._authAdminList:
                if role in roles: admin = True; break
            aclRead = []
            aclCreate = []
            aclUpdate = []
            aclDelete = []
            if not admin:
                for role in roles:
                    if role not in roleMap: continue
                    role = roleMap[role]
                    aclRead = mergeArray(aclRead, role.aclRead)
                    aclCreate = mergeArray(aclCreate, role.aclCreate)
                    aclUpdate = mergeArray(aclUpdate, role.aclUpdate)
                    aclDelete = mergeArray(aclDelete, role.aclDelete)

            authInfoDict = {
                'org': org,
                'username': userInfo['preferred_username'],
                'admin': admin,
                'roles': roles,
                'aclRead': aclRead,
                'aclCreate': aclCreate,
                'aclUpdate': aclUpdate,
                'aclDelete': aclDelete
            }

            await runBackground(self._authRedis.write(token, authInfoDict))
            authInfo = AuthInfo(**authInfoDict)
            self._authAuthMap[token] = authInfo
            return authInfo

    async def createOrg(self, org:dict):
        if not org['name']: raise EpException(400, 'Bad Request')
        if not org['displayName']: raise EpException(400, 'Bad Request')
        orgName = org['name']

        org['externalId'] = (await self._authKeyCloak.createRealm(orgName, org['displayName']))['id']
        await self._authKeyCloak.createGroup(orgName, self._authRoleRoot)
        await self._authKeyCloak.createGroup(orgName, self._authGroupRoot)

        role = await Role(org=orgName, name=self._authRoleAdmin, displayName=self._authRoleAdmin, admin=True).createModel()
        roleAdminId = str(role.id)
        role = await Role(org=orgName, name=self._authRoleUser, displayName=self._authRoleUser).createModel()
        roleUserId = str(role.id)
        group = await Group(org=orgName, name=self._authGroupAdmin, displayName=self._authGroupAdmin).createModel()
        groupAdminId = str(group.id)
        group = await Group(org=orgName, name=self._authGroupUser, displayName=self._authGroupUser).createModel()
        groupUserId = str(group.id)

        await self.refreshRoleMap()

        systemUser = await Account(
            org=orgName,
            username=self._authSystemUsername,
            displayName=self._authSystemUsername,
            givenName=self._authSystemUsername,
            familyName=self._authSystemUsername,
            email=f'{self._authSystemUsername}@{self._authDefaultOrgDomain}',
            roles=[roleAdminId],
            groups=[groupAdminId]
        ).createModel()
        await self.updatePassword(systemUser.model_dump(), self._authSystemPassword)

        await Account(
            org=orgName,
            username=self._authDefaultUsername,
            displayName=self._authDefaultUsername,
            givenName=self._authDefaultUsername,
            familyName=self._authDefaultUsername,
            email=f'{self._authDefaultUsername}@{self._authDefaultOrgDomain}',
            roles=[roleAdminId, roleUserId],
            groups=[groupAdminId, groupUserId]
        ).createModel()

        return org

    async def updateOrg(self, org:dict):
        await self._authKeyCloak.updateRealmDisplayName(org['name'], org['displayName'])
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

        await runBackground(self.refreshRoleMap())
        return org

    async def createRole(self, role:dict):
        orgName = role['org']
        if not orgName: raise EpException(400, 'Bad Request')
        roleName = role['id']
        roleRootId = (await self._authKeyCloak.findGroup(orgName, self._authRoleRoot))['id']
        role['externalId'] = (await self._authKeyCloak.createGroup(orgName, roleName, roleRootId, {self._authRoleAttr: [roleName]}))['id']
        return role

    async def deleteRole(self, role:dict):
        await self._authKeyCloak.deleteGroup(role['org'], role['externalId'])
        return role

    async def createGroup(self, group:dict):
        orgName = group['org']
        if not orgName: raise EpException(400, 'Bad Request')
        groupName = group['id']
        groupRootId = (await self._authKeyCloak.findGroup(orgName, self._authGroupRoot))['id']
        group['externalId'] = (await self._authKeyCloak.createGroup(orgName, groupName, groupRootId, {self._authGroupAttr: [groupName]}))['id']
        return group

    async def updateGroup(self, group:dict):
        await self._authKeyCloak.updateGroupName(group['org'], group['externalId'], group['name'])
        return group

    async def deleteGroup(self, group:dict):
        await self._authKeyCloak.deleteGroup(group['org'], group['externalId'])
        return group

    async def createAccount(self, account:dict):
        orgName = account['org']
        if not orgName: raise EpException(400, 'Bad Request')

        userId = (await self._authKeyCloak.createUser(
            realm=orgName,
            username=account['username'],
            email=account['email'],
            firstName=account['givenName'],
            lastName=account['familyName']
        ))['id']
        account['externalId'] = userId

        roleMap = self._authRoleMap
        if not account['roles']: account['roles'] = [self._authRoleUser]
        roles = []
        for role in account['roles']:
            try: await self._authKeyCloak.registerUserToGroup(orgName, userId, roleMap[orgName][role].externalId)
            except: pass
            else: roles.append(role)
        account['roles'] = roles

        if not account['groups']: account['groups'] = [self._authGroupUser]
        groups = []
        for groupId in account['groups']:
            try:
                group = await Group.readModelByID(groupId)
                await self._authKeyCloak.registerUserToGroup(orgName, userId, group.externalId)
            except: pass
            else: groups.append(groupId)
        account['groups'] = groups

        return account

    async def updateAccount(self, account:dict):
        await self.refreshRoleMap()

        current = await Account.readModelByID(account['id'])
        orgName = account['org']
        userId = account['externalId']
        accountRole = account['roles']
        currentRole = current['roles']

        roleMap = self._authRoleMap
        news, dels = getNewsAndDelsArray(accountRole, currentRole)
        roles = getSharesArray(accountRole, currentRole)
        for role in news:
            try: await self._authKeyCloak.registerUserToGroup(orgName, userId, roleMap[orgName][role].externalId)
            except: pass
            else: roles.append(role)
        for role in dels:
            try: await self._authKeyCloak.unregisterUserFromGroup(orgName, userId, roleMap[orgName][role].externalId)
            except: pass
        account['roles'] = roles
        await self._authKeyCloak.updateUserProperty(
            realm=orgName,
            userId=userId,
            email=account['email'],
            firstName=account['givenName'],
            lastName=account['familyName']
        )
        return account

    async def updatePassword(self, account:dict, password:str):
        await self._authKeyCloak.updateUserPassword(account['org'], account['externalId'], password)
        return account

    async def deleteAccount(self, account:dict):
        await self._authKeyCloak.deleteUser(account['org'], account['externalId'])
        return account
