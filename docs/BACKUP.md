# Private backups and recovery

Pai has no network backup client. Use an owner-controlled, access-restricted
location outside the checkout, with a second private copy of the encrypted
files on storage you already control. Save the encryption key separately.
Use a freshly generated, base64-encoded 32-byte random secret as
`PAI_BACKUP_KEY`. Supply it from your local secret store.

```sh
uv run --offline --locked python -m pai.backup backup /private/pai.sqlite /private/new-snapshot.pai
uv run --offline --locked python -m pai.backup erasures /private/pai.sqlite /private/new-erasures.pai
uv run --offline --locked python -m pai.backup restore /private/new-snapshot.pai /private/drill.sqlite --erasures /private/new-erasures.pai --policy /private/policy.json
```

The commands use SQLite's online backup API and streaming AES-256-GCM.
Encrypted files can be copied off-host. Temporary plaintext stays inside
private local directories, so use a trusted host and disk encryption. Choose
a local destination filesystem supporting hard links for atomic publication.
Restore authenticates the input before opening it as SQLite and always
writes a new database. The key never goes into source, CI or logs.

## Erasures and retention

Maintain a current encrypted erasure checkpoint independent of the backup.
Refresh it after any deletion or opt-out and before replacing the last
good copies. Use an erasure checkpoint known to include every acknowledged
deletion since the snapshot. File authentication and ordering do not prove
the operator has the most recent checkpoint. If that state is uncertain,
keep the bot disconnected and use a clean archive. Never use an older
snapshot beyond the period covered by the retained erasure markers.

Restore reapplies current scope, retention and recorded deletions and
opt-outs before publishing the replacement. Rotate and remove superseded
backups under the notice's retention schedule. Active deletion cannot
alter previously copied encrypted files. Keep those files inaccessible
except to the recovery operator and remove affected generations on an
erasure request. No automatic off-host copy, rotation or destruction is
performed.

Test on synthetic data first. Confirm that recent permitted text remains
readable and searchable, deleted texts and opted-out authors stay absent,
and wrong keys or tampering produce no published archive. Keep the original
archive for the user's rollback decision during a drill.
