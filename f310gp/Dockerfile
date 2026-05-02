FROM ghcr.io/home-assistant/base-python:3.14-alpine3.23

RUN pip3 install --no-cache-dir paho-mqtt paramiko

WORKDIR /data
COPY run.sh /
COPY f310gp_hass.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
