FROM ubuntu:22.04

ARG DATA_PATH

# BASH is needed for Poetry to work at build time
SHELL ["/bin/bash", "-c"]

# Install requirements
RUN DEBIAN_FRONTEND=noninteractive apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y ca-certificates build-essential python3-dev pipx wget gpg git

# Get some example data from RIPE and RADB
RUN mkdir "$DATA_PATH"
RUN wget -nc -O "${DATA_PATH}/ripe.db.as-set.gz" https://ftp.ripe.net/ripe/dbase/split/ripe.db.as-set.gz
RUN wget -nc -O "${DATA_PATH}/ripe.db.aut-num.gz" https://ftp.ripe.net/ripe/dbase/split/ripe.db.aut-num.gz
RUN wget -nc -O "${DATA_PATH}/ripe.db.route-set.gz" https://ftp.ripe.net/ripe/dbase/split/ripe.db.route-set.gz
RUN wget -nc -O "${DATA_PATH}/ripe.db.route.gz" https://ftp.ripe.net/ripe/dbase/split/ripe.db.route.gz
RUN wget -nc -O "${DATA_PATH}/ripe.db.route6.gz" https://ftp.ripe.net/ripe/dbase/split/ripe.db.route6.gz
RUN wget -nc -O "${DATA_PATH}/RIPE.CURRENTSERIAL" https://ftp.ripe.net/ripe/dbase/RIPE.CURRENTSERIAL
RUN wget -nc -O "${DATA_PATH}/radb.db.gz" ftp://ftp.radb.net/radb/dbase/radb.db.gz
RUN wget -nc -O "${DATA_PATH}/RADB.CURRENTSERIAL" ftp://ftp.radb.net/radb/dbase/RADB.CURRENTSERIAL

# Setup irrd
RUN pipx ensurepath
RUN pipx install poetry
COPY ./pyproject.toml /irrd/pyproject.toml
RUN cd /irrd/ && \
/root/.local/bin/poetry config virtualenvs.create false && \
/root/.local/bin/poetry install -vv --no-interaction --with=dev,docs
RUN useradd irrd
