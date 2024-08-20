FROM keycloak/keycloak:25.0.1
EXPOSE 7800
EXPOSE 8080
EXPOSE 9000
COPY init.d/themes/custom-theme /opt/keycloak/themes/custom-theme
ENTRYPOINT ["/opt/keycloak/bin/kc.sh", "start"]