FROM python:3

# Initialize
RUN mkdir -p /data/django
WORKDIR /data/django

# Setup
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y locales netcat && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# maybe needed  libpq-dev

ENV LANG=en_US.UTF-8
RUN locale-gen en_US.UTF-8

RUN pip3 install --upgrade pip

# Prepare
COPY . /data/django/

RUN pip3 install --upgrade -r requirements.txt

RUN python3 manage.py collectstatic --noinput

CMD /usr/local/bin/gunicorn ct_backend.wsgi:application -w 10 --timeout 120 -b :5000