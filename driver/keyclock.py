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
        self._kcHostport = int(config['keycloak']['port'])

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
    async def readRealm(self, realm:str):
        if realm != 'master': return await self.get(f'/admin/realms/{realm}')
        return None

    async def searchRealm(self, filter:str | None=None):
        results = []

        if filter:
            for realm in await self.get(f'/admin/realms'):
                if realm['realm'] != 'master':
                    if filter in realm['realm']: results.append(realm)
        else:
            for realm in await self.get(f'/admin/realms'):
                if realm['realm'] != 'master': results.append(realm)

        return results

    async def createRealm(self, realm:str, displayName:str):
        if realm == 'master': raise EpException(400, 'Could not create realm with predefined name')
        return await self.createRealmPrivileged(realm, displayName)

    async def createRealmPrivileged(self, realm:str, displayName:str):
        await self.post(f'/admin/realms', {
            'realm': realm,
            'displayName': displayName,
            'enabled': True
        })
        await self.post(f'/admin/realms/{realm}/client-scopes', {
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
        for scope in await self.get(f'/admin/realms/{realm}/client-scopes'):
            if scope['name'] == 'openid-client-scope': scopeId = scope['id']; break
        else: raise EpException(404, 'Could not find client scope')
        await self.post(f'/admin/realms/{realm}/client-scopes/{scopeId}/protocol-mappers/models', {
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
        await self.delete(f'/admin/realms/{realm}/default-default-client-scopes/{scopeId}')
        await self.put(f'/admin/realms/{realm}/default-default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realm}/clients', {
            'clientId': realm,
            'name': realm,
            'description': realm,
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
        for client in await self.get(f'/admin/realms/{realm}/clients'):
            if client['clientId'] == realm: clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realm}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realm}/clients', {
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
        for client in await self.get(f'/admin/realms/{realm}/clients'):
            if client['clientId'] == 'guacamole': clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realm}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.post(f'/admin/realms/{realm}/clients', {
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
        for client in await self.get(f'/admin/realms/{realm}/clients'):
            if client['clientId'] == 'minio':
                clientId = client['id']; break
        else: raise EpException(404, 'Could not find client')
        await self.put(f'/admin/realms/{realm}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.put(f'/admin/realms/{realm}', {
            'accessTokenLifespan': 1800,
            'revokeRefreshToken': True
        })
        return await self.readRealm(realm)

    async def updateRealmDisplayName(self, realm:str, displayName:str):
        await self.put(f'/admin/realms/{realm}', {'displayName': displayName})
        return True

    async def deleteRealm(self, realm:str):
        await self.delete(f'/admin/realms/{realm}')
        return True

    async def getClientSecret(self, realm:str, clientId:str):
        for client in await self.get(f'/admin/realms/{realm}/clients'):
            if client['clientId'] == clientId:
                if 'secret' in client: return client['secret']
                else: return None
        return None

    # Group ####################################################################
    async def readGroup(self, realm:str, groupId:str):
        return await self.get(f'/admin/realms/{realm}/groups/{groupId}')

    async def searchGroup(self, realm:str, parentId:str | None=None, filter:str | None=None):
        if parentId: groups = await self.get(f'/admin/realms/{realm}/groups/{parentId}/children')
        else: groups = await self.get(f'/admin/realms/{realm}/groups')
        if filter:
            result = []
            for group in groups:
                if filter in group['name']: result.append(group)
            return result
        else: groups

    async def findGroup(self, realm:str, groupName:str, parentId:str | None=None):
        for group in await self.searchGroup(realm, parentId, groupName):
            if group['name'] == groupName: return group
        return None

    async def createGroup(self, realm:str, groupName:str, parentId:str | None=None, attributes:dict | None=None):
        payload = {'name': groupName}
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
