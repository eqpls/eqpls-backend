# -*- coding: utf-8 -*-
'''
Created on 2024. 2. 8.
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from common import EpException, AsyncRest, DriverBase

#===============================================================================
# Constants
#===============================================================================
KEYCLOAK_SESSION_IDLE_SEC = 7200
KEYCLOAK_SESSION_MAX_SEC = 43200
KEYCLOAK_TOKEN_LIFE_SPAN_SEC = 7200


#===============================================================================
# Implement
#===============================================================================
class KeyCloak(DriverBase):

    def __init__(self, config):
        DriverBase.__init__(self, config)

        defConf = config['default']
        kcConf = config['keycloak']

        self._kcEndpoint = defConf['endpoint']
        self._kcEndpointUrl = f'https://{self._kcEndpoint}'
        self._origins = [origin.strip() for origin in defConf['origins'].split(',')] if 'origins' in defConf and defConf['origins'] else []
        if self._origins:
            if '*' in self._origins: self._origins = ['*']
            elif self._kcEndpointUrl not in self._origins: self._origins.append(self._kcEndpointUrl)

        self._kcUsername = defConf['system_access_key']
        self._kcPassword = defConf['system_secret_key']

        self._kcHostname = kcConf['hostname']
        self._kcHostport = int(kcConf['hostport'])
        self._kcBaseUrl = f'http://{self._kcHostname}:{self._kcHostport}/auth'
        self._kcTheme = kcConf['theme'] if 'theme' in kcConf and kcConf['theme'] else None

        self._kcHeaders = None
        self._kcAccessToken = None
        self._kcRefreshToken = None

    async def connect(self, *args, **kargs):
        async with AsyncRest(self._kcBaseUrl) as rest:
            tokens = await rest.post(f'/realms/master/protocol/openid-connect/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'client_id=admin-cli&grant_type=password&username={self._kcUsername}&password={self._kcPassword}'
            )
        self._kcAccessToken = tokens['access_token']
        self._kcRefreshToken = tokens['refresh_token']
        self._kcHeaders = {
            'Authorization': f'Bearer {self._kcAccessToken}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        return self

    async def disconnect(self):
        async with AsyncRest(self._kcBaseUrl) as rest:
            await rest.post(f'/realms/master/protocol/openid-connect/logout',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'client_id=admin-cli&refresh_token={self._kcRefreshToken}'
            )

    #===========================================================================
    # Basic Rest Methods
    #===========================================================================
    async def get(self, url):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.get(url, headers=self._kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).get(url)
                else: raise e

    async def post(self, url, payload):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.post(url, json=payload, headers=self._kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).post(url, payload)
                else: raise e

    async def put(self, url, payload):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.put(url, json=payload, headers=self._kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).put(url, payload)
                else: raise e

    async def patch(self, url, payload):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.patch(url, json=payload, headers=self._kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).patch(url, payload)
                else: raise e

    async def delete(self, url, payload=None):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.delete(url, json=payload, headers=self._kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).delete(url)
                else: raise e

    #===========================================================================
    # Master Interface
    #===========================================================================
    # Realm ####################################################################
    async def readRealm(self, realmId:str):
        if realmId != 'master': return await self.get(f'/admin/realms/{realmId}')
        return None

    async def searchRealms(self):
        results = []
        for realm in await self.get(f'/admin/realms'):
            if realm['realm'] != 'master': results.append(realm)
        return results

    async def createRealm(self, realmId:str, displayName:str):
        if realmId == 'master': raise EpException(400, 'Could not create realm with predefined name')
        await self.post(f'/admin/realms', {
            'realm': realmId,
            'displayName': displayName,
            'enabled': True
        })

        realm = await self.get(f'/admin/realms/{realmId}')
        realm['resetPasswordAllowed'] = True
        await self.put(f'/admin/realms/{realmId}', realm)

        if self._kcTheme:
            realm = await self.get(f'/admin/realms/{realmId}')
            realm['loginTheme'] = self._kcTheme
            await self.put(f'/admin/realms/{realmId}/ui-ext', realm)

        await self.post(f'/admin/realms/{realmId}/client-scopes', {
            'name': 'openid-client-scope',
            'description': 'openid-client-scope',
            'type': 'default',
            'protocol': 'openid-connect',
            'attributes': {
                'consent.screen.text': '',
                'display.on.consent.screen': True,
                'include.in.token.scope': True,
                'gui.order': ''
            }
        })
        for scope in await self.get(f'/admin/realms/{realmId}/client-scopes'):
            if scope['name'] == 'openid-client-scope': scopeId = scope['id']; break
        else: raise EpException(404, 'Could not find client scope')
        await self.post(f'/admin/realms/{realmId}/client-scopes/{scopeId}/protocol-mappers/models', {
            'name': 'policy',
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-attribute-mapper',
            'config': {
                'claim.name': 'policy',
                'user.attribute': 'policy',
                'jsonType.label': 'String',
                'multivalued': True,
                'aggregate.attrs': True,
                'id.token.claim': True,
                'access.token.claim': True,
                'lightweight.claim': False,
                'userinfo.token.claim': True,
                'introspection.token.claim': True
            }
        })
        await self.post(f'/admin/realms/{realmId}/client-scopes/{scopeId}/protocol-mappers/models', {
            'name': 'groups',
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-attribute-mapper',
            'config': {
                'claim.name': 'groups',
                'user.attribute': 'groups',
                'jsonType.label': 'String',
                'multivalued': True,
                'aggregate.attrs': True,
                'id.token.claim': True,
                'access.token.claim': True,
                'lightweight.claim': False,
                'userinfo.token.claim': True,
                'introspection.token.claim': True
            }
        })
        await self.post(f'/admin/realms/{realmId}/client-scopes/{scopeId}/protocol-mappers/models', {
            'name': 'roles',
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-realm-role-mapper',
            'config': {
                'claim.name': 'roles',
                'usermodel.realmRoleMapping.rolePrefix': '',
                'jsonType.label': 'String',
                'multivalued': True,
                'id.token.claim': True,
                'access.token.claim': True,
                'lightweight.claim': False,
                'userinfo.token.claim': True,
                'introspection.token.claim': True
            }
        })
        await self.delete(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}')
        await self.put(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': realmId,
            'name': realmId,
            'description': realmId,
            'protocol': 'openid-connect',
            'publicClient': True,
            'rootUrl': self._kcEndpointUrl,
            'baseUrl': self._kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self._origins,
            'authorizationServicesEnabled': False,
            'serviceAccountsEnabled': False,
            'implicitFlowEnabled': False,
            'directAccessGrantsEnabled': True,
            'standardFlowEnabled': True,
            'frontchannelLogout': True,
            'alwaysDisplayInConsole': True,
            'attributes': {
                'saml_idp_initiated_sso_url_name': '',
                'oauth2.device.authorization.grant.enabled': False,
                'oidc.ciba.grant.enabled': False,
                'post.logout.redirect.uris': '+'
            }
        })
        for client in await self.get(f'/admin/realms/{realmId}/clients'):
            if client['clientId'] == realmId: clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': 'guacamole',
            'name': 'guacamole',
            'description': 'guacamole',
            'protocol': 'openid-connect',
            'publicClient': True,
            'rootUrl': self._kcEndpointUrl,
            'baseUrl': self._kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self._origins,
            'authorizationServicesEnabled': False,
            'serviceAccountsEnabled': False,
            'implicitFlowEnabled': True,
            'directAccessGrantsEnabled': True,
            'standardFlowEnabled': False,
            'frontchannelLogout': True,
            'alwaysDisplayInConsole': False,
            'attributes': {
                'saml_idp_initiated_sso_url_name': '',
                'oauth2.device.authorization.grant.enabled': False,
                'oidc.ciba.grant.enabled': False,
            }
        })
        for client in await self.get(f'/admin/realms/{realmId}/clients'):
            if client['clientId'] == 'guacamole': clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': 'minio',
            'name': 'minio',
            'description': 'minio',
            'protocol': 'openid-connect',
            'publicClient': False,
            'rootUrl': self._kcEndpointUrl,
            'baseUrl': self._kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self._origins,
            'authorizationServicesEnabled': False,
            'serviceAccountsEnabled': False,
            'implicitFlowEnabled': False,
            'directAccessGrantsEnabled': True,
            'standardFlowEnabled': True,
            'frontchannelLogout': True,
            'alwaysDisplayInConsole': False,
            'attributes': {
                'saml_idp_initiated_sso_url_name': '',
                'oauth2.device.authorization.grant.enabled': False,
                'oidc.ciba.grant.enabled': False,
                'post.logout.redirect.uris': '+',
                'use.jwks.url': True
            }
        })
        for client in await self.get(f'/admin/realms/{realmId}/clients'):
            if client['clientId'] == 'minio':
                clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.put(f'/admin/realms/{realmId}', {
            'ssoSessionIdleTimeout': KEYCLOAK_SESSION_IDLE_SEC,
            'ssoSessionMaxLifespan': KEYCLOAK_SESSION_MAX_SEC,
            'accessTokenLifespan': KEYCLOAK_TOKEN_LIFE_SPAN_SEC,
            'accessTokenLifespanForImplicitFlow': KEYCLOAK_TOKEN_LIFE_SPAN_SEC,
            'revokeRefreshToken': True
        })
        return await self.readRealm(realmId)

    async def updateRealm(self, realm:dict):
        realmId = realm['realm']
        if realmId == 'master': raise EpException(400, 'Could not update realm with predefined name')
        await self.put(f'/admin/realms/{realmId}', realm)
        return await self.readRealm(realmId)

    async def deleteRealm(self, realmId:str):
        if realmId == 'master': raise EpException(400, 'Could not delete realm with predefined name')
        await self.delete(f'/admin/realms/{realmId}')
        return True

    # Client ###################################################################
    async def getClientSecret(self, realmId:str, clientId:str):
        for client in await self.get(f'/admin/realms/{realmId}/clients'):
            if client['clientId'] == clientId:
                if 'secret' in client: return client['secret']
                else: return None
        return None

    # Role #####################################################################
    async def readRole(self, realmId:str, roleId:str):
        return await self.get(f'/admin/realms/{realmId}/roles-by-id/{roleId}')

    async def searchRoles(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/roles?search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/roles')

    async def searchGroupsInRole(self, realmId:str, roleId:str):
        roleName = (await self.readRole(realmId, roleId))['name']
        return await self.get(f'/admin/realms/{realmId}/roles/{roleName}/groups')

    async def searchUsersInRole(self, realmId:str, roleId:str):
        roleName = (await self.readRole(realmId, roleId))['name']
        return await self.get(f'/admin/realms/{realmId}/roles/{roleName}/users')

    async def createRole(self, realmId:str, name:str, description:str='', attributes:dict | None=None):
        await self.post(f'/admin/realms/{realmId}/roles', {
            'name': name,
            'description': description,
            'attributes': attributes if attributes else {}
        })
        return await self.get(f'/admin/realms/{realmId}/roles/{name}')

    async def updateRole(self, realmId:str, role:dict):
        roleId = role['id']
        await self.put(f'/admin/realms/{realmId}/roles-by-id/{roleId}', role)
        return await self.readRole(realmId, roleId)

    async def deleteRole(self, realmId:str, roleId:str):
        await self.delete(f'/admin/realms/{realmId}/roles-by-id/{roleId}')
        return True

    # Group ####################################################################
    async def readGroup(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}')

    async def searchGroups(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/groups?search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/groups')

    async def searchUsersInGroup(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}/members')

    async def createGroup(self, realmId:str, name:str, attributes:dict | None=None):
        await self.post(f'/admin/realms/{realmId}/groups', {
            'name': name,
            'attributes': attributes if attributes else {}
        })
        groups = await self.searchGroups(realmId, search=name)
        for group in groups:
            if name == group['name']: return group
        raise EpException(500, 'Could not find group created')

    async def updateGroup(self, realmId:str, group:dict):
        groupId = group['id']
        await self.put(f'/admin/realms/{realmId}/groups/{groupId}', group)
        return await self.readGroup(realmId, groupId)

    async def insertGroupRole(self, realmId:str, groupId:str, roleIds:list[str]):
        roles = []
        for role in await self.searchRoles(realmId):
            if role['id'] in roleIds: roles.append(role)
        await self.post(f'/admin/realms/{realmId}/groups/{groupId}/role-mappings/realm', roles)
        return await self.readGroup(realmId, groupId)

    async def deleteGroupRole(self, realmId:str, groupId:str, roleIds:list[str]):
        roles = []
        for role in await self.searchRoles(realmId):
            if role['id'] in roleIds: roles.append(role)
        await self.delete(f'/admin/realms/{realmId}/groups/{groupId}/role-mappings/realm', roles)
        return await self.readGroup(realmId, groupId)

    async def deleteGroup(self, realmId:str, groupId:str):
        await self.delete(f'/admin/realms/{realmId}/groups/{groupId}')
        return True

    # User #####################################################################
    async def readUser(self, realmId:str, userId:str):
        return await self.get(f'/admin/realms/{realmId}/users/{userId}')

    async def searchUsers(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/users?search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/users')

    async def createUser(self, realmId:str, username:str, email:str, firstName:str, lastName:str):
        await self.post(f'/admin/realms/{realmId}/users', {
            'username': username,
            'email': email,
            'firstName': firstName,
            'lastName': lastName
        })
        for user in await self.searchUsers(realmId, search=username):
            if username == user['username']:
                userId = user['id']
                roles = await self.get(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm')
                await self.delete(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm', roles)
                return user
        raise EpException(500, 'Could not find user created')

    async def updateUser(self, realmId:str, user:dict):
        userId = user['id']
        await self.put(f'/admin/realms/{realmId}/users/{userId}', user)
        return await self.readUser(realmId, userId)

    async def updateUserEnabled(self, realmId:str, userId:str, enabled:bool):
        await self.put(f'/admin/realms/{realmId}/users/{userId}', {'enabled': enabled})
        return True

    async def updateUserPassword(self, realmId:str, userId:str, password:str, temporary:bool=True):
        await self.put(f'/admin/realms/{realmId}/users/{userId}/reset-password', {
            'temporary': temporary,
            'type': 'password',
            'value': password
        })
        return True

    async def insertUserRoles(self, realmId:str, userId:str, roleIds:list[str]):
        roles = []
        for role in await self.searchRoles(realmId):
            if role['id'] in roleIds: roles.append(role)
        await self.post(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm', roles)
        return await self.readUser(realmId, userId)

    async def deleteUserRoles(self, realmId:str, userId:str, roleIds:list[str]):
        roles = []
        for role in await self.searchRoles(realmId):
            if role['id'] in roleIds: roles.append(role)
        await self.delete(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm', roles)
        return await self.readUser(realmId, userId)

    async def registerUserToGroup(self, realmId:str, userId:str, groupId:str):
        await self.put(f'/admin/realms/{realmId}/users/{userId}/groups/{groupId}', {})
        return await self.readUser(realmId, userId)

    async def unregisterUserFromGroup(self, realmId:str, userId:str, groupId:str):
        await self.delete(f'/admin/realms/{realmId}/users/{userId}/groups/{groupId}')
        return await self.readUser(realmId, userId)

    async def deleteUser(self, realmId:str, userId:str):
        await self.delete(f'/admin/realms/{realmId}/users/{userId}')
        return True

    #===========================================================================
    # Account Interface
    #===========================================================================
    async def getUserInfo(self, realm:str, token:str):
        async with AsyncRest(self._kcBaseUrl) as rest:
            return await rest.get(f'/realms/{realm}/protocol/openid-connect/userinfo', headers={'Authorization': f'Bearer {token}'})
