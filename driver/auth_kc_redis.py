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
from common import AuthDriverBase, AuthInfo, Org, Account, Policy, Group
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

        self._authPolicyAttr = config['keycloak']['policy_attr']
        self._authPolicyAdmin = config['keycloak']['policy_admin']
        self._authPolicyUser = config['keycloak']['policy_user']
        self._authPolicyRoot = config['keycloak']['policy_root']

        self._authRefreshInfo = int(config['keycloak']['refresh_auth_info'])
        self._authRefreshPolicy = int(config['keycloak']['refresh_policy'])

        self._authRefresh = True
        self._authInfoMap = {}
        self._authPolicyMap = {}

    async def connect(self):
        await self._authKeyCloak.connect()
        await self._authRedis.connect()

        if not await Org.searchModels(filter=f'name:{self._authDefaultOrg}', archive=True):
            await Org(
                org=self._authDefaultOrg,
                name=self._authDefaultOrg,
                displayName=self._authDefaultOrgName
            ).createModel()

        await runBackground(self.__refresh_info_map__())
        await runBackground(self.__refresh_policy_map__())
        return self

    async def disconnect(self):
        self._authRefresh = False
        await self._authRedis.disconnect()
        await self._authKeyCloak.disconnect()

    async def __refresh_info_map__(self):
        while self._authRefresh:
            await asleep(self._authRefreshInfo)
            self._authInfoMap = {}

    async def __refresh_policy_map__(self):
        while self._authRefresh:
            await asleep(self._authRefreshPolicy)
            await self.refreshPolicyMap()

    async def refreshPolicyMap(self):
        policyMap = {}
        for policy in await Policy.searchModels(archive=True):
            if policy.org not in policyMap: policyMap[policy.org] = {}
            policyMap[policy.org][policy.name] = policy
        self._authPolicyMap = policyMap

    async def getAuthInfo(self, org:str, token:str):
        if token in self._authInfoMap: return self._authInfoMap[token]
        authInfo = await self._authRedis.read(token)
        if authInfo:
            authInfo = AuthInfo(**authInfo)
            self._authInfoMap[token] = authInfo
            return authInfo
        else:
            policyMap = self._authPolicyMap
            if not org: org = self._authDefaultOrg
            userInfo = await self._authKeyCloak.getUserInfo(org, token)
            policies = userInfo['policy'] if 'policy' in userInfo else []
            admin = True if self._authPolicyAdmin in policies else False
            aclRead = []
            aclCreate = []
            aclUpdate = []
            aclDelete = []
            for policy in policies:
                if policy not in policyMap: continue
                policy = policyMap[policy]
                aclRead = mergeArray(aclRead, policy.aclRead)
                aclCreate = mergeArray(aclCreate, policy.aclCreate)
                aclUpdate = mergeArray(aclUpdate, policy.aclUpdate)
                aclDelete = mergeArray(aclDelete, policy.aclDelete)

            authInfoDict = {
                'org': org,
                'username': userInfo['preferred_username'],
                'admin': admin,
                'policy': policies,
                'aclRead': aclRead,
                'aclCreate': aclCreate,
                'aclUpdate': aclUpdate,
                'aclDelete': aclDelete
            }

            await runBackground(self._authRedis.write(token, authInfoDict))
            authInfo = AuthInfo(**authInfoDict)
            self._authInfoMap[token] = authInfo
            return authInfo

    async def createOrg(self, org:dict):
        if not org['name']: raise EpException(400, 'Bad Request')
        if not org['displayName']: raise EpException(400, 'Bad Request')
        orgName = org['name']

        org['externalId'] = (await self._authKeyCloak.createRealm(orgName, org['displayName']))['id']
        await self._authKeyCloak.createGroup(orgName, self._authPolicyRoot)

        await Policy(org=orgName, name=self._authPolicyAdmin).createModel()
        await Policy(org=orgName, name=self._authPolicyUser).createModel()

        await self.refreshPolicyMap()

        systemUser = await Account(
            org=orgName,
            username=self._authSystemUsername,
            displayName=self._authSystemUsername,
            givenName=self._authSystemUsername,
            familyName=self._authSystemUsername,
            email=f'{self._authSystemUsername}@{self._authDefaultOrgDomain}',
            policy=[self._authPolicyAdmin]
        ).createModel()
        await self.updatePassword(systemUser.model_dump(), self._authSystemPassword)

        await Account(
            org=orgName,
            username=self._authDefaultUsername,
            displayName=self._authDefaultUsername,
            givenName=self._authDefaultUsername,
            familyName=self._authDefaultUsername,
            email=f'{self._authDefaultUsername}@{self._authDefaultOrgDomain}',
            policy=[self._authPolicyAdmin, self._authPolicyUser]
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

        for policy in await Policy.searchModels(filter=f'org:{orgName}'):
            try: await policy.deleteModel()
            except: pass

        try: await self._authKeyCloak.deleteRealm(orgName)
        except: pass

        await runBackground(self.refreshPolicyMap())
        return org

    async def createPolicy(self, policy:dict):
        orgName = policy['org']
        if not orgName: raise EpException(400, 'Bad Request')
        policyRootId = (await self._authKeyCloak.findGroup(orgName, self._authPolicyRoot))['id']
        policy['externalId'] = (await self._authKeyCloak.createGroup(orgName, policy['name'], policyRootId, {self._authPolicyAttr: [policy['name']]}))['id']
        return policy

    async def deletePolicy(self, policy:dict):
        await self._authKeyCloak.deleteGroup(policy['org'], policy['externalId'])
        return policy

    async def createGroup(self, group:dict):
        orgName = group['org']
        if not orgName: raise EpException(400, 'Bad Request')
        # for org in await Org.searchModels(filter=f'name:{orgName}', archive=True):
        #     for option in org.option:
        #         if option.key == 'groupRootId':
        #             groupRootId = option.value
        #             break
        #     else: raise EpException(404, 'Not Found')
        #     break
        groupRootId = (await self._authKeyCloak.findGroup(orgName, self._authGroupRoot))['id']
        group['externalId'] = (await self._authKeyCloak.createGroup(orgName, group['name'], groupRootId))['id']
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

        policyMap = self._authPolicyMap
        if not account['policy']: account['policy'] = [self._authPolicyUser]
        policies = []
        for policy in account['policy']:
            try: await self._authKeyCloak.registerUserToGroup(orgName, userId, policyMap[orgName][policy].externalId)
            except: pass
            else: policies.append(policy)
        account['policy'] = policies

        return account

    async def updateAccount(self, account:dict):
        await self.refreshPolicyMap()

        current = await Account.readModelByID(account['id'])
        orgName = account['org']
        userId = account['externalId']
        accountRole = account['policy']
        currentRole = current['policy']

        policyMap = self._authPolicyMap
        news, dels = getNewsAndDelsArray(accountRole, currentRole)
        policies = getSharesArray(accountRole, currentRole)
        for policy in news:
            try: await self._authKeyCloak.registerUserToGroup(orgName, userId, policyMap[orgName][policy].externalId)
            except: pass
            else: policies.append(policy)
        for policy in dels:
            try: await self._authKeyCloak.unregisterUserFromGroup(orgName, userId, policyMap[orgName][policy].externalId)
            except: pass
        account['policy'] = policies
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
