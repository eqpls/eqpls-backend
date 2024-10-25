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
from common import EpException, AsyncRest, DriverBase, SECONDS


#===============================================================================
# Implement
#===============================================================================
class KeyCloak(DriverBase):

    def __init__(self, control):
        DriverBase.__init__(self, control)
        kcConf = self.control.config['keycloak']
        self.kcDefaultAcl = {}
        self.kcEndpointUrl = f'https://{self.control.endpoint}'
        self.kcHostname = kcConf['hostname']
        self.kcHostport = int(kcConf['hostport'])
        self.kcBaseUrl = f'http://{self.kcHostname}:{self.kcHostport}/auth'
        self.kcTheme = kcConf['theme'] if 'theme' in kcConf and kcConf['theme'] else None
        self.kcSessionIdleTimeout = int(kcConf['session_idle_timeout'])
        self.kcSessionMaxLifespan = int(kcConf['session_max_lifespan'])
        self.kcTokenLifespan = int(kcConf['token_lifespan'])
        self.kcHeaders = None
        self.kcAccessToken = None
        self.kcRefreshToken = None

    async def initialize(self, *args, **kargs):
        if 'defaultAcl' in kargs:
            for sref, crud in kargs['defaultAcl'].items(): self.kcDefaultAcl[sref] = [crud]
        await self.connect()
        try: await self.readRealm(self.control.tenant)
        except EpException as e:
            if e.status_code != 404: raise e
            for client in await self.get('/admin/realms/master/clients'):
                if client['clientId'] == 'admin-cli':
                    client['attributes']['access.token.lifespan'] = SECONDS.YEAR
                    client['attributes']['client.session.max.lifespan'] = SECONDS.YEAR
                    client['attributes']['client.session.idle.timeout'] = SECONDS.YEAR
                    await self.put(f'/admin/realms/master/clients/{client["id"]}', client)
                    await self.connect()
                    break
            else: raise EpException(500, 'Internal Server Error')
            await self.connect()
            await self.createRealm(self.control.tenant, self.control.title)
        except Exception as e: raise e

    async def connect(self, *args, **kargs):
        if self.kcRefreshToken:
            try: tokens = await self.loginByRefreshToken('master', 'admin-cli', self.kcRefreshToken)
            except:
                await self.disconnect()
                return await self.connect()
        else: tokens = await self.login('master', 'admin-cli', self.control.systemAccessKey, self.control.systemSecretKey)
        self.kcAccessToken = tokens['access_token']
        self.kcRefreshToken = tokens['refresh_token']
        self.kcHeaders = {
            'Authorization': f'Bearer {self.kcAccessToken}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        return self

    async def disconnect(self):
        try: await self.logout('master', 'admin-cli', self.kcRefreshToken)
        except: pass
        self.kcRefreshToken = None
        self.kcAccessToken = None

    #===========================================================================
    # Basic Rest Methods
    #===========================================================================
    async def get(self, url):
        async with AsyncRest(self.kcBaseUrl) as s:
            try: return await s.get(url, headers=self.kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).get(url)
                else: raise e

    async def post(self, url, payload):
        async with AsyncRest(self.kcBaseUrl) as s:
            try: return await s.post(url, json=payload, headers=self.kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).post(url, payload)
                else: raise e

    async def put(self, url, payload):
        async with AsyncRest(self.kcBaseUrl) as s:
            try: return await s.put(url, json=payload, headers=self.kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).put(url, payload)
                else: raise e

    async def patch(self, url, payload):
        async with AsyncRest(self.kcBaseUrl) as s:
            try: return await s.patch(url, json=payload, headers=self.kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).patch(url, payload)
                else: raise e

    async def delete(self, url, payload=None):
        async with AsyncRest(self.kcBaseUrl) as s:
            try: return await s.delete(url, json=payload, headers=self.kcHeaders)
            except EpException as e:
                if e.status_code == 401: return await (await self.connect()).delete(url)
                else: raise e

    #===========================================================================
    # OpenId Connect
    #===========================================================================
    async def login(self, realmId:str, clientId:str, username:str, password:str):
        async with AsyncRest(self.kcBaseUrl) as rest:
            return await rest.post(f'/realms/{realmId}/protocol/openid-connect/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'grant_type=password&client_id={clientId}&username={username}&password={password}'
            )

    async def loginByRefreshToken(self, realmId:str, clientId:str, refreshToken):
        async with AsyncRest(self.kcBaseUrl) as rest:
            return await rest.post(f'/realms/{realmId}/protocol/openid-connect/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'grant_type=refresh_token&client_id={clientId}&refresh_token={refreshToken}'
            )

    async def logout(self, realmId:str, clidentId:str, refreshToken:str):
        async with AsyncRest(self.kcBaseUrl) as rest:
            await rest.post(f'/realms/{realmId}/protocol/openid-connect/logout',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'client_id={clidentId}&refresh_token={refreshToken}'
            )

    async def getUserInfo(self, realmId:str, token:str):
        async with AsyncRest(self.kcBaseUrl) as rest:
            return await rest.get(f'/realms/{realmId}/protocol/openid-connect/userinfo', headers={'Authorization': f'Bearer {token}'})

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
        if realmId == 'master': raise EpException(400, 'Bad Request')

        # create realm
        await self.post(f'/admin/realms', {
            'realm': realmId,
            'displayName': displayName,
            'enabled': True
        })
        realm = await self.get(f'/admin/realms/{realmId}')
        realm['resetPasswordAllowed'] = True
        await self.put(f'/admin/realms/{realmId}', realm)
        if self.kcTheme:
            realm = await self.get(f'/admin/realms/{realmId}')
            realm['loginTheme'] = self.kcTheme
            await self.put(f'/admin/realms/{realmId}/ui-ext', realm)

        # create default admin role
        await self.createRole(realmId, self.control.adminRoleName, 'default admin role')
        adminRole = await self.readRoleByName(realmId, self.control.adminRoleName)

        # create default user role
        await self.createRole(realmId, self.control.userRoleName, 'default user role')
        userRole = await self.readRoleByName(realmId, self.control.userRoleName)

        # create default admin group
        await self.createGroup(realmId, self.control.adminGroupName)
        adminGroupId = (await self.readGroupByName(realmId, self.control.adminGroupName))['id']
        await self.setGroupRoles(realmId, adminGroupId, [adminRole])

        # create default user group
        await self.createGroup(realmId, self.control.userGroupName)
        userGroupId = (await self.readGroupByName(realmId, self.control.userGroupName))['id']
        await self.setGroupRoles(realmId, userGroupId, [userRole])

        # create system user
        await self.createUser(
            realmId,
            self.control.systemAccessKey,
            f'{self.control.systemAccessKey}@{self.control.domain}',
            self.control.systemAccessKey,
            self.control.systemAccessKey
        )
        systemUser = await self.readUserByUsername(realmId, self.control.systemAccessKey)
        systemUserId = systemUser['id']
        await self.unsetUserRoles(realmId, systemUserId, await self.getUserRoles(realmId, systemUserId))
        await self.setUserToGroup(realmId, systemUserId, adminGroupId)
        await self.setUserEnabled(realmId, systemUserId, True)
        await self.setUserPassword(realmId, systemUserId, self.control.systemSecretKey, False)

        # create admin user
        await self.createUser(
            realmId,
            self.control.adminUsername,
            f'{self.control.adminUsername}@{self.control.domain}',
            self.control.adminUsername,
            self.control.adminUsername
        )
        adminUser = await self.readUserByUsername(realmId, self.control.adminUsername)
        adminUserId = adminUser['id']
        await self.unsetUserRoles(realmId, adminUserId, await self.getUserRoles(realmId, adminUserId))
        await self.setUserToGroup(realmId, adminUserId, adminGroupId)
        await self.setUserToGroup(realmId, adminUserId, userGroupId)
        await self.setUserEnabled(realmId, adminUserId, True)
        await self.setUserPassword(realmId, adminUserId, self.control.adminPassword, False)

        # delete default realm roles
        for role in await self.searchRoles(realmId):
            if 'default-roles-' in role['name']:
                comps = await self.get(f'/admin/realms/{realmId}/roles-by-id/{role["id"]}/composites')
                await self.delete(f'/admin/realms/{realmId}/roles-by-id/{role["id"]}/composites', comps)
                await self.post(f'/admin/realms/{realmId}/roles-by-id/{role["id"]}/composites', [userRole])

        # create openid client scope
        await self.post(f'/admin/realms/{realmId}/client-scopes', {
            'name': 'openid',
            'description': 'openid',
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
            if scope['name'] == 'openid': scopeId = scope['id']; break
        else: raise EpException(404, 'Not Found')

        # add group mapper
        await self.post(f'/admin/realms/{realmId}/client-scopes/{scopeId}/protocol-mappers/add-models', [{
            'name': 'groups',
            'protocol': 'openid-connect',
            'protocolMapper': 'oidc-usermodel-realm-role-mapper',
            'config': {
                'claim.name': 'groups',
                'user.attribute': 'groups',
                'jsonType.label': 'String',
                'multivalued': True,
                'id.token.claim': True,
                'access.token.claim': True,
                'lightweight.claim': False,
                'userinfo.token.claim': True,
                'introspection.token.claim': True
            }
        }])

        # register default client scope
        await self.delete(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}')
        await self.put(f'/admin/realms/{realmId}/default-default-client-scopes/{scopeId}', {})

        # add openid client
        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': realmId,
            'name': realmId,
            'description': realmId,
            'protocol': 'openid-connect',
            'publicClient': True,
            'rootUrl': self.kcEndpointUrl,
            'baseUrl': self.kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self.control.origins if self.control.origins else [self.kcEndpointUrl],
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
        else: raise EpException(404, 'Not Found')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        # add guacamole client
        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': 'guacamole',
            'name': 'guacamole',
            'description': 'guacamole',
            'protocol': 'openid-connect',
            'publicClient': True,
            'rootUrl': self.kcEndpointUrl,
            'baseUrl': self.kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self.control.origins if self.control.origins else [self.kcEndpointUrl],
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
        else: raise EpException(404, 'Not Found')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        # add minio client
        await self.post(f'/admin/realms/{realmId}/clients', {
            'clientId': 'minio',
            'name': 'minio',
            'description': 'minio',
            'protocol': 'openid-connect',
            'publicClient': False,
            'rootUrl': self.kcEndpointUrl,
            'baseUrl': self.kcEndpointUrl,
            'redirectUris': ['*'],
            'webOrigins': self.control.origins if self.control.origins else [self.kcEndpointUrl],
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
            if client['clientId'] == 'minio': clientId = client['id']; break
        else: raise EpException(404, 'Not Found')
        await self.put(f'/admin/realms/{realmId}/clients/{clientId}/default-client-scopes/{scopeId}', {})

        await self.put(f'/admin/realms/{realmId}', {
            'ssoSessionIdleTimeout': self.kcSessionIdleTimeout,
            'ssoSessionMaxLifespan': self.kcSessionMaxLifespan,
            'accessTokenLifespan': self.kcTokenLifespan,
            'accessTokenLifespanForImplicitFlow': self.kcTokenLifespan,
            'revokeRefreshToken': True
        })

    async def updateRealm(self, realm:dict):
        realmId = realm['realm']
        if realmId == 'master': raise EpException(400, 'Bad Request')
        await self.put(f'/admin/realms/{realmId}', realm)

    async def deleteRealm(self, realmId:str):
        if realmId == 'master': raise EpException(400, 'Bad Request')
        await self.delete(f'/admin/realms/{realmId}')

    async def getClientSecret(self, realmId:str, clientId:str):
        for client in await self.get(f'/admin/realms/{realmId}/clients'):
            if client['clientId'] == clientId:
                if 'secret' in client: return client['secret']
                else: return None
        return None

    # Group ####################################################################
    async def readGroup(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}')

    async def readGroupByName(self, realmId:str, groupName:str):
        for group in await self.searchGroups(realmId, groupName):
            if group['name'] == groupName: return group
        else: raise EpException(404, 'Not Found')

    async def searchGroups(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/groups?briefRepresentation&search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/groups?briefRepresentation')

    async def searchGroupsByRoleId(self, realmId:str, roleId:str):
        roleName = (await self.readRole(realmId, roleId))['name']
        return await self.get(f'/admin/realms/{realmId}/roles/{roleName}/groups')

    async def createGroup(self, realmId:str, name:str, attributes:dict | None=None):
        await self.post(f'/admin/realms/{realmId}/groups', {
            'name': name,
            'attributes': attributes if attributes else {}
        })

    async def updateGroup(self, realmId:str, group:dict):
        await self.put(f'/admin/realms/{realmId}/groups/{group["id"]}', {'name': group['name']})

    async def getGroupRoles(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}/role-mappings/realm')

    async def setGroupRoles(self, realmId:str, groupId:str, roles:list):
        await self.post(f'/admin/realms/{realmId}/groups/{groupId}/role-mappings/realm', roles)

    async def deleteGroup(self, realmId:str, groupId:str):
        await self.delete(f'/admin/realms/{realmId}/groups/{groupId}')

    # Role #####################################################################
    async def readRole(self, realmId:str, roleId:str):
        return await self.get(f'/admin/realms/{realmId}/roles-by-id/{roleId}')

    async def readRoleByName(self, realmId:str, roleName:str):
        return await self.get(f'/admin/realms/{realmId}/roles/{roleName}')

    async def searchRoles(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/roles?search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/roles')

    async def createRole(self, realmId:str, name:str, description:str='', attributes:dict | None=None):
        await self.post(f'/admin/realms/{realmId}/roles', {
            'name': name,
            'description': description,
            'attributes': attributes if attributes else self.kcDefaultAcl
        })

    async def updateRole(self, realmId:str, role:dict):
        await self.put(f'/admin/realms/{realmId}/roles-by-id/{role["id"]}', role)

    async def deleteRole(self, realmId:str, roleId:str):
        await self.delete(f'/admin/realms/{realmId}/roles-by-id/{roleId}')

    async def deleteRoleByName(self, realmId:str, roleName:str):
        await self.delete(f'/admin/realms/{realmId}/roles/{roleName}')

    # User #####################################################################
    async def readUser(self, realmId:str, userId:str):
        return await self.get(f'/admin/realms/{realmId}/users/{userId}')

    async def readUserByUsername(self, realmId:str, username:str):
        for user in await self.searchUsers(realmId, search=username):
            if username == user['username']: return user
        raise EpException(404, 'Not Found')

    async def searchUsers(self, realmId:str, search:str | None=None):
        if search: return await self.get(f'/admin/realms/{realmId}/users?search={search}')
        else: return await self.get(f'/admin/realms/{realmId}/users')

    async def searchUsersByGroupId(self, realmId:str, groupId:str):
        return await self.get(f'/admin/realms/{realmId}/groups/{groupId}/members')

    async def searchUsersByRoleId(self, realmId:str, roleId:str):
        return await self.searchUsersInRoleName(realmId, (await self.readRole(realmId, roleId))['name'])

    async def searchUsersByRoleName(self, realmId:str, roleName:str):
        return await self.get(f'/admin/realms/{realmId}/roles/{roleName}/users')

    async def createUser(self, realmId:str, username:str, email:str, firstName:str, lastName:str):
        await self.post(f'/admin/realms/{realmId}/users', {
            'username': username,
            'email': email,
            'firstName': firstName,
            'lastName': lastName
        })

    async def updateUser(self, realmId:str, user:dict):
        await self.put(f'/admin/realms/{realmId}/users/{user["id"]}', user)

    async def setUserEnabled(self, realmId:str, userId:str, enabled:bool):
        await self.put(f'/admin/realms/{realmId}/users/{userId}', {'enabled': enabled})

    async def setUserPassword(self, realmId:str, userId:str, password:str, temporary:bool=True):
        await self.put(f'/admin/realms/{realmId}/users/{userId}/reset-password', {
            'temporary': temporary,
            'type': 'password',
            'value': password
        })

    async def getUserRoles(self, realmId:str, userId:str):
        return await self.get(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm')

    async def setUserRoles(self, realmId:str, userId:str, roles:list):
        await self.post(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm', roles)

    async def unsetUserRoles(self, realmId:str, userId:str, roles:list):
        await self.delete(f'/admin/realms/{realmId}/users/{userId}/role-mappings/realm', roles)

    async def setUserToGroup(self, realmId:str, userId:str, groupId:str):
        await self.put(f'/admin/realms/{realmId}/users/{userId}/groups/{groupId}', {})

    async def unsetUserFromGroup(self, realmId:str, userId:str, groupId:str):
        await self.delete(f'/admin/realms/{realmId}/users/{userId}/groups/{groupId}')

    async def deleteUser(self, realmId:str, userId:str):
        await self.delete(f'/admin/realms/{realmId}/users/{userId}')
