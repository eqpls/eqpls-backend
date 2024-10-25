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
from common import EpException, AUTH_HEADER, ModelStatus, getNewsAndDelsArray
from common import LoginRequest, UserInfo, AuthInfo, User, Group, AccessControl
from .controls import Control

#===============================================================================
# SingleTone
#===============================================================================
ctrl = Control(__file__)
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.post(f'{ctrl.uriver}/login', tags=['AAA'])
async def log_in(loginReq:LoginRequest) -> dict:
    return await ctrl.login(loginReq.username, loginReq.password)


@api.get(f'{ctrl.uriver}/logout', tags=['AAA'])
async def log_out(refreshToken:str) -> dict:
    await ctrl.logout(refreshToken)
    return {'result': 'ok'}


@api.get(f'{ctrl.uriver}/userinfo', tags=['AAA'])
async def get_user_info(token: AUTH_HEADER) -> UserInfo:
    return await ctrl.getUserInfo(token)


@api.get(f'{ctrl.uriver}/authinfo', tags=['AAA'])
async def get_auth_info(token: AUTH_HEADER) -> AuthInfo:
    return await ctrl.getAuthInfo(token)


@api.get(f'{ctrl.uriver}/client/{{clientId}}/secret', tags=['AAA'])
async def get_client_secret(token: AUTH_HEADER, clientId:str) -> dict:
    (await ctrl.getAuthInfo(token)).checkAdmin()
    secret = await ctrl.keycloak.getClientSecret(ctrl.tenant, clientId)
    if secret: return {'clientSecret': secret}
    raise EpException(404, 'Not Found')


@api.get(f'{ctrl.uriver}/users/{{userId}}', tags=['User'])
async def read_user(token: AUTH_HEADER, userId:str) -> User:
    (await ctrl.getAuthInfo(token)).checkRead('User')
    user = await ctrl.keycloak.readUser(ctrl.tenant, userId)
    user['sref'] = 'User'
    user['uref'] = f'{ctrl.uriver}/users/{user["id"]}'
    return user


@api.get(f'{ctrl.uriver}/username/{{username}}', tags=['User'])
async def read_user_by_username(token: AUTH_HEADER, username:str) -> User:
    (await ctrl.getAuthInfo(token)).checkRead('User')
    user = await ctrl.keycloak.readUserByUsername(ctrl.tenant, username)
    user['sref'] = 'User'
    user['uref'] = f'{ctrl.uriver}/users/{user["id"]}'
    return user


@api.get(f'{ctrl.uriver}/users', tags=['User'])
async def search_user_list(token:AUTH_HEADER, search:str | None=None) -> list[User]:
    (await ctrl.getAuthInfo(token)).checkRead('User')
    result = []
    for user in await ctrl.keycloak.searchUsers(ctrl.tenant, search):
        user['sref'] = 'User'
        user['uref'] = f'{ctrl.uriver}/users/{user["id"]}'
        result.append(user)
    return result


@api.post(f'{ctrl.uriver}/users', tags=['User'])
async def create_user(token: AUTH_HEADER, user:User) -> User:
    (await ctrl.getAuthInfo(token)).checkCreate('User')
    username = user.username
    await ctrl.keycloak.createUser(ctrl.tenant, username, user.email, user.firstName, user.lastName)
    user = await ctrl.keycloak.readUserByUsername(ctrl.tenant, username)
    userId = user['id']
    await ctrl.keycloak.unsetUserRoles(ctrl.tenant, userId, await ctrl.keycloak.getUserRoles(ctrl.tenant, userId))
    await ctrl.keycloak.setUserEnabled(ctrl.tenant, userId, True)
    await ctrl.keycloak.setUserPassword(ctrl.tenant, userId, username)
    await ctrl.keycloak.setUserToGroup(ctrl.tenant, userId, ctrl.userGroupId)
    user['sref'] = 'User'
    user['uref'] = f'{ctrl.uriver}/users/{userId}'
    return user


@api.put(f'{ctrl.uriver}/users/{{userId}}', tags=['User'])
async def update_user(token: AUTH_HEADER, userId:str, _user:User) -> User:
    (await ctrl.getAuthInfo(token)).checkUpdate('User')
    user = await ctrl.keycloak.readUser(ctrl.tenant, userId)
    user['email'] = _user.email
    user['firstName'] = _user.firstName
    user['lastName'] = _user.lastName
    await ctrl.keycloak.updateUser(ctrl.tenant, user)
    user['sref'] = 'User'
    user['uref'] = f'{ctrl.uriver}/users/{userId}'
    return user


@api.delete(f'{ctrl.uriver}/users/{{userId}}', tags=['User'])
async def delete_user(token: AUTH_HEADER, userId:str) -> ModelStatus:
    (await ctrl.getAuthInfo(token)).checkDelete('User')
    await ctrl.keycloak.deleteUser(ctrl.tenant, userId)
    return {
        'id': userId,
        'sref': 'User',
        'uref': f'{ctrl.uriver}/users/{userId}',
        'status': 'deleted'
    }


@api.get(f'{ctrl.uriver}/groups/{{groupId}}', tags=['Group'])
async def read_group(token: AUTH_HEADER, groupId:str) -> Group:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    return {
        'id': groupId,
        'parentId': group['parentId'] if 'parentId' in group else '',
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'code': group['realmRoles'][0] if group['realmRoles'] else '',
        'name': group['name'],
        'path': group['path'],
        'subGroupCount': group['subGroupCount']
    }


@api.get(f'{ctrl.uriver}/groupname/{{groupName}}', tags=['Group'])
async def read_group_by_name(token: AUTH_HEADER, groupName:str) -> Group:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    group = await ctrl.keycloak.readGroupByName(ctrl.tenant, groupName)
    groupId = group['id']
    return {
        'id': groupId,
        'parentId': group['parentId'] if 'parentId' in group else '',
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'code': group['realmRoles'][0] if group['realmRoles'] else '',
        'name': group['name'],
        'path': group['path'],
        'subGroupCount': group['subGroupCount']
    }


@api.get(f'{ctrl.uriver}/groupcode/{{groupCode}}', tags=['Group'])
async def read_group_by_code(token: AUTH_HEADER, groupCode:str) -> Group:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    role = await ctrl.keycloak.readRoleByName(ctrl.tenant, groupCode)
    group = await ctrl.keycloak.searchGroupsByRoleId(ctrl.tenant, role['id'])
    if group:
        try: group = await ctrl.keycloak.readGroup(ctrl.tenant, group[0]['id'])
        except: raise EpException(404, 'Not Found')
    else: raise EpException(404, 'Not Found')
    groupId = group['id']
    return {
        'id': groupId,
        'parentId': group['parentId'] if 'parentId' in group else '',
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'code': group['realmRoles'][0] if group['realmRoles'] else '',
        'name': group['name'],
        'path': group['path'],
        'subGroupCount': group['subGroupCount']
    }


@api.get(f'{ctrl.uriver}/groups/{{groupId}}/acl', tags=['Group'])
async def read_group_acl(token: AUTH_HEADER, groupId:str) -> list[AccessControl]:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    code = group['realmRoles'][0] if group['realmRoles'] else ''
    if not code: raise Exception(501, 'Not Implemented')
    role = await ctrl.keycloak.readRoleByName(ctrl.tenant, code)
    return [{
        'sref': sref,
        'crud': crud[0]
    } for sref, crud in role['attributes'].items()]


@api.get(f'{ctrl.uriver}/groups/{{groupId}}/users', tags=['Group'])
async def read_group_users(token: AUTH_HEADER, groupId:str) -> list[User]:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    result = []
    for user in await ctrl.keycloak.searchUsersByGroupId(ctrl.tenant, groupId):
        user['sref'] = 'User'
        user['uref'] = f'{ctrl.uriver}/users/{user["id"]}'
        result.append(user)
    return result


@api.get(f'{ctrl.uriver}/groups/{{groupCode}}/users', tags=['Group'])
async def read_group_users_by_code(token: AUTH_HEADER, groupCode:str) -> list[User]:
    (await ctrl.getAuthInfo(token)).checkRead('User')
    result = []
    for user in await ctrl.keycloak.searchUsersByRoleName(ctrl.tenant, groupCode):
        user['sref'] = 'User'
        user['uref'] = f'{ctrl.uriver}/users/{user["id"]}'
        result.append(user)
    return result


@api.get(f'{ctrl.uriver}/groups', tags=['Group'])
async def search_group_list(token:AUTH_HEADER, search:str | None=None) -> list[Group]:
    (await ctrl.getAuthInfo(token)).checkRead('Group')
    result = []
    groups = await ctrl.keycloak.searchGroups(ctrl.tenant, search)
    for group in groups:
        groupId = group['id']
        result.append({
            'id': groupId,
            'parentId': group['parentId'] if 'parentId' in group else '',
            'sref': 'Group',
            'uref': f'{ctrl.uriver}/groups/{groupId}',
            'code': group['realmRoles'][0] if group['realmRoles'] else '',
            'name': group['name'],
            'path': group['path'],
            'subGroupCount': group['subGroupCount']
        })
    return result


@api.post(f'{ctrl.uriver}/groups', tags=['Group'])
async def create_group(token: AUTH_HEADER, group:Group) -> Group:
    (await ctrl.getAuthInfo(token)).checkCreate('Group')
    if group.code in ctrl.accountRestrictGroupCodes: raise EpException(409, 'Conflict')
    groupName = group.name
    try: await ctrl.keycloak.readGroupByName(ctrl.tenant, groupName)
    except: pass
    else: raise EpException(409, 'Conflict')
    try: await ctrl.keycloak.readRoleByName(ctrl.tenant, group.code)
    except: pass
    else: raise EpException(409, 'Conflict')
    await ctrl.minio.createPolicy(group.code, f'g.{group.code}.*/*')
    await ctrl.keycloak.createRole(ctrl.tenant, group.code, groupName)
    role = await ctrl.keycloak.readRoleByName(ctrl.tenant, group.code)
    await ctrl.keycloak.createGroup(ctrl.tenant, groupName)
    group = await ctrl.keycloak.readGroupByName(ctrl.tenant, groupName)
    await ctrl.keycloak.setGroupRoles(ctrl.tenant, group['id'], [role])
    group = await ctrl.keycloak.readGroupByName(ctrl.tenant, groupName)
    groupId = group['id']
    return {
        'id': groupId,
        'parentId': group['parentId'] if 'parentId' in group else '',
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'code': group['realmRoles'][0] if group['realmRoles'] else '',
        'name': group['name'],
        'path': group['path'],
        'subGroupCount': group['subGroupCount']
    }


@api.put(f'{ctrl.uriver}/groups/{{groupId}}', tags=['Group'])
async def update_group(token: AUTH_HEADER, groupId:str, _group:Group) -> Group:
    (await ctrl.getAuthInfo(token)).checkUpdate('Group')
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    group['name'] = _group.name
    await ctrl.keycloak.updateGroup(ctrl.tenant, group)
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    return {
        'id': groupId,
        'parentId': group['parentId'] if 'parentId' in group else '',
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'code': group['realmRoles'][0] if group['realmRoles'] else '',
        'name': group['name'],
        'path': group['path'],
        'subGroupCount': group['subGroupCount']
    }


@api.put(f'{ctrl.uriver}/groups/{{groupId}}/acl', tags=['Group'])
async def update_group_acl(token: AUTH_HEADER, groupId:str, accessControlList:list[AccessControl]) -> list[AccessControl]:
    (await ctrl.getAuthInfo(token)).checkUpdate('Group')
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    code = group['realmRoles'][0] if group['realmRoles'] else ''
    if not code: raise Exception(501, 'Not Implemented')
    attributes = {}
    for accessControl in accessControlList: attributes[accessControl.sref] = [accessControl.crud]
    role = await ctrl.keycloak.readRoleByName(ctrl.tenant, code)
    role['attributes'] = attributes
    await ctrl.keycloak.updateRole(ctrl.tenant, role)
    return accessControlList


@api.put(f'{ctrl.uriver}/groups/{{groupId}}/users', tags=['Group'])
async def update_group_users(token: AUTH_HEADER, groupId:str, users:list[User]) -> list[User]:
    (await ctrl.getAuthInfo(token)).checkUpdate('Group')
    news, dels = getNewsAndDelsArray(
        [user.id for user in users],
        [user['id'] for user in await ctrl.keycloak.searchUsersByGroupId(ctrl.tenant, groupId)]
    )
    isError = False
    for userId in news:
        try: await ctrl.keycloak.setUserToGroup(ctrl.tenant, userId, groupId)
        except: isError = True
    for userId in dels:
        try: await ctrl.keycloak.unsetUserFromGroup(ctrl.tenant, userId, groupId)
        except: isError = True
    if isError: raise EpException(409, 'Conflict')
    return users


@api.delete(f'{ctrl.uriver}/groups/{{groupId}}', tags=['Group'])
async def delete_group(token: AUTH_HEADER, groupId:str) -> ModelStatus:
    (await ctrl.getAuthInfo(token)).checkDelete('Group')
    group = await ctrl.keycloak.readGroup(ctrl.tenant, groupId)
    code = group['realmRoles'][0] if group['realmRoles'] else ''
    await ctrl.keycloak.deleteGroup(ctrl.tenant, groupId)
    await ctrl.keycloak.deleteRoleByName(ctrl.tenant, code)
    await ctrl.minio.deletePolicy(code)
    return {
        'id': groupId,
        'sref': 'Group',
        'uref': f'{ctrl.uriver}/groups/{groupId}',
        'status': 'deleted'
    }
