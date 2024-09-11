# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

import os


def parameters(module, path, config):
    default = config['default']
    modconf = config[module]

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

    hostname = modconf['hostname']
    hostaddr = modconf['hostaddr']
    hostport = int(modconf['hostport'])
    export = int(modconf['export']) if modconf['export'] and modconf['export'].lower() != 'false' else None
    memory = modconf['memory']

    publish = os.path.abspath(modconf['publish'])
    proxies = filter(None, [p.strip() for p in modconf['proxies'].split(',')])

    upstreams = ''
    locations = ''
    servers = ''
    
    ports = {
        f'{hostport}/tcp': (hostaddr, hostport)
    } if export else {}

    if 'guacamole' in modules:
        upstreams += '''
    upstream guacamole { server guacamole:8080; }
'''

        locations += '''
        location /guacamole/ { proxy_pass http://guacamole/guacamole/; }
'''

    if 'objstore' in modules:
        if export: ports['9000/tcp'] = (hostaddr, 9000)
        
        upstreams += '''
    upstream objstore-s3 { server objstore:9000; }

    upstream objstore-ui { server objstore:9001; }
'''
        servers += '''
    server {
        listen 9000 ssl;
        server_name %s;
        location / {
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            proxy_connect_timeout 300;
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
            proxy_pass http://objstore-s3/;
        }
    }
''' % endpoint

        locations += '''
        location /objstore/oauth/callback {
            default_type application/json;
            return 200 '{"code":"$arg_code","state":"$arg_state"}';
        }

        location /objstore/ {
            rewrite ^/objstore/(.*) /$1 break;
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-NginX-Proxy true;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            real_ip_header X-Real-IP;
            proxy_connect_timeout 300;
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
            proxy_pass http://objstore-ui;
        }
'''

    for p in proxies:
        prxconf = config[p]
        prxname = prxconf['hostname']

        upstreams += '''
    upstream %s { server %s:%s; }
''' % (prxname, prxname, prxconf['hostport'])

        locations += '''
        location /%s/ { proxy_pass http://%s/%s/; }
''' % (prxname, prxname, prxname)

    with open(f'{path}/{module}/conf.d/nginx.conf', 'w') as fd: fd.write(\
"""
user root;
worker_processes 1;
events {
    worker_connections 1024;
    multi_accept on;
    use epoll;
}
http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 0;
    large_client_header_buffers 4 128k;
    ssl_certificate_key /webcert/server.key;
    ssl_certificate /webcert/server.crt;
    ssl_session_timeout 10m;
    ssl_protocols SSLv2 SSLv3 TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    resolver 127.0.0.11 valid=2s;
    proxy_buffers 4 256k;
    proxy_buffer_size 128k;
    proxy_busy_buffers_size 256k;
    proxy_http_version 1.1;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    server {
        listen 443 ssl;
        server_name %s;

        location /auth/ {
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Server $host;
            proxy_pass http://keycloak/;
        }
%s
        location / { alias /webroot/; }
    }
    
%s

    upstream keycloak { server keycloak:8080; }
%s
}
""" % (endpoint, locations, servers, upstreams))

    environment = [
    ]

    volumes = [
        f'{path}/{module}/conf.d/nginx.conf:/etc/nginx/nginx.conf',
        f'{publish}:/webroot',
        f'{path}/webcert:/webcert',
        f'{path}/{module}/data.d:/data.d',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': 'curl -kv https://127.0.0.1 || exit 1',
        'interval': health_check_interval * 1000000000,
        'timeout': health_check_timeout * 1000000000,
        'retries': health_check_retries
    }

    restart_policy = None

    command = None
    options = {
        'detach': True,
        'name': f'{tenant}-{module}',
        'hostname': hostname,
        'network': tenant,
        'mem_limit': memory,
        'ports': ports,
        'environment': environment,
        'volumes': volumes,
        'healthcheck': healthcheck,
        'restart_policy': restart_policy
    }
    post_exec = None

    return (f'{tenant}/{module}:{version}', command, options, post_exec)
