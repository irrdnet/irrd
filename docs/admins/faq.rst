=====================
FAQ / troubleshooting
=====================

PostgreSQL error about multirow inserts
---------------------------------------

Any IRRd process that uses the database can fail with an error like::

    sqlalchemy.exc.CompileError: The 'default' dialect with current database version settings does not support in-place multirow inserts.

This error message is a red herring. The message that is actually about the
real error can be found earlier in the logs, and should be more helpful.
In several past cases, the true cause was the server running out of memory,
causing one of the PostgreSQL processed to be killed by the kernel.
