FROM docker.arvancloud.ir/nginx:1.30-alpine

RUN cp /dev/null /etc/apk/repositories && \
    mkdir -p /var/www/static/ \
    /var/www/next_static/ \
    /etc/ssl \
    /etc/letsencrypt/ && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/main" >> /etc/apk/repositories && \
    echo "https://mirror.mobinhost.com/alpine/v3.22/community" >> /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add bash curl openssl
