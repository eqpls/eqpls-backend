# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os
import time
import shutil
import docker
import argparse
import importlib
import configparser

#===============================================================================
# Implement
#===============================================================================
# load configs
path = os.path.dirname(os.path.realpath(__file__))
config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read(f'{path}/project.ini', encoding='utf-8')
client = docker.from_env()
default = config['default']

title = default['title']
tenant = default['tenant']
endpoint = default['endpoint']
version = default['version']
stage = default['stage']
system_access_key = default['system_access_key']
system_secret_key = default['system_secret_key']
admin_username = default['admin_username']
admin_password = default['admin_password']
health_check_interval = int(default['health_check_interval'])
health_check_timeout = int(default['health_check_timeout'])
health_check_retries = int(default['health_check_retries'])
modules = [m.strip() for m in default['modules'].split(',')]


#===============================================================================
# Container Control
#===============================================================================
# build
def build(module): client.images.build(nocache=True, rm=True, path=f'{path}/{module}', tag=f'{tenant}/{module}:{version}')


# deploy
def deploy(module):
    try: os.mkdir(f'{path}/{module}/conf.d')
    except: pass
    try: os.mkdir(f'{path}/{module}/data.d')
    except: pass
    try: os.mkdir(f'{path}/{module}/back.d')
    except: pass

    mod = importlib.import_module(f'{module}.deploy')
    image, command, options, post_exec = mod.parameters(module, path, config)

    container = client.containers.run(
        image=image,
        command=command,
        **options
    )

    while True:
        time.sleep(1)
        container.reload()
        print('check desire status of container')
        if container.status != 'running':
            print('container was exited')
            exit(1)
        if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
            print('container is healthy')
            if post_exec: container.exec_run(post_exec)
            break


# start
def start(module):
    try:
        for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.start()
    except: pass


# restart
def restart(module):
    try:
        for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.restart()
    except: pass


# stop
def stop(module):
    try:
        for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.stop()
    except: pass


# clean
def clean(module):
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.remove(v=True, force=True)
    shutil.rmtree(f'{path}/{module}/conf.d', ignore_errors=True)
    shutil.rmtree(f'{path}/{module}/data.d', ignore_errors=True)


# purge
def purge(module):
    try:
        for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.remove(v=True, force=True)
    except: pass
    try: client.images.remove(image=f'{tenant}/{module}:{version}', force=True)
    except: pass
    shutil.rmtree(f'{path}/{module}/conf.d', ignore_errors=True)
    shutil.rmtree(f'{path}/{module}/data.d', ignore_errors=True)


#===============================================================================
# Container Control
#===============================================================================
def print_help(message=None):
    if message: print(f'{message}\n')
    parser.print_help()
    print('support modules')
    for module in modules: print(f' - {module}')
    print()
    exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--build', action='store_true', help='build container')
    parser.add_argument('-d', '--deploy', action='store_true', help='deploy container')
    parser.add_argument('-s', '--start', action='store_true', help='start container')
    parser.add_argument('-r', '--restart', action='store_true', help='restart container')
    parser.add_argument('-t', '--stop', action='store_true', help='stop container')
    parser.add_argument('-c', '--clean', action='store_true', help='clean container')
    parser.add_argument('-p', '--purge', action='store_true', help='purge container')
    parser.add_argument('module', help='target module')
    args = parser.parse_args()

    if not (args.build or args.deploy or args.start or args.restart or args.stop or args.clean or args.purge):
        print_help(f'command option must be required')

    if args.module == 'all':
        if args.stop: modules = reversed(modules)
        elif args.clean: modules = reversed(modules)
        elif args.purge: modules = reversed(modules)
    elif args.module not in modules: print_help(f'"{args.module}" is not in modules')
    else: modules = [args.module]

    for module in modules:
        if args.stop: stop(module)
        if args.clean: clean(module)
        if args.purge: purge(module)
        if args.build: build(module)
        if args.deploy: deploy(module)
        if args.start: start(module)
        if args.restart: restart(module)
