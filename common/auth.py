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
from pydantic import BaseModel
from .exceptions import EpException


#===============================================================================
# Implement
#===============================================================================
class LoginRequest(BaseModel):

    username:str
    password:str


class UserInfo(BaseModel):

    id:str
    username: str
    email: str
    admin: bool
    firstName: str
    lastName: str
    groups: list[str] = []


class AuthInfo(BaseModel):

    id: str
    username: str
    email: str
    admin: bool
    groups: list[str] = []
    aclRead: list[str] = []
    aclCreate: list[str] = []
    aclUpdate: list[str] = []
    aclDelete: list[str] = []

    def checkAdmin(self):
        if self.admin: return self
        raise EpException(403, 'Forbidden')

    def checkUsername(self, username):
        if self.admin or self.username == username: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyUsername(self, username):
        if self.username == username: return username
        raise EpException(403, 'Forbidden')

    def checkGroup(self, group):
        if self.admin or group in self.groups: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyGroup(self, group):
        if group in self.groups: return group
        raise EpException(403, 'Forbidden')

    def checkRead(self, sref):
        if self.admin or sref in self.aclRead: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyRead(self, sref):
        if sref in self.aclRead: return sref
        raise EpException(403, 'Forbidden')

    def checkCreate(self, sref):
        if self.admin or sref in self.aclCreate: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyCreate(self, sref):
        if sref in self.aclCreate: return sref
        raise EpException(403, 'Forbidden')

    def checkUpdate(self, sref):
        if self.admin or sref in self.aclUpdate: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyUpdate(self, sref):
        if sref in self.aclUpdate: return sref
        raise EpException(403, 'Forbidden')

    def checkDelete(self, sref):
        if self.admin or sref in self.aclDelete: return self
        raise EpException(403, 'Forbidden')

    def checkOnlyDelete(self, sref):
        if sref in self.aclDelete: return sref
        raise EpException(403, 'Forbidden')


class User(BaseModel):

    id:str = ''
    sref:str = ''
    uref:str = ''
    username:str
    email:str
    firstName:str = ''
    lastName:str = ''


class Group(BaseModel):

    id:str = ''
    parentId:str = ''
    sref:str = ''
    uref:str = ''
    code:str
    name:str
    path:str = ''
    subGroupCount:int = 0


class AccessControl(BaseModel):

    sref:str
    crud:str
