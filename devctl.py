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
import os
import time
import shutil
import docker
import argparse
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

tenant = defconf['tenant']
endpoint = defconf['endpoint']
version = defconf['version']
stage = defconf['stage']

health_check_interval = defconf['health_check_interval']
health_check_timeout = defconf['health_check_timeout']
health_check_retries = defconf['health_check_retries']

webConf = config['nginx']
proxies = [proxy.strip() for proxy in webConf['proxies'].split(',')] if 'proxies' in webConf else []


#===============================================================================
# Container Control
#===============================================================================
# build
def build(): client.images.build(nocache=True, rm=True, path=f'{path}/webself', tag=f'{tenant}/webself:{stage}-v{version}')


# deploy
def deploy():
    try: os.mkdir(f'{path}/webself/conf.d')
    except: pass

    locations = ['''
location /auth/ {
add_header 'Access-Control-Allow-Origin' '*';
add_header 'Access-Control-Allow-Methods' '*';
add_header 'Access-Control-Allow-Headers' '*';
add_header 'Access-Control-Allow-Credentials' 'true';
proxy_pass https://%s/auth/;
}
''' % endpoint, '''
location /minio/ {
add_header 'Access-Control-Allow-Origin' '*';
add_header 'Access-Control-Allow-Methods' '*';
add_header 'Access-Control-Allow-Headers' '*';
add_header 'Access-Control-Allow-Credentials' 'true';
proxy_pass https://%s/minio/;
}
''' % endpoint, '''
location /guacamole/ {
add_header 'Access-Control-Allow-Origin' '*';
add_header 'Access-Control-Allow-Methods' '*';
add_header 'Access-Control-Allow-Headers' '*';
add_header 'Access-Control-Allow-Credentials' 'true';
proxy_pass https://%s/guacamole/;
}
''' % endpoint]

    for p in proxies:
        locations.append('''
location /%s/ {
add_header 'Access-Control-Allow-Origin' '*';
add_header 'Access-Control-Allow-Methods' '*';
add_header 'Access-Control-Allow-Headers' '*';
add_header 'Access-Control-Allow-Credentials' 'true';
proxy_pass https://%s/%s/;
}
''' % (p, endpoint, p))

    with open(f'{path}/webself/conf.d/default.conf', 'w') as fd: fd.write(\
'''
server {
listen 443 ssl;
server_name localhost;

%s

location / {
add_header 'Access-Control-Allow-Origin' '*';
add_header 'Access-Control-Allow-Methods' '*';
add_header 'Access-Control-Allow-Headers' '*';
add_header 'Access-Control-Allow-Credentials' 'true';
alias /webroot/;
}
}

''' % ''.join(locations))

    options = {
        'detach': True,
        'init': True,
        'name': f'{tenant}-webself',
        'hostname': 'webself',
        'network': tenant,
        'ports': {
            '443/tcp': ('0.0.0.0', '443')
        },
        'volumes': [f'{os.path.abspath(hostpath)}:{contpath}' for hostpath, contpath in {'./webroot': '/webroot', './webcert': '/webcert', './webself/conf.d': '/conf.d'}.items()],
        'healthcheck': {
            'test': 'curl -k https://127.0.0.1 || exit 1',
            'interval': int(health_check_interval) * 1000000000,
            'timeout': int(health_check_timeout) * 1000000000,
            'retries': int(health_check_retries)
        }
    }

    container = client.containers.run(
        image=f'{tenant}/webself:{stage}-v{version}',
        **options
    )

    print(f'[webself] check status .', end='', flush=True)
    while True:
        time.sleep(1)
        container.reload()
        print('.', end='', flush=True)
        if container.status != 'running':
            print(f'\n[webself] was exited', flush=True)
            exit(1)
        if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
            print(' [ OK ]', flush=True)
            break


# start
def start():
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-webself'}):
        container.start()
        while True:
            time.sleep(1)
            container.reload()
            print('.', end='', flush=True)
            if container.status != 'running':
                print(f'\n[webself] was exited', flush=True)
                exit(1)
            if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
                print(' [ OK ]', flush=True)
                break


# restart
def restart():
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-webself'}):
        container.restart()
        while True:
            time.sleep(1)
            container.reload()
            print('.', end='', flush=True)
            if container.status != 'running':
                print(f'\n[webself] was exited', flush=True)
                exit(1)
            if 'Health' in container.attrs['State'] and container.attrs['State']['Health']['Status'] == 'healthy':
                print(' [ OK ]', flush=True)
                break


# stop
def stop():
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-webself'}): container.stop()


# clean
def clean():
    for container in client.containers.list(all=True, filters={'name': f'{tenant}-webself'}): container.remove(v=True, force=True)
    shutil.rmtree(f'{path}/webself/conf.d', ignore_errors=True)


# purge
def purge():
    clean()
    try: client.images.remove(image=f'{tenant}/webself:{stage}-v{version}', force=True)
    except: pass


#===============================================================================
# Container Control
#===============================================================================
def print_help(message=None):
    if message: print(f'{message}\n')
    parser.print_help()
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
    args = parser.parse_args()

    if not (args.build or args.deploy or args.start or args.restart or args.stop or args.clean or args.purge): print_help(f'command option must be required')

    if args.stop: stop()
    if args.clean: clean()
    if args.purge: purge()
    if args.build: build()
    if args.deploy: deploy()
    if args.start: start()
    if args.restart: restart()
