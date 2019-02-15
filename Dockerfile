FROM alpine:3.9

RUN apk add --update --no-cache \
        gcc \
        git \
        libffi-dev \
        musl-dev \
        openssh-client \
        openssl-dev \
        python3 \
        python3-dev

RUN pip3 install --no-cache-dir --upgrade \
        docopt \
        gitpython \
        jinja2 \
        kubernetes \
        prometheus_client

RUN apk del --purge \
        gcc \
        libffi-dev \
        musl-dev \
        openssl-dev \
        python3-dev

RUN rm -rf \
        /var/cache/apk/* \
        /root/.cache \
        /tmp/*

ADD *.py /work/
ADD templates /work/templates

WORKDIR /work

ENTRYPOINT ["python3", "-u", "main.py"]
