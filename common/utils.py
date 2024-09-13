# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import sys
import base64
import random
import string
import logging
import datetime
import configparser

#===============================================================================
# Constnats
#===============================================================================
_LETTER_CANDIDATES = list(string.ascii_letters) + [str(i) for i in range(10)]
_LETTER_LOWER_CANDIDATES = list(string.ascii_lowercase) + [str(i) for i in range(10)]
_LETTER_UPPER_CANDIDATES = list(string.ascii_uppercase) + [str(i) for i in range(10)]


#===============================================================================
# Implement
#===============================================================================
def setEnvironment(key, value):
    __builtins__[key] = value
    return value


def getConfig(path):
    config = configparser.ConfigParser()
    config.read(path, encoding='utf-8')
    return config


class Logger:

    @classmethod
    def register(cls, config, name='uvicorn.default'): setEnvironment('LOG', Logger(config['default']['stage'], name))

    def __init__(self, stage, name):
        if name: self._logger = logging.getLogger(name=name)
        else:
            self._logger = logging.getLogger()
            self._logger.addHandler(logging.StreamHandler(sys.stdout))
        if 'dev' in stage: self._logger.setLevel(logging.DEBUG)
        else: self._logger.setLevel(logging.INFO)

    def _formatter_(self, message): return f'[{datetime.datetime.now()}] {message}'

    def KEYVAL(self, key, val): return f' - {key:<24} : {val}'

    def DEBUG(self, message): self._logger.debug(self._formatter_(message))

    def INFO(self, message): self._logger.info(self._formatter_(message))

    def WARN(self, message): self._logger.warning(self._formatter_(message))

    def ERROR(self, message): self._logger.error(self._formatter_(message))

    def CRITICAL(self, message): self._logger.critical(self._formatter_(message))


def mergeArray(arr1, arr2):
    return arr1 + list(set(arr2) - set(arr1))


def getNewsAndDelsArray(new, old):
    news = []
    dels = []
    for item in mergeArray(new, old):
        if item not in old: news.append(item)
        if item not in new: dels.append(item)
    return (news, dels)


def getSharesArray(arr1, arr2):
    shares = []
    for item in arr1:
        if item in arr2: shares.append(item)
    return shares


def getRandomString(length):
    return random.choice(string.ascii_letters) + ''.join(random.choice(_LETTER_CANDIDATES) for _ in range(length - 1))


def getRandomLower(length):
    return random.choice(string.ascii_lowercase) + ''.join(random.choice(_LETTER_LOWER_CANDIDATES) for _ in range(length - 1))


def getRandomUpper(length):
    return random.choice(string.ascii_uppercase) + ''.join(random.choice(_LETTER_UPPER_CANDIDATES) for _ in range(length - 1))


def encodeBase64(data):
    return base64.b64encode(data.encode('utf-8')).decode('ascii')


def decodeBase64(data):
    return base64.b64decode(data.encode('ascii')).decode('utf-8')

