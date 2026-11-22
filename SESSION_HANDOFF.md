# Pai Windows handoff

See [STATUS.md](STATUS.md) for the latest verified revision and outstanding checks. The Windows runtime uses the existing operator-provisioned test policy, the Groq Free route and SQLite with FTS5. The private working directory contains the configuration, live archive and encrypted backups.

For a single-instance Windows rollout:

1. Verify the target Git revision, locked install and doctor check. Keep the previous installed version available.
2. Stop the existing Pai connector if it is running. Confirm its process tree has exited before proceeding.
3. Create a fresh encrypted backup with the operator's existing backup key. Keep the existing policy, environment file, database and previous snapshots in place.
4. Start one bot with the private runtime paths, then confirm the Gateway ready signal and verify behavior in the authorized Discord test scope. If startup fails, stop the new process before restoring the previous release.

Use the tracked code-only bundle described in [docs/HOSTING.md](docs/HOSTING.md) for future authorized deployments. A legacy locally staged archive can contain private configuration and SQLite data. Keep it local. Enzonic provisioning and any production launch are separate from Windows test rollouts.
