-- Append-only Postgres store for ledger_ship.py. Run as the schema owner; give the shipper role
-- INSERT and SELECT only (no UPDATE/DELETE/TRUNCATE). The triggers below also block UPDATE/DELETE for the owner.
CREATE TABLE IF NOT EXISTS field_ledger (
  seq  bigint PRIMARY KEY CHECK (seq > 0),
  line text   NOT NULL            -- raw JSON line, byte-exact, so the hash can be recomputed
);
CREATE TABLE IF NOT EXISTS field_ledger_seals (
  seq  bigint PRIMARY KEY CHECK (seq > 0),
  head text   NOT NULL,
  hmac text   NOT NULL
);
CREATE OR REPLACE FUNCTION field_ledger_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'field ledger tables are append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS field_ledger_ro ON field_ledger;
CREATE TRIGGER field_ledger_ro BEFORE UPDATE OR DELETE ON field_ledger
  FOR EACH ROW EXECUTE FUNCTION field_ledger_append_only();
DROP TRIGGER IF EXISTS field_ledger_seals_ro ON field_ledger_seals;
CREATE TRIGGER field_ledger_seals_ro BEFORE UPDATE OR DELETE ON field_ledger_seals
  FOR EACH ROW EXECUTE FUNCTION field_ledger_append_only();
