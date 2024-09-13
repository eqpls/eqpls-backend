FROM elasticsearch:8.14.0
EXPOSE 9200
USER 0:0
COPY init.d/start.sh /start.sh
ENTRYPOINT ["/start.sh"]

