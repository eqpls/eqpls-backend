#!/bin/sh

echo -n "export MINIO_IDENTITY_OPENID_CLIENT_SECRET_PRIMARY_IAM=" > /client_secret
curl -s "http://uerp:8090/internal/client/secret?org=eqpls&client=minio" >> /client_secret
. /client_secret
/usr/bin/docker-entrypoint.sh "$@"