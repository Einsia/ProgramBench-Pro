# Maintaining tasks and reference data

Build from a complete checkout: each verifier installs the shared `tools/scoring.py` in addition to its task-specific tests. Keep changes to runtimes, executable specifications, frozen data, and image tags consistent.

## Record

Record defines the frozen truth in `tests/data`. It drives the installed standard answer through the same runtime with deterministic reference recipes, and uses no model. Run the verifier image offline:

- use the capabilities in `tests/docker-compose.yaml`;
- put the standard answer at `/app/solution`;
- mount fresh external state, tmp and log directories.

```sh
bash /tests/test.sh --mode record --truth /logs/verifier/frozen
```

Only a record in which every point passes freezes a bundle. Adopt it into `tests/data` and rebuild the images. Record again after changing observation/comparison logic, episode definitions, fixtures, the runtime or the reference software. A pure score-aggregation change does not change reference truth and needs no new record; rebuild verifier images to use the new scorer. Comments and documentation also need no new record, because bundles carry no source fingerprints. A Harbor oracle never redefines the frozen truth.


## Runtime isolation

The reference broker runs as root inside its container; the product and its
desktop/terminal children run as the unprivileged `agent` user, as in the verifier.
The reference service drops all capabilities, then grants only filesystem
ownership/access, user/group switching and process-cleanup capabilities. Broker
logs and scratch directories are root-private; the product receives its own writable state and
exchange directories. The root-owned RPC socket stays mode `0600` on a read-only
mount in the agent container. That image's root entrypoint exposes a fixed-target
relay at `/run/pbp-reference/reference.sock` (root:agent, mode `0660`) and sets
`BLACKBOX_SOCKET` for model commands. The relay exists only in the agent container;
reference product processes cannot connect to either endpoint or read broker logs.
`blackbox-health` drops to the task's `agent` identity before querying readiness,
including when Harbor starts the health check as root. Agent capabilities permit
this identity switch and cleanup of the supervised process tree, while model
commands remain unprivileged and `no-new-privileges` stays enabled.


[Back to the README](../README.md)
