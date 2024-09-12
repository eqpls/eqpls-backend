# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    modconf = config[module]

    endpoint = defconf['endpoint']
    modules = [m.strip() for m in defconf['modules'].split(',')]
    proxies = [proxy.strip() for proxy in modconf['proxies'].split(',')] if 'proxies' in modconf else []

    upstreams = []
    locations = []

    if 'keycloak' in modules:
        upstreams.append('''
upstream keycloak { server keycloak:8080; }
''')
        locations.append('''
location /auth/ {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Server $host;
    proxy_pass http://keycloak/auth/;
}
''')

    if 'guacamole' in modules:
        upstreams.append('''
upstream guacamole { server guacamole:8080; }
''')
        locations.append('''
location /guacamole/ { proxy_pass http://guacamole/guacamole/; }
''')

    if 'minio' in modules:
        upstreams.append('''
upstream minio-ui { server minio:9001; }
''')
        locations.append('''
location /minio/oauth/callback {
    default_type application/json;
    return 200 '{"code":"$arg_code","state":"$arg_state"}';
}
location /minio/ {
    rewrite ^/minio/(.*) /$1 break;
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
    proxy_pass http://minio-ui;
}
''')

        with open(f'{path}/{module}/conf.d/s3.conf', 'w') as fd:
            fd.write('''
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
        proxy_pass http://minio-s3/;
    }
}
upstream minio-s3 { server minio:9000; }
''' % (endpoint))

    for p in proxies:
        prxconf = config[p]
        prxname = prxconf['hostname']
        prxport = prxconf['hostport']
        upstreams.append('''
upstream %s { server %s:%s; }
''' % (prxname, prxname, prxport))
        locations.append('''
location /%s/ { proxy_pass http://%s/%s/; }
''' % (prxname, prxname, prxname))

    with open(f'{path}/{module}/conf.d/default.conf', 'w') as fd: fd.write(\
'''
server {
listen 443 ssl;
server_name %s;
%s
location / { alias /webroot/; }
}
%s
''' % (endpoint, ''.join(locations), ''.join(upstreams)))
