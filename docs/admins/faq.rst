=====================
FAQ / troubleshooting
=====================

PostgreSQL error about multirow inserts
---------------------------------------

Any IRRd process that uses the database can fail with an error like::

    sqlalchemy.exc.CompileError: The 'default' dialect with current
    database version settings does not support in-place multirow inserts.

This error message is a red herring. The message that is actually about the
real error can be found earlier in the logs, and should be more helpful.
In several past cases, the true cause was the server running out of memory,
causing one of the PostgreSQL processed to be killed by the kernel.


NRTM errors in the logs
-----------------------

If you mirror other sources over NRTM, you might see log messages like::

    Received NRTM response for DEMO: %% ERROR: Serials 23092 - 305951 do not exist

These may not be errors. There are two explanations:

* Working as intended. In NRTMv3, IRRd mirrors up to the most recent serial.
  Then, on every update requests all updates from the latest known serial plus 1.
  However, that serial might not exist yet, causing the error above.
* Mirroring not working. Your instance may be out of sync, and too far behind
  to catch up with NRTM.

Unfortunately, the error messages in NRTMv3 can be ambiguous for these kind
of cases. Some are more clear - "access denied" usually means only that. Some
also distinguish better whether the requested serials are too new or too old.
In general, to check whether or not you are up to date, you can use the
`!J` or `!j` queries on the NRTM source and your local instance.
