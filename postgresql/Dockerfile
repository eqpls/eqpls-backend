FROM postgres:16.3-alpine3.20
EXPOSE 5432
RUN echo ". /init.d/init.sh" > /docker-entrypoint-initdb.d/init.sh
CMD ["-c", "config_file=/conf.d/postgresql.conf"]
