# Zotero black-box reconstruction

Recreate **Zotero 10.0.6** from scratch based only on its observable behavior. A
running reference installation is the specification. Query it through the
black-box interface described below, using the product's normal user and
programmatic interfaces, and treat everything it shows you, including screens,
responses, documents and the product's own documentation, as observations of
the required behavior. Then build an independent implementation in
`/app/solution` that behaves the same way. Your implementation is evaluated
later in a fresh environment without access to the reference.

## Rules

### Not allowed

1. **Obtaining an existing implementation.** Do not access the internet. Do not
   obtain the product's source code, binaries or packages by any means, such as
   package managers, caches, container images or other copies. Even if the
   product is familiar to you, reimplement it from observation.
2. **Depending on the reference.** The delivered application must not contact
   the reference or the black-box interface, forward requests, or replay screens,
   responses or files captured from the reference in place of implementing the
   behavior.
3. **Bypassing the black-box interface.** Do not try to access the reference's
   container, filesystem or processes, or verifier tests, answers or data, and do
   not work around the interface's restrictions.

A submission found to break these rules is disqualified and scores zero.

### Allowed

- Any operation the black-box interface accepts, as often as you like, including
  resets and restarts.
- Product data the reference shows you, such as screens, documents and exported files, as observations.
- Everything in your own environment: the installed tools and libraries, your
  own test inputs, and any testing or analysis of your own application.
- Reading the black-box runtime installed at `/opt/blackbox/runtime`. It is the
  code that drives your application during evaluation; the reference is not in
  it.

## Delivery

Work in `/app/solution` and provide an executable `/app/solution/start.sh`. It
must start the application in the foreground and keep running for the
application's lifetime, for example by using `exec` for the final process. Only
`/app/solution` is transferred to the evaluation environment, which is offline
and has the same preinstalled tools as your environment. Put every file the
application needs at runtime inside `/app/solution` and resolve those files
relative to `start.sh`. If `start.sh` is missing or fails to start the
application in that fresh environment, the evaluation has nothing to run.
Implementation language, internal structure and visual design are your
choices.

### Runtime contract

The application is a native desktop application on the X11 display given by
`DISPLAY`, using the D-Bus session and accessibility (AT-SPI) bus supplied in
its environment; do not start another display or desktop session. Its windows
must have English labels and appropriate accessible roles. The application
counts as started when one of its windows is reachable through AT-SPI; this
must happen within 90 seconds. Keep all persistent state under
`DATA_DIR`; the runtime also supplies private `HOME`, `TMPDIR`,
`XDG_CACHE_HOME` and `XDG_CONFIG_HOME` directories. A fresh `DATA_DIR` must
begin in the reference's initial state, and saved settings and documents must
survive a restart of the application with the same `DATA_DIR`. The desktop is
one 1280×900 X11 screen with a single virtual desktop; ordinary application windows open maximized.

Serve the local HTTP interface on `127.0.0.1` at `PORT`. Accept `PBP_API_KEY` as a local API key already approved by the user. The runtime supplies `PBP_INBOX` and `PBP_OUTBOX` as the input and output document directories.

## Evaluation

Evaluation launches your application with the same runtime that drives the
reference, in the reference's place: each episode gets a fresh copy of
`/app/solution` and a fresh `DATA_DIR`, and episodes run one at a time. What
you cannot do or see through `blackbox`, the evaluation cannot do or see either.

## Exploring the reference

The exploration command is `/usr/local/bin/blackbox`, also available as
`blackbox`. Start with:

```sh
blackbox '{"op":"help"}'
```

The help response is the authoritative description of operations, request
fields and limits; requests with unknown fields are rejected. Pass one JSON
request as the argument or on standard input; you can also call the client from
Python through ordinary subprocess calls. Product errors are valid
observations. A broker validation error or a timeout means the request itself
failed; inspect it before retrying. Keep exploration outputs such as
screenshots and downloads outside `/app/solution`, for example under `/tmp`.

`reset` returns the reference to its initial state with a fresh data directory;
`restart` restarts it with the same data; `status` reports whether it is
running and ready.

`blackbox --target self` sends the same request to your own application
instead. On first use it starts the same black-box runtime on `/app/solution`
in your environment, as your user, with private state, logs and socket under
`/tmp/blackbox-self` and a port of its own; later requests reuse it, and
`blackbox --target self --stop` stops it. Help, operations, observations,
limits and validation are identical, and `restart` runs your current
`start.sh` again with the same data while `reset` starts it with a fresh
`DATA_DIR`. Evaluation drives your application through this same runtime, so
use it to check that your application starts, can be operated and shows its
state the way you intend. The runtime is installed at `/opt/blackbox/runtime`.

There is no feature list. Deciding which behaviors to investigate, and in what
order, is part of the task. Explore extensively before and while implementing,
use resets and restarts to separate transient from persistent state, and compare
your implementation with the reference as you build it.

## Time limit

The whole attempt, including exploration, implementation and testing, has a
wall-clock limit of **8 hours (28,800 seconds)**. `/app/solution` is evaluated
as it is when the attempt ends, so keep a working application there from early
on and improve it incrementally.
