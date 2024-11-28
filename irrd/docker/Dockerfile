# description="IRRd4 Docker Image"
#
# Dockerfile for the IRRd4 application.
#
# This Dockerfile sets up a Python 3.12.3 environment and installs the necessary dependencies for running the IRRd4 application. It copies an init script to the container, updates the package lists, installs build tools and other required packages, installs the IRRd4 package, and sets up the necessary directories and permissions.
#
# The resulting Docker image can be used to run the IRRd4 application in a containerized environment.

FROM python:3.12.3-bookworm

ARG IRRD_VERSION=4.4.4

COPY init.sh /app/irrd/init.sh

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc gnupg dumb-init cron

RUN pip install --no-cache-dir -U pip psycopg2 \
    && pip install --no-cache-dir irrd==$IRRD_VERSION

RUN apt-get clean autoclean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/run/irrd
RUN chown daemon:daemon /var/run/irrd

CMD ["/app/irrd/init.sh"]
