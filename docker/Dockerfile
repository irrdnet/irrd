FROM ubuntu:24.04

# Install requirements
RUN DEBIAN_FRONTEND=noninteractive apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
ca-certificates build-essential git gpg libenchant-2-2 libpq-dev netcat-traditional python3-dev pipx wget
RUN apt-get clean && \
rm -rf /var/lib/apt/lists/*

ARG APP_PATH
ARG CONFIG_FILE

# BASH is needed for Poetry to work at build time
SHELL ["/bin/bash", "-c"]

# Setup poetry
RUN pipx install poetry
# Persist poetry path to $PATH in ~/.bashrc for run-time availability
RUN pipx ensurepath
# Add poetry path to current $PATH for build-time availability
ENV PATH="/root/.local/bin:${PATH}"

# Setup irrd
WORKDIR $APP_PATH/
COPY ./pyproject.toml $APP_PATH/pyproject.toml
COPY ./poetry.lock $APP_PATH/poetry.lock
# "poetry config virtualenvs.create false" will install the poetry dependencies
# globally, not in a venv. This would be ideal, it allows all apps to access the
# dependencies. This is not supported by pipx though, it will throw an error
# that this clashes with any dependencies installed by the system package
# manager.
#
# So we need to install poetry dep's in a venv. This can be problematic because
# IRRd forks threads/processes and they don't run in the same poetry venv with
# all the poetry managed dep's. To resolve this:
# Install poetry dep's in a venv (default) but force the venv to be in the
# project directory (non-default), so that they the venv is in a consistent
# location ($APP_PATH/.venv). Then we can make the venv python bin our default
# python bin, and all applications and threads/forks will have access to the
# poetry dep's.
RUN poetry config virtualenvs.create true && \
poetry config virtualenvs.in-project true && \
poetry install -vv --no-interaction --with=dev,docs

# Copy a config file into the container with the relevant settings to access the
# other containers (postgres and redis).
# This can be overrider by the build argument.
COPY $CONFIG_FILE /etc/irrd.yaml

RUN useradd irrd
