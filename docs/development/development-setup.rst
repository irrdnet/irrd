=================
Development setup
=================

Development environment & unit tests
------------------------------------

This project uses poetry_.
The basic method to set up a local environment is::

    poetry install --no-root --with=dev,docs

Poetry will make a virtualenv by default, details of which you
can find in ``poetry env info``. The rest of this page assumes
you are running commands inside ``poetry shell``.

.. _poetry: https://python-poetry.org/

Some of the test use a live database for thoroughness. The database
URL needs to be set in ``IRRD_DATABASE_URL``, e.g. for a local database,
no authentication, database ``irrd_test``::

    export IRRD_DATABASE_URL=postgresql:///irrd_test

Some tests also require a running Redis instance, which needs to be set
in ``IRRD_REDIS_URL``, e.g.::

    export IRRD_REDIS_URL=redis://localhost/3

The tests will refuse to work on a database that already has tables.
Note that setting this environment variable will also override the database
for running IRRd itself.

To run the tests with py.test, you can simply run::

    pytest irrd

If you'd also like to measure coverage and see missing lines, run it as::

    pytest --cov-report term-missing:skip-covered --cov=irrd irrd

If you're running the tests on Mac OS X, there is an issue where default
temporary directories have names too long for GnuPG, causing a 5-second delay.
To avoid this, use ``--basetemp`` to set an alternate temporary directory, e.g.::

    pytest --cov-report term-missing:skip-covered --cov=irrd --basetemp=.tmpdirs/ irrd

You may also want to add ``-v`` for more verbose output.

Docker
------------------------------------

Docker files are provided in `docker/` which build a container that runs IRRd,
and also starts a Redis and Postgres container. An additional Postgres container
is provided for running pytest.

A default configuration file (`docker/irrd.yaml`) is used to run IRRd inside docker.

If you're unfamiliar with docker, some typical actions are:

* Build the IRRd container: `docker compose build`
* Start all containers: `docker compose up -d`
* Start a live log of the STDOUT from all containers: `docker compose logs -f`
* Drop into a BASH shell in the IRRd container: `docker compose exec irrd bash`

After starting the containers, these ports are exposed:

* localhost:8043 - irrd: whois daemon
* localhost:8080 - irrd: http daemon
* localhost:5432 - Postgres
* localhost:6379 - Redis
* localhost:5433 - Postgres instance for PyTest

Pytest can be ran from inside docker

    docker compose exec irrd bash
    export IRRD_DATABASE_URL=postgresql://test-postgresql:5432/irrd_test
    export IRRD_REDIS_URL=redis://redis/3
    poetry run pytest irrd/

Sphinx can also be run from inside docker:

    docker compose exec irrd bash
    git config --global --add safe.directory $(pwd)
    poetry -n --no-ansi run sphinx-build -nW -b spelling docs/ docs/build

To drop into a PostgreSQL shell use:

    docker compose exec postgresql psql

To drop into a Redis shell use:

    docker compose exec redis redis-cli

A script is included to import some real world data for testing during
development. The script downloads data from public IRR DBs, updates the IRRd
config to use these data sources, restarts IRRd to load the configuration 
changes, and ingests the downloaded data. The following command can be used
to import the data for testing:

    docker compose exec irrd bash -c "\$APP_PATH/docker/import_data.sh"

This data import can take several minutes to complete. After the import has
completed you can check the status IRRd by checking the `HTTP status page`_.

.. _HTTP status page: http://localhost:8080/v1/status/

Integration test
----------------

The integration test is not included when running ``pytest irrd``.
To run the integration test, two databases need to be configured, e.g.::

    export IRRD_DATABASE_URL_INTEGRATION_1=postgresql:///irrd_test1
    export IRRD_DATABASE_URL_INTEGRATION_2=postgresql:///irrd_test2

You'll also need two different Redis databases. You can use the same
instance with different database numbers, e.g.::

    export IRRD_REDIS_URL_INTEGRATION_1=redis://localhost/4
    export IRRD_REDIS_URL_INTEGRATION_2=redis://localhost/5

.. danger::
    The integration test will wipe all contents of IRRd tables in the databases
    ``IRRD_DATABASE_URL_INTEGRATION_1`` and ``IRRD_DATABASE_URL_INTEGRATION_2``,
    along with both redis databases, without further checks or confirmation.

The test can then be started with::

    pytest --basetemp=.tmpdirs/ -s -vv irrd/integration_tests/run.py

The `-s` parameter prevents `stdout` capture (i.e. shows stdout output in the
console), which gives some information about the test setup to aid in
debugging. This example also uses the temporary directory name fix for
Mac OS X, as suggested for unit tests.

The integration test will start two instances of IRRd, one mirroring off the
other, and an email server that captures all mail. It will then run a series
of updates and queries, verify the contents of mails, the state of the
databases, mirroring, UTF-8 handling and run all basic types of queries.

Code coverage is not measured for the integration test, as its purpose is
not to test all paths, but rather verify that the most important paths
are working end-to-end.

Linting and formatting
----------------------

In addition to the tests, this project uses `mypy`, `ruff`, `isort` and `black`
for style checking. Some are in a poe task for convenience. To run these, run::

    mypy irrd
    poe lint
    # To run ruff with auto fix:
    poe ruff-fix

Exclusions from checks
----------------------

Code can be excluded from code coverage, and can be excluded from checks by
`mypy`. This should be done in rare cases, where the quality of
the code would suffer otherwise, and for tests where the risks are small and
the effort would be great.

To ignore a line or block for test coverage, add ``# pragma: no cover`` to
the end, and ``# type:ignore`` to ignore `mypy` errors.

Docs
----

The documentation is written in reStructuredText, and an HTML version
can be generated with::

    cd docs
    make html
    open _build/html/index.html

If you're new to the RST format, you may find the `quick reference`_ helpful.

.. _quick reference: http://docutils.sourceforge.net/docs/user/rst/quickref.html

Making a release
----------------
To create a new packaged version of IRRD:

* Create the new release notes and commit them in the main branch.
* If this is a new minor release (x.y), update ``SECURITY.rst``.
* If you are adding changes from main to an existing release branch,
  cherry-pick the changes from the main branch, at least including the release
  notes commit. Version updates of dependencies are not generally applied to
  the release branch, except in case of known important bugs or security issues.
* Ensure the version is correct/updated in ``irrd/__init__.py`` and ``pyproject.toml``.
* Commit the version change (in the existing release branch if there is one).
* Tag the new release with git (`git tag v<version>`),
  and push the tag (`git push origin v<version>`).
* Run ``poetry build``
* Your source archive and built distribution are now in ``dist/``
* Create a new release on GitHub
* If this is not a pre-release, upload to PyPI with ``poetry publish``
* If this was a new minor release (x.y), create a new branch for it.

For more background, a good start is the `Python packaging tutorial`_.

.. _Python packaging tutorial: https://packaging.python.org/tutorials/packaging-projects/
