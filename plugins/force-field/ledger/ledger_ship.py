#!/usr/bin/env python3
"""Reference ledger shipper and verifier for the FIELD Enforcement Gate (reference implementation).

Ships the gate's local sha-256 hash-chained ledger (.claude/state/field-ledger.jsonl) to an
append-only remote store and seals the chain head with an HMAC key the agent does not hold.

  ledger_ship.py ship   --ledger PATH --sink SINK [--key-env FIELD_SEAL_KEY]
  ledger_ship.py verify --sink SINK [--key-env FIELD_SEAL_KEY]

SINK: dir:/path | s3://bucket/prefix | postgres://user@host/db   (see README.md)
Exit codes (same as hooks/verify-ledger.py): 0 intact, 1 tampered / refused, 2 empty or missing.

Chain rule (identical to the gate, hooks/field-gate.py ledger_append):
  hash = sha256(prev_hash + json.dumps(record_without_hash, sort_keys=True)); first prev_hash = 64 zeros.
Seal: hmac_sha256(key, f"{seq}:{head_hash}"), written once per ship run. Sealing is what the local
chain lacks: a ledger re-chained after an edit verifies INTACT locally, but cannot be re-sealed
without the key. Keep the key off the agent's host. Not shipped: key management, rotation.
"""
import argparse
import hashlib
import hmac
import json
import os
import sys

ZERO = "0" * 64


def chain_check(lines, prev=ZERO, start_seq=1):
    """Verify `lines` (raw JSON strings) continue a chain at `prev`. Returns (ok, last_hash, problem)."""
    for i, line in enumerate(lines, start_seq):
        try:
            rec = json.loads(line)
            h = rec.pop("hash")
        except Exception:
            return False, prev, f"record {i}: unreadable"
        if rec.get("prev_hash") != prev:
            return False, prev, f"record {i}: broken link"
        if hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest() != h:
            return False, prev, f"record {i}: hash mismatch"
        prev = h
    return True, prev, None


def seal(key, seq, head):
    return hmac.new(key, f"{seq}:{head}".encode(), hashlib.sha256).hexdigest()


# ---- sinks: append-only; put_record must not overwrite; seals are write-once per seq ----
class DirSink:
    def __init__(self, path):
        self.p = path
        os.makedirs(os.path.join(path, "records"), exist_ok=True)
        os.makedirs(os.path.join(path, "seals"), exist_ok=True)

    def _w(self, rel, text):
        fd = os.open(os.path.join(self.p, rel), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)  # EEXIST = refuse
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)

    def put_record(self, seq, line):
        self._w(f"records/{seq:012d}.json", line)

    def put_seal(self, seq, head, mac):
        self._w(f"seals/{seq:012d}.json", json.dumps({"seq": seq, "head": head, "hmac": mac}))

    def records(self):
        d = os.path.join(self.p, "records")
        return [open(os.path.join(d, n), encoding="utf-8").read() for n in sorted(os.listdir(d))]

    def seals(self):
        d = os.path.join(self.p, "seals")
        return [json.load(open(os.path.join(d, n), encoding="utf-8")) for n in sorted(os.listdir(d))]


class S3Sink:
    """Needs boto3. For tamper resistance enable S3 Object Lock (compliance mode) on the bucket."""
    def __init__(self, url):
        import boto3
        from botocore.exceptions import ClientError
        self._err = ClientError
        rest = url[len("s3://"):]
        self.bucket, _, self.prefix = rest.partition("/")
        self.prefix = self.prefix.strip("/")
        self.c = boto3.client("s3", endpoint_url=os.environ.get("FIELD_S3_ENDPOINT") or None)

    def _k(self, rel):
        return f"{self.prefix}/{rel}" if self.prefix else rel

    def _put(self, rel, text):
        # IfNoneMatch="*": the write fails (412) if the key exists, so records and seals are never overwritten.
        self.c.put_object(Bucket=self.bucket, Key=self._k(rel), Body=text.encode(), IfNoneMatch="*")

    def put_record(self, seq, line):
        self._put(f"records/{seq:012d}.json", line)

    def put_seal(self, seq, head, mac):
        self._put(f"seals/{seq:012d}.json", json.dumps({"seq": seq, "head": head, "hmac": mac}))

    def _list(self, sub):
        keys, tok = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": self._k(sub + "/")}
            if tok:
                kw["ContinuationToken"] = tok
            r = self.c.list_objects_v2(**kw)
            keys += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return sorted(keys)
            tok = r["NextContinuationToken"]

    def _get(self, key):
        return self.c.get_object(Bucket=self.bucket, Key=key)["Body"].read().decode()

    def records(self):
        return [self._get(k) for k in self._list("records")]

    def seals(self):
        return [json.loads(self._get(k)) for k in self._list("seals")]


class PgSink:
    """Needs psycopg2. Apply schema.sql first: it makes both tables append-only (UPDATE/DELETE raise)."""
    def __init__(self, url):
        import psycopg2
        self.db = psycopg2.connect(url)
        self.db.autocommit = True

    def put_record(self, seq, line):
        with self.db.cursor() as c:
            c.execute("INSERT INTO field_ledger(seq, line) VALUES (%s, %s)", (seq, line))

    def put_seal(self, seq, head, mac):
        with self.db.cursor() as c:
            c.execute("INSERT INTO field_ledger_seals(seq, head, hmac) VALUES (%s, %s, %s)", (seq, head, mac))

    def records(self):
        with self.db.cursor() as c:
            c.execute("SELECT line FROM field_ledger ORDER BY seq")
            return [r[0] for r in c.fetchall()]

    def seals(self):
        with self.db.cursor() as c:
            c.execute("SELECT seq, head, hmac FROM field_ledger_seals ORDER BY seq")
            return [{"seq": s, "head": h, "hmac": m} for s, h, m in c.fetchall()]


def open_sink(spec):
    if spec.startswith("dir:"):
        return DirSink(spec[4:])
    if spec.startswith("s3://"):
        return S3Sink(spec)
    if spec.startswith(("postgres://", "postgresql://")):
        return PgSink(spec)
    sys.exit("unknown sink (use dir:, s3:// or postgres://)")


def get_key(env):
    k = os.environ.get(env, "")
    if len(k) < 32:
        sys.exit(f"{env} must hold a seal key of at least 32 characters (kept off the agent's host)")
    return k.encode()


def ship(args):
    key = get_key(args.key_env)
    local = []
    if os.path.exists(args.ledger):
        with open(args.ledger, encoding="utf-8") as fh:
            local = [ln for ln in fh.read().splitlines() if ln.strip()]
    if not local:
        print(f"LEDGER MISSING: {args.ledger}")
        return 2
    ok, head, problem = chain_check(local)
    if not ok:
        print(f"REFUSED: local ledger does not verify ({problem}); nothing shipped")
        return 1
    sink = open_sink(args.sink)
    remote = sink.records()
    n = len(remote)
    if n > len(local) or remote != local[:n]:
        print(f"REFUSED: remote ({n} records) is not a prefix of the local ledger; fork or rollback, nothing shipped")
        return 1
    for seq in range(n + 1, len(local) + 1):
        sink.put_record(seq, local[seq - 1])
    if len(local) > n:
        sink.put_seal(len(local), head, seal(key, len(local), head))
    print(f"SHIPPED {len(local) - n} new record(s); remote now {len(local)}; head {head[:12]}")
    return 0


def verify(args):
    key = get_key(args.key_env)
    sink = open_sink(args.sink)
    recs, seals = sink.records(), sink.seals()
    if not recs:
        print("LEDGER MISSING: remote holds no records")
        return 2
    ok, head, problem = chain_check(recs)
    bad = [] if ok else [problem]
    heads = {}
    prev = ZERO
    for i, ln in enumerate(recs, 1):  # head hash after each seq, for seal checks
        try:
            prev = json.loads(ln)["hash"]
        except Exception:
            break
        heads[i] = prev
    for s in seals:
        if not hmac.compare_digest(s.get("hmac", ""), seal(key, s["seq"], s["head"])):
            bad.append(f"seal at {s['seq']}: bad HMAC")
        elif heads.get(s["seq"]) != s["head"]:
            bad.append(f"seal at {s['seq']}: head does not match record")
    if not seals or seals[-1]["seq"] != len(recs):
        bad.append("records after the last seal (unsealed tail) or no seal")
    for b in bad:
        print(b)
    print(f"{'REMOTE LEDGER INTACT AND SEALED' if not bad else 'REMOTE LEDGER TAMPERED OR UNSEALED'} "
          f"({len(recs)} records, {len(seals)} seals)")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ship", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--sink", required=True)
        p.add_argument("--key-env", default="FIELD_SEAL_KEY")
        if name == "ship":
            p.add_argument("--ledger", required=True)
    a = ap.parse_args()
    sys.exit(ship(a) if a.cmd == "ship" else verify(a))


if __name__ == "__main__":
    main()
