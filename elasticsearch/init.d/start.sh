#!/bin/sh

initSystemUser () {
if [ ! -f /deployed ]; then
while true; do
	curl -k -f https://localhost:9200
	HEALTH=$(echo $?)
	if [ $HEALTH == 22 ]; then break; fi
	sleep 2
done
sleep 1
/usr/share/elasticsearch/bin/elasticsearch-users useradd $EQPLS_SYSTEM_ACCESS_KEY -p "$EQPLS_SYSTEM_SECRET_KEY" -r superuser -s
touch /deployed
fi
}

initSystemUser &
su elasticsearch -c "/bin/tini -- /usr/local/bin/docker-entrypoint.sh eswrapper"