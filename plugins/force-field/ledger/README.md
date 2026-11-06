# Ledger reference implementation (reference, not a product)

`ledger_ship.py` ships the Enforcement Gate's local hash-chained ledger
(`.claude/state/field-ledger.jsonl`) to an append-only remote store and seals the chain head with an HMAC
key that the governed agent does not hold. It is the "ledger reference implementation" from the ROADMAP,
scoped to what is tested.

```
export FIELD_SEAL_KEY=...                       # at least 32 characters; keep it off the agent's host
python3 ledger/ledger_ship.py ship   --ledger .claude/state/field-ledger.jsonl --sink SINK
python3 ledger/ledger_ship.py verify --sink SINK
```

Sinks: `dir:/path` (for tests and air-gapped use), `s3://bucket/prefix` (needs `boto3`),
`postgres://user@host/db` (needs `psycopg2`; apply `ledger/schema.sql` first). Exit codes match
`hooks/verify-ledger.py`: 0 intact, 1 tampered or refused, 2 missing or empty.

## What it adds over the local chain
- **Remote copy.** Records are written once, never overwritten: file `O_EXCL`, S3 `IfNoneMatch: *`, Postgres primary key
  plus triggers that reject `UPDATE`/`DELETE`.
- **Sealing.** Each ship run writes `HMAC-SHA256(key, "<seq>:<head hash>")`. A ledger re-chained after an edit passes
  `verify-ledger.py` but cannot be re-sealed without the key. `verify` fails on a bad seal, a seal that does not match
  its record, or records after the last seal.
- **Fork refusal.** `ship` refuses if the remote is not a prefix of the local ledger (rollback or re-chain), and refuses
  a local ledger that does not verify.

## Limits (read before relying on it)
- Tamper-evident, not tamper-proof. Whoever holds the key and write access can forge a seal. Records after the last
  seal are reported as unsealed, not trusted.
- Shipping is batch, not per call: records between ship runs exist only locally. Run it from a scheduler held outside the agent.
- The seal key is read from an environment variable. Rotation, KMS/HSM storage and key escrow are not provided.
- S3 tamper resistance needs Object Lock (compliance mode) configured on the bucket; this script does not set it.
- Not enforced by the gate: the gate does not read the remote store; `ledger.store` stays descriptive.

## Tested
`hooks/test/test_ledger_ship.py`: dir sink (stdlib only); S3 against `moto` (needs `boto3`, `moto`); Postgres 16 against a
real local server (needs `psycopg2` and `FIELD_TEST_PG_URL`). Not tested: live AWS S3, other Postgres versions, Windows.
Not in `hooks/test/run_all.sh` or CI.
