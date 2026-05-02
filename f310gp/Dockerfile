ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.14-alpine3.23
FROM ${BUILD_FROM}

RUN pip3 install --no-cache-dir paho-mqtt paramiko

COPY run.sh /
COPY f310gp_hass.py /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
