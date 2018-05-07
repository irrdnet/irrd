===========
Development
===========

Development environment & tests
-------------------------------

The basic method to set up a local environment is::

    mkvirtualenv -p `which python3` irrd4
    pip install -r requirements.txt

To run the tests with py.test, you can simply run::

    pytest irrd

If you'd also like to measure coverage and see missing lines, run it as::

    pytest --cov-report term-missing --cov=irrd irrd

If you're running the tests on Mac OS X, there is an issue where default
temporary directories have names too long for GnuPG, causing a 5-second delay.
To avoid this, use ``--basetemp`` to set an alternate temporary directory, e.g.::

    pytest --cov-report term-missing --cov=irrd --basetemp=.tmpdirs/ irrd

You may also want to add ``-v`` for more verbose output.

Docs
----

The documentation is written in reStructuredText, and an HTML version
can be generated with::

    cd docs
    make html
    open _build/html/index.html

If you're new to the RST format, you may find the `quick reference`_ helpful.

.. _quick reference: http://docutils.sourceforge.net/docs/user/rst/quickref.html
