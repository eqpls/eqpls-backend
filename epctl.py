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
os.chdir(path)
config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.optionxform = str
config.read(f'{path}/project.ini', encoding='utf-8')
config = config._sections
client = docker.from_env()
defconf = config['default']

title = defconf['title']
tenant = defconf['tenant']
domain = defconf['domain']
endpoint = defconf['endpoint']

version = defconf['version']
stage = defconf['stage']

system_access_key = defconf['system_access_key']
system_secret_key = defconf['system_secret_key']
admin_username = defconf['admin_username']
admin_password = defconf['admin_password']

health_check_interval = defconf['health_check_interval']
health_check_timeout = defconf['health_check_timeout']
health_check_retries = defconf['health_check_retries']

modules = [m.strip() for m in defconf['modules'].split(',')]


#===============================================================================
# Container Control
#===============================================================================
# build
def build(module): client.images.build(nocache=True, rm=True, path=f'{path}/{module}', tag=f'{tenant}/{module}:{stage}-v{version}')


# deploy
def deploy(module):
    try: os.mkdir(f'{path}/{module}/conf.d')
    except: pass
    try: os.mkdir(f'{path}/{module}/test.d')
    except: pass

    importlib.import_module(f'{module}.deploy').config(path, module, config)

    modconf = config[module]
    envconf = config[f'{module}:environment']
    portconf = config[f'{module}:ports']
    volconf = config[f'{module}:volumes']
    healthconf = config[f'{module}:healthcheck']
    if 'test' not in healthconf: healthconf['test'] = 'echo "OK" || exit 1'
    if 'interval' not in healthconf: healthconf['interval'] = health_check_interval
    if 'timeout' not in healthconf: healthconf['timeout'] = health_check_timeout
    if 'retries' not in healthconf: healthconf['retries'] = health_check_retries

    hostname = modconf['hostname']
    memory = modconf['memory'] if 'memory' in modconf else None
    command = modconf['command'] if 'command' in modconf and modconf['command'] else None
    postcmd = modconf['postcmd'] if 'postcmd' in modconf and modconf['postcmd'] else None

    environment = [f'{k}={v}' for k, v in envconf.items()]

    ports = {}
    for internal, external in portconf.items():
        external = external.split(':')
        ports[internal] = (external[0], external[1])

    volumes = [f'{os.path.abspath(hostpath)}:{contpath}' for hostpath, contpath in volconf.items()]
    if stage == 'dev': volumes.append(f'{path}/{module}/test.d:/test.d',)

    healthcheck = {}
    if healthconf:
        healthcheck['test'] = healthconf['test']
        healthcheck['interval'] = int(healthconf['interval']) * 1000000000
        healthcheck['timeout'] = int(healthconf['timeout']) * 1000000000
        healthcheck['retries'] = int(healthconf['retries'])

    options = {
        'detach': True,
        'init': True,
        'name': f'{tenant}-{module}',
        'hostname': hostname,
        'network': tenant,
        'mem_limit': memory,
        'environment': environment,
        'ports': ports,
        'volumes': volumes,
        'healthcheck': healthcheck,
    }

    container = client.containers.run(
        image=f'{tenant}/{module}:{stage}-v{version}',
        command=command,
        **options
    )

    print(f'[{module}] check status .', end='', flush=True)
    while True:
        time.sleep(1)
        container.reload()
        print('.', end='', flush=True)
        if container.status != 'running':
            print(f'\n[{module}] was exited', flush=True)
            exit(1)
        if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
            print(' [ OK ]', flush=True)
            if postcmd: container.exec_run(postcmd)
            break


# start
def start(module):
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}):
        container.start()
        print(f'[{module}] check status .', end='', flush=True)
        while True:
            time.sleep(1)
            container.reload()
            print('.', end='', flush=True)
            if container.status != 'running':
                print(f'\n[{module}] was exited', flush=True)
                exit(1)
            if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
                print(' [ OK ]', flush=True)
                break


# restart
def restart(module):
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}):
        container.restart()
        print(f'[{module}] check status .', end='', flush=True)
        while True:
            time.sleep(1)
            container.reload()
            print('.', end='', flush=True)
            if container.status != 'running':
                print(f'\n[{module}] was exited', flush=True)
                exit(1)
            if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
                print(' [ OK ]', flush=True)
                break


# stop
def stop(module):
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.stop()


# clean
def clean(module):
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-{module}'}): container.remove(v=True, force=True)
    shutil.rmtree(f'{path}/{module}/conf.d', ignore_errors=True)
    shutil.rmtree(f'{path}/{module}/data.d', ignore_errors=True)


# purge
def purge(module):
    clean(module)
    try: client.images.remove(image=f'{tenant}/{module}:{stage}-v{version}', force=True)
    except: pass


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
