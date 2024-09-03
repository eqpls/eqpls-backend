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
# Implement
#===============================================================================
class KeyCloak(DriverBase):

    def __init__(self, config):
        DriverBase.__init__(self, config)

        self._kcEndpoint = config['default']['endpoint']
        self._kcUsername = config['default']['system_access_key']
        self._kcPassword = config['default']['system_secret_key']

        self._kcHostname = config['keycloak']['hostname']
        self._kcHostport = int(config['keycloak']['hostport'])

        self._kcFrontend = f'https://{self._kcEndpoint}'
        self._kcBaseUrl = f'http://{self._kcHostname}:{self._kcHostport}'

        self._kcAccessToken = None
        self._kcRefreshToken = None
        self._kcHeaders = None

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

    async def delete(self, url):
        async with AsyncRest(self._kcBaseUrl) as s:
            try: return await s.delete(url, headers=self._kcHeaders)
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
            'name': 'roles',
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-attribute-mapper',
            'config': {
                'claim.name': 'roles',
                'user.attribute': 'roles',
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
        await self.delete(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}')
        await self.put(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': realmId,
            'name': realmId,
            'description': realmId,
            'protocol': 'openid-connect',
            'publicClient': True,
            'rootUrl': self._kcFrontend,
            'baseUrl': self._kcFrontend,
            'redirectUris': ['*'],
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
            'rootUrl': self._kcFrontend,
            'baseUrl': self._kcFrontend,
            'redirectUris': ['*'],
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
            'rootUrl': self._kcFrontend,
            'baseUrl': self._kcFrontend,
            'redirectUris': ['*'],
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
            'accessTokenLifespan': 1800,
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

    async def searchRoles(self, realmId:str, filter:str | None=None):
        if filter: return await self.get(f'/admin/realms/{realmId}/roles?q=${filter}')
        else: return await self.get(f'/admin/realms/{realmId}/roles')

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
        return await self.get(f'/admin/realms/{realmId}/roles-by-id/{roleId}')

    async def deleteRole(self, realmId:str, roleId:str):
        await self.delete(f'/admin/realms/{realmId}/roles-by-id/{roleId}')
        return True

    # Group ####################################################################
    async def readGroup(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}')

    async def searchGroups(self, realmId:str, filter:str | None=None):
        if filter: return await self.get(f'/admin/realms/{realmId}/groups?q=${filter}')
        else: return await self.get(f'/admin/realms/{realmId}/groups')

    async def createGroup(self, realmId:str, name:str, attributes:dict | None=None):
        await self.post(f'/admin/realms/{realm}/groups/{parentId}/children', {
            'name': name,
            'attributes': attributes if attributes else {}
        })
        groups = await self.searchGroups(realmId, filter=f'name:{name}')
        for group in groups:
            if name == group['name']: return group
        raise EpException(500, 'Could not delete realm with predefined name')

        # Edit Here
        payload = {'name': name}
        if attributes: payload['attributes'] = attributes
        if parentId: await self.post(f'/admin/realms/{realm}/groups/{parentId}/children', payload)
        else: await self.post(f'/admin/realms/{realm}/groups', payload)
        return await self.findGroup(realm, groupName, parentId)

    async def updateGroupName(self, realm:str, groupId:str, groupName:str):
        await self.put(f'/admin/realms/{realm}/groups/{groupId}', {'name': groupName})
        return True

    async def updateGroupAttributes(self, realm:str, groupId:str, attributes:dict):
        await self.put(f'/admin/realms/{realm}/groups/{groupId}', {'attributes': attributes})
        return True

    async def deleteGroup(self, realm:str, groupId:str):
        await self.delete(f'/admin/realms/{realm}/groups/{groupId}')
        return True

    # User #####################################################################
    async def readUser(self, realm:str, userId:str):
        return await self.get(f'/admin/realms/{realm}/users/{userId}')

    async def readUsersInGroup(self, realm:str, groupId:str):
        return await self.get(f'/admin/realms/{realm}/groups/{groupId}/members')

    async def searchUser(self, realm:str, filter:str | None=None):
        if filter: return await self.get(f'/admin/realms/{realm}/users?username={filter}')
        else: return await self.get(f'/admin/realms/{realm}/users')

    async def findUser(self, realm:str, username:str):
        for result in await self.searchUser(realm, username):
            if result['username'] == username: return result
        return None

    async def createUser(self, realm:str, username:str, email:str, firstName:str, lastName:str, password:str | None=None, enabled:bool=True):
        await self.post(f'/admin/realms/{realm}/users', {
            'username': username,
            'email': email,
            'firstName': firstName,
            'lastName': lastName
        })
        user = await self.findUser(realm, username)
        userId = user['id']
        await self.updateUserPassword(realm, userId, password if password else username, False if password else True)
        if enabled: await self.put(f'/admin/realms/{realm}/users/{userId}', {'enabled': True})
        return user

    async def updateUserPassword(self, realm:str, userId:str, password:str, temporary=True):
        await self.put(f'/admin/realms/{realm}/users/{userId}/reset-password', {
            'temporary': temporary,
            'type': 'password',
            'value': password
        })
        return True

    async def updateUserProperty(self, realm:str, userId:str, email:str | None=None, firstName:str | None=None, lastName:str | None=None):
        payload = {}
        if email: payload['email'] = email
        if firstName: payload['firstName'] = firstName
        if lastName: payload['lastName'] = lastName
        if payload: await self.put(f'/admin/realms/{realm}/users/{userId}', payload)
        return True

    async def registerUserToGroup(self, realm:str, userId:str, groupId:str):
        await self.put(f'/admin/realms/{realm}/users/{userId}/groups/{groupId}', {})
        return True

    async def unregisterUserFromGroup(self, realm:str, userId:str, groupId:str):
        await self.delete(f'/admin/realms/{realm}/users/{userId}/groups/{groupId}')
        return True

    async def deleteUser(self, realm:str, userId:str):
        await self.delete(f'/admin/realms/{realm}/users/{userId}')
        return True

    #===========================================================================
    # Account Interface
    #===========================================================================
    async def getUserInfo(self, realm:str, token:str):
        async with AsyncRest(self._kcBaseUrl) as rest:
            return await rest.get(f'/realms/{realm}/protocol/openid-connect/userinfo', headers={'Authorization': f'Bearer {token}'})
