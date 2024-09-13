#!/bin/sh

/usr/bin/docker-entrypoint.sh server --address="0.0.0.0:9000" --console-address=":9001" $DATA_STORE_LIST