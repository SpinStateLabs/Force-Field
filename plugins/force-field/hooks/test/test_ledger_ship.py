"""Tests for ledger/ledger_ship.py. Dir sink always; S3 (moto) and Postgres run when their libraries /
FIELD_TEST_PG_URL are present. Ledgers are written by the gate's own ledger_append (real format)."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


gate = load("field_gate", ROOT / "hooks" / "field-gate.py")
ship_mod = load("ledger_ship", ROOT / "ledger" / "ledger_ship.py")
KEY = "k" * 40


def make_ledger(path, n, start=0):
    for i in range(start, start + n):
        gate.ledger_append(path, {"ts": f"t{i}", "event": "allow", "tool": "Bash", "n": i})


def run(*a, key=KEY):
    env = dict(os.environ, FIELD_SEAL_KEY=key)
    return subprocess.run([sys.executable, str(ROOT / "ledger" / "ledger_ship.py"), *a],
                          capture_output=True, text=True, env=env)


class Common:
    """Behaviour every sink must have. Subclasses set self.sink (spec) and tamper(seq, text)."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.ledger = self.tmp / "ledger.jsonl"
        make_ledger(self.ledger, 5)

    def ship(self):
        return run("ship", "--ledger", str(self.ledger), "--sink", self.sink)

    def verify(self, key=KEY):
        return run("verify", "--sink", self.sink, key=key)

    def test_ship_verify_incremental_and_idempotent(self):
        r = self.ship(); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SHIPPED 5", r.stdout)
        self.assertEqual(self.verify().returncode, 0)
        make_ledger(self.ledger, 3, start=5)
        r = self.ship(); self.assertIn("SHIPPED 3", r.stdout)
        r = self.ship(); self.assertIn("SHIPPED 0", r.stdout)  # nothing new, no extra seal
        r = self.verify(); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("8 records, 2 seals", r.stdout)

    def test_wrong_key_fails(self):
        self.ship()
        r = self.verify(key="z" * 40); self.assertEqual(r.returncode, 1); self.assertIn("bad HMAC", r.stdout)

    def test_refuses_broken_local_chain(self):
        lines = self.ledger.read_text().splitlines()
        lines[2] = lines[2].replace('"n": 2', '"n": 99')
        self.ledger.write_text("\n".join(lines) + "\n")
        r = self.ship(); self.assertEqual(r.returncode, 1); self.assertIn("REFUSED", r.stdout)

    def test_refuses_rechained_local_ledger(self):
        # The case the local chain cannot catch: a ledger re-chained from scratch with a different history.
        self.ship()
        self.ledger.unlink()
        for i in range(5):
            gate.ledger_append(self.ledger, {"ts": f"x{i}", "event": "allow", "tool": "Bash", "n": i})
        self.assertEqual(run("verify", "--sink", self.sink).returncode, 0)  # remote itself still fine
        r = self.ship(); self.assertEqual(r.returncode, 1); self.assertIn("not a prefix", r.stdout)

    def test_unsealed_tail_detected(self):
        self.ship()
        make_ledger(self.ledger, 1, start=5)
        extra = self.ledger.read_text().splitlines()[-1]
        self.put_raw_record(6, extra)  # a record written without a seal
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("unsealed", r.stdout)

    def test_remote_edit_detected(self):
        self.ship()
        self.tamper(3)
        self.assertEqual(self.verify().returncode, 1)

    def test_missing_ledger_is_2(self):
        self.ledger.unlink()
        self.assertEqual(self.ship().returncode, 2)


class DirTests(Common, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.d = self.tmp / "sink"
        self.sink = f"dir:{self.d}"

    def put_raw_record(self, seq, line):
        ship_mod.DirSink(str(self.d)).put_record(seq, line)

    def tamper(self, seq):
        p = self.d / "records" / f"{seq:012d}.json"
        p.write_text(p.read_text().replace('"n": 2', '"n": 77'))

    def test_overwrite_refused(self):
        self.ship()
        with self.assertRaises(FileExistsError):
            ship_mod.DirSink(str(self.d)).put_record(1, "x")


try:
    import boto3, moto  # noqa
    from moto import mock_aws
    HAVE_S3 = True
except Exception:
    HAVE_S3 = False


@unittest.skipUnless(HAVE_S3, "boto3/moto not installed")
class S3Tests(unittest.TestCase):
    """In-process against moto: exercises S3Sink directly (the CLI runs in a subprocess moto cannot patch)."""

    def setUp(self):
        self.m = mock_aws(); self.m.start()
        os.environ.update(AWS_ACCESS_KEY_ID="x", AWS_SECRET_ACCESS_KEY="x", AWS_DEFAULT_REGION="us-east-1")
        boto3.client("s3").create_bucket(Bucket="ledger-test")
        self.tmp = pathlib.Path(tempfile.mkdtemp()); self.ledger = self.tmp / "l.jsonl"
        make_ledger(self.ledger, 4)
        os.environ["FIELD_SEAL_KEY"] = KEY

    def tearDown(self):
        self.m.stop()

    def args(self, **kw):
        import argparse
        return argparse.Namespace(sink="s3://ledger-test/pre", key_env="FIELD_SEAL_KEY", ledger=str(self.ledger), **kw)

    def test_ship_verify_overwrite_and_tamper(self):
        self.assertEqual(ship_mod.ship(self.args()), 0)
        self.assertEqual(ship_mod.verify(self.args()), 0)
        s = ship_mod.S3Sink("s3://ledger-test/pre")
        with self.assertRaises(s._err) as cm:  # IfNoneMatch: existing key is never overwritten
            s.put_record(1, "x")
        self.assertIn("PreconditionFailed", str(cm.exception))
        boto3.client("s3").put_object(Bucket="ledger-test", Key="pre/records/000000000002.json", Body=b"{}")  # out-of-band edit
        self.assertEqual(ship_mod.verify(self.args()), 1)


PG = os.environ.get("FIELD_TEST_PG_URL")


@unittest.skipUnless(PG, "FIELD_TEST_PG_URL not set")
class PgTests(Common, unittest.TestCase):
    def setUp(self):
        import psycopg2
        db = psycopg2.connect(PG); db.autocommit = True
        with db.cursor() as c:
            c.execute("DROP TABLE IF EXISTS field_ledger, field_ledger_seals CASCADE")
            c.execute((ROOT / "ledger" / "schema.sql").read_text())
        self.db = db
        self.sink = PG
        super().setUp()

    def put_raw_record(self, seq, line):
        ship_mod.PgSink(PG).put_record(seq, line)

    def tamper(self, seq):  # owner bypassing the trigger, as an admin with DDL rights could
        with self.db.cursor() as c:
            c.execute("ALTER TABLE field_ledger DISABLE TRIGGER field_ledger_ro")
            c.execute("UPDATE field_ledger SET line = replace(line, '\"n\": 2', '\"n\": 77') WHERE seq = %s", (seq,))
            c.execute("ALTER TABLE field_ledger ENABLE TRIGGER field_ledger_ro")

    def test_update_delete_blocked(self):
        self.ship()
        import psycopg2
        with self.db.cursor() as c:
            with self.assertRaises(psycopg2.Error):
                c.execute("UPDATE field_ledger SET line = 'x' WHERE seq = 1")
            with self.assertRaises(psycopg2.Error):
                c.execute("DELETE FROM field_ledger_seals")


if __name__ == "__main__":
    unittest.main()
