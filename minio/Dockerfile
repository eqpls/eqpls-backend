FROM minio/minio:RELEASE.2024-05-10T01-41-38Z
EXPOSE 9000
EXPOSE 9001
COPY init.d/start.sh /start.sh
ENTRYPOINT ["/start.sh"]