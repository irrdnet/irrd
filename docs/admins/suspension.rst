=====================
Maintainer suspension
=====================

Maintainer suspension allows IRRD admins to suspend a maintainer and all
objects it maintains. When an object is suspended, IRRD acts as if it was
deleted, with the exception that it can be reactivated. Suspension and
reactivation have a shared or similar interface to
:doc:`regular authoritative database changes </users/database-changes>`,
are only accessible with the override password, and are opt-in.
Suspension is intended to support admins who restrict access to their
IRR database.

Impact of suspension and reactivation
-------------------------------------
You can submit a suspension for a `mntner` in a source that is both
authoritative and has ``suspension_enabled`` set. When you do this, the
following happens:

* IRRD finds the `mntner` object and all objects with this `mntner` in
  their ``mnt-by``. If the `mntner` object does not exist (or is already suspended)
  IRRD rejects the request.
* For each object, IRRD checks whether it has any other currently existing
  and non-suspended `mntners`. If it does have other maintainers, the object
  is left as is.
* The `mntner` that is suspended and any object that has this maintainer as
  its only active `mnt-by`, is deleted from the active RPSL objects and stored
  in a separate storage.
* IRRD writes deletion entries to the journal, causing the suspended objects
  to be deleted from mirrors.
* You receive a response, similar to that of any other object change,
  of the status and a list of all objects included in the suspension.
* No other notifications of any kind are sent to anyone.

A suspended object is similar to a regular deleted object:

* It does not occur in any database export.
* It can not be returned by any query.
* It can not be referred to from any object.
* It can not be used for authentication.

Other than allowing reactivation, there is one situation where suspended
objects have an impact: it is not permitted to create a `mntner` with the same
primary key as an already suspended object. The reason is that if that second
`mntner` would also be suspended, IRRD would be unable to distinguish them.

When you reactivate an object, the following happens:

* IRRD finds the suspended `mntner` object and all objects that had this
  `mntner` in their ``mnt-by`` when they were suspended. If the `mntner` is
  not found in the suspended object store, IRRD rejects the request.
* For each object, IRRD checks whether there is a (newer) active object with
  the same primary key. If this exists, the object is not restored,
  but the IRRD will continue to restore the other objects.
  Note that the `mntner` you are suspending will always be suspended,
  regardless of its own ``mnt-by`` value.
* IRRD writes NRTM add entries to the journal, causing the suspended objects
  to be reappear on mirrors.
* The creation time of the reactivated objects is set to the original
  creation time before suspension. The last updated time is updated upon
  reactivation.
* You receive a response, similar to that of any other object change,
  of the status and a list of all objects that were reactivated, and which
  were skipped due to a primary key conflict.
* No other notifications of any kind are sent to anyone.

.. tip::
   As IRRD sends no notifications of any kind to users for suspensions and
   reactivations, it is up to you to communicate this. To your user, the objects
   have simply disappeared.

Multiple maintainers
--------------------
When reactivating objects, it is important to note that IRRD restores all
objects that **at the time of that object's suspension**, had the reactivated
`mntner` in their ``mnt-by``, in the state they had at the time of their
suspension. This is potentially different from: all
objects that **at the time of the mntner's suspension**, had the reactivated
`mntner` in their ``mnt-by``, in the state they had at the time of that 
maintainer's suspension. The distinction matters with multiple
maintainer suspensions, which are rare but complex.

Consider the following:

* MNT-A and MNT-B are both in the ``mnt-by`` of ROLE-EXAMPLE
* MNT-A is suspended
* ROLE-EXAMPLE remains active, because MNT-B is still active
* MNT-B is suspended
* ROLE-EXAMPLE is suspended, because it has no active maintainers
* MNT-A is reactivated
* ROLE-EXAMPLE is restored, because at the time it was suspended,
  MNT-A was still in ``mnt-by``, even though it was the suspension
  of MNT-B that caused ROLE-EXAMPLE to be suspended itself

Broken references
-----------------
IRRD usually rejects the deletion or creation of authoritative objects if
this creates broken references. Suspensions and reactivations are exempt
from this requirement. IRRD will suspend an object even if there are
other references to it, and will reactivate an object even if it has
references to other objects that do not currently exist.

As with any legacy objects, users making later regular changes to these
objects must fix the broken references when submitting any modification.

Submitting suspensions and reactivations
----------------------------------------

There are two ways to submit suspensions and reactivations: the HTTP API,
or e-mail submission. 

HTTP API
^^^^^^^^
To submit changes over HTTP, make a POST or DELETE request to ``/v1/suspension/``.
For example, if the IRRd instance is running on ``rr.example.net``, the URL is::

    https://rr.example.net/v1/submit/

The expected request body is a JSON object, with a number of keys:

* ``objects``: a list of objects. Each is a JSON object with
  a ``mntner``, ``source`` and ``request_type`` key. The ``request_type``
  is either ``suspend`` or ``reactivate``.
* ``override``: an string containing the override password.

Here's an example::

  {
      "objects":[
          {
              "mntner":"EXAMPLE-MNT",
              "source":"EXAMPLE",
              "request_type":"suspend"
          }
      ],
      "override":"my-password"
  }

The responses are the same as the
:ref:`regular object submission API <database-changes-http-api-response>`.
The objects that were suspended or reactivated are listed in ``info_messages``.

Submitting over e-mail
^^^^^^^^^^^^^^^^^^^^^^
Submitting over e-mail is done using the same e-mail interface as other
object submissions.

Suspension and reactivation are set with the special ``suspension`` attribute
which must be part of the object, similar to the ``delete`` attribute. Valid
values are ``suspend`` and ``reactivate``.
You can use a shortened `mntner` syntax, like so::

    override: my-password

    suspension: suspend
    mntner:     EXAMPLE-MNT
    source:     EXAMPLE
