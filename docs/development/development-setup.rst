=================
Development setup
=================

Development environment & tests
-------------------------------

The basic method to set up a local environment is::

    mkvirtualenv -p `which python3` irrd4
    pip install -r requirements.txt

Some of the test use a live database for thoroughness. The database
URL needs to be set in ``IRRD_DATABASE_URL``, e.g. for a local database,
no authentication, database ``irrd_test``::

    export IRRD_DATABASE_URL=postgresql:///irrd_test

The tests will refuse to work on a database that already has tables.
Note that setting this environment variable will also override the database
for running IRRd itself.

To run the tests with py.test, you can simply run::

    pytest irrd

If you'd also like to measure coverage and see missing lines, run it as::

    pytest --cov-report term-missing --cov=irrd irrd

If you're running the tests on Mac OS X, there is an issue where default
temporary directories have names too long for GnuPG, causing a 5-second delay.
To avoid this, use ``--basetemp`` to set an alternate temporary directory, e.g.::

    pytest --cov-report term-missing --cov=irrd --basetemp=.tmpdirs/ irrd

You may also want to add ``-v`` for more verbose output.

In addition to the tests, this project uses `mypy` for type checking and `flake8`
for style checking. To run these, run::

    mypy irrd --ignore-missing-imports
    flake8

If all is well, neither command should provide output.

Exclusions from checks
----------------------

Code can be excluded from code coverage, and can be excluded from checks by
`mypy` and `flake8`. This should be done in rare cases, where the quality of
the code would suffer otherwise, and for tests where the risks are small and
the effort would be great.

To ignore a line or block for test coverage, add ``# pragma: no cover`` to
the end, ``# type:ignore`` to ignore `mypy` errors, and ``# noqa: <number>``
for `flake8` violations. For the latter, the number is the error number
from the command output.

Docs
----

The documentation is written in reStructuredText, and an HTML version
can be generated with::

    cd docs
    make html
    open _build/html/index.html

If you're new to the RST format, you may find the `quick reference`_ helpful.

.. _quick reference: http://docutils.sourceforge.net/docs/user/rst/quickref.html

Packaging
---------
To create a new packaged version of IRRD:

* If this is a new minor release (x.y), create a new branch for it first - otherwise
  switch to the branch of the current minor release.
* Ensure the version is correct/updated in ``irrd/__init__.py`` and ``setup.py``.
* Commit the version change.
* Tag the new release with git (`git tag -a <tagname>`),
  and push the tag (`git push origin <tag_name>`).
* Run ``./setup.py sdist bdist_wheel``
* Your source archive and built distribution are now in ``dist/``
* Upload them to PyPI with ``twine upload dist/*``

For more background, a good start is the `Python packaging tutorial`_.

.. _Python packaging tutorial: https://packaging.python.org/tutorials/packaging-projects/
