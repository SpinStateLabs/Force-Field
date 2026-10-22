#!/usr/bin/env bash
# PostToolUse evidence-hook tests (ADR-0075 part (a)). Run from anywhere:  bash hooks/test/run_post_hook.sh
# field-post.py appends ONE ledger record, rule "E3-policy-executed", when a call the gate answered with "ask"
# (decision ask, rule E3-policy) is followed by a PostToolUse for the same tool_use_id in the same session.
# Evidence only: always exit 0, no stdout, no-op without a manifest. It never records who approved.
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; G="$HERE/../field-gate.py"; P="$HERE/../field-post.py"; PL="$HERE/../field-post.sh"; V="$HERE/../verify-ledger.py"
PY=$(command -v python3 || command -v python)
"$PY" -c 'import yaml' 2>/dev/null || { echo "FAIL  PyYAML missing for $PY"; exit 1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
expect() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi; }
has() { case $2 in *"$3"*) expect "$1" y y ;; *) expect "$1" y n; echo "      output was: $2" ;; esac; }

# project <name> [policy]: a governed project whose E3 match asks (verdict policy)
project() {
  local dir="$T/$1"; mkdir -p "$dir"
  "$PY" - "$HERE/field-manifest.yaml" "$dir/field-manifest.yaml" "${2:-require_human_approval}" <<'PYEOF'
import sys, yaml
src, dst, policy = sys.argv[1:4]
d = yaml.safe_load(open(src))
d["enforcement"]["irreversible_actions"]["deny_patterns_verdict"] = "policy"
d["enforcement"]["irreversible_action_policy"] = policy
yaml.safe_dump(d, open(dst, "w"), sort_keys=False)
PYEOF
  printf %s "$dir"
}
# pre <dir> <session> <tool_use_id> <command> [mode] -> exit code of the gate (the PreToolUse event)
pre() {
  "$PY" -c '
import json,sys
print(json.dumps({"session_id":sys.argv[1],"tool_use_id":sys.argv[2],"tool_name":"Bash","tool_input":{"command":sys.argv[3]},"permission_mode":sys.argv[4]}))' \
    "$2" "$3" "$4" "${5-default}" | CLAUDE_PROJECT_DIR="$1" "$PY" "$G" >/dev/null 2>&1; echo $?
}
# postjson <session> <tool_use_id> [mode|NONE] -> a PostToolUse input with the keys verified on Claude Code 2.1.307
postjson() {
  "$PY" -c '
import json,sys
d={"session_id":sys.argv[1],"transcript_path":"/x/t.jsonl","cwd":"/x","prompt_id":"p1","effort":"high",
   "hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf build"},
   "tool_response":{"stdout":"done","stderr":"","interrupted":False},"tool_use_id":sys.argv[2],"duration_ms":17}
if sys.argv[3]!="NONE": d["permission_mode"]=sys.argv[3]
print(json.dumps(d))' "$1" "$2" "${3-default}"
}
# post <dir> <json> -> "exit|stdout" of field-post.py
post() { local out rc; out=$(printf %s "$2" | CLAUDE_PROJECT_DIR="$1" "$PY" "$P" 2>/dev/null); rc=$?; printf '%s|%s' "$rc" "$out"; }
ledger() { printf %s "$1/.claude/state/field-ledger.jsonl"; }
lines() { if [ -f "$(ledger "$1")" ]; then wc -l < "$(ledger "$1")" | tr -d ' '; else echo 0; fi; }
sha() { if [ -f "$1" ]; then "$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; else echo none; fi; }
executed() { grep -c '"rule": "E3-policy-executed"' "$(ledger "$1")" 2>/dev/null || true; }
field() { tail -n 1 "$(ledger "$1")" | "$PY" -c 'import sys,json;r=json.loads(sys.stdin.read());print(r.get(sys.argv[1]))' "$2"; }
verify() { "$PY" "$V" "$(ledger "$1")" >/dev/null; echo $?; }
BAD='rm -rf build'

# 1. ask, then ran: exactly one event, with the facts the hook may state and the one it may not
D=$(project ran); expect "pre: the ask is emitted (exit 0)" 0 "$(pre "$D" s1 toolu_A "$BAD")"
expect "pre: ledger holds the ask only" "1" "$(lines "$D")"
r=$(post "$D" "$(postjson s1 toolu_A default)")
expect "ask then ran: hook exits 0" 0 "${r%%|*}"; expect "ask then ran: nothing on stdout" "" "${r#*|}"
expect "ask then ran: exactly one event appended" "2" "$(lines "$D")"; expect "ask then ran: one E3-policy-executed" 1 "$(executed "$D")"
expect "event rule" "E3-policy-executed" "$(field "$D" rule)"; expect "event decision" "executed" "$(field "$D" decision)"
expect "event ran" "True" "$(field "$D" ran)"; expect "event tool_use_id" "toolu_A" "$(field "$D" tool_use_id)"
expect "event session" "s1" "$(field "$D" session)"; expect "event permission_mode (from the PostToolUse input)" "default" "$(field "$D" permission_mode)"
expect "event tool (from the ask record)" "Bash" "$(field "$D" tool)"
expect "event states human approval is NOT evidenced" "not_evidenced" "$(field "$D" human_approval)"
expect "event names no approver" "None" "$(field "$D" approver)"
ASKHASH=$(head -n 1 "$(ledger "$D")" | "$PY" -c 'import sys,json;print(json.loads(sys.stdin.read())["hash"])')
expect "event links the ask by hash" "$ASKHASH" "$(field "$D" ask_hash)"
has "default-mode reason says who answered is not recorded" "$(field "$D" reason)" "does not say who answered"
expect "verify-ledger passes with the new event" 0 "$(verify "$D")"
# the event does not copy the tool's output or input
case $(cat "$(ledger "$D")") in *'"stdout"'*|*'"tool_response"'*) expect "no tool_response in the ledger" y n ;; *) expect "no tool_response in the ledger" y y ;; esac

# 2. ask, then declined: no PostToolUse, so nothing is appended; an unrelated post does not match it
D=$(project declined); pre "$D" s1 toolu_B "$BAD" >/dev/null
expect "ask then declined: ledger holds only the ask" "1" "$(lines "$D")"; expect "ask then declined: no executed event" 0 "$(executed "$D")"
B=$(sha "$(ledger "$D")"); r=$(post "$D" "$(postjson s1 toolu_OTHER default)")
expect "post for another id: exit 0" 0 "${r%%|*}"; expect "post for another id: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"

# 3. not an ask: allow, E3 deny, E3-allowed -> nothing appended
D=$(project nonask); pre "$D" s1 toolu_C "ls -la" >/dev/null; pre "$D" s1 toolu_D "echo hi" >/dev/null
B=$(sha "$(ledger "$D")"); r=$(post "$D" "$(postjson s1 toolu_C default)")
expect "plain allow then post: exit 0" 0 "${r%%|*}"; expect "plain allow then post: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
D=$(project forbid forbid); expect "pre: forbid denies" 2 "$(pre "$D" s1 toolu_E "$BAD")"
B=$(sha "$(ledger "$D")"); post "$D" "$(postjson s1 toolu_E default)" >/dev/null; expect "deny then post: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
D=$(project allowl allow_with_ledger); pre "$D" s1 toolu_F "$BAD" >/dev/null
B=$(sha "$(ledger "$D")"); post "$D" "$(postjson s1 toolu_F default)" >/dev/null; expect "E3-allowed then post: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"

# 4. a run under auto is not a human approval, whatever the ask's own mode was
D=$(project auto); pre "$D" s1 toolu_G "$BAD" auto >/dev/null; post "$D" "$(postjson s1 toolu_G auto)" >/dev/null
expect "auto: one event" 1 "$(executed "$D")"; expect "auto: permission_mode recorded" "auto" "$(field "$D" permission_mode)"
expect "auto: mode_is_default false" "False" "$(field "$D" mode_is_default)"; expect "auto: human approval not evidenced" "not_evidenced" "$(field "$D" human_approval)"
has "auto: reason says NOT a human approval" "$(field "$D" reason)" "NOT a human approval"
expect "auto: verify-ledger passes" 0 "$(verify "$D")"
D=$(project default2); pre "$D" s1 toolu_H "$BAD" default >/dev/null; post "$D" "$(postjson s1 toolu_H default)" >/dev/null
expect "default: mode_is_default true" "True" "$(field "$D" mode_is_default)"
case $(field "$D" reason) in *"NOT a human approval"*) expect "default: reason does not use the NOT-a-human marking" y n ;; *) expect "default: reason does not use the NOT-a-human marking" y y ;; esac
for m in acceptEdits dontAsk bypassPermissions bogus; do
  D=$(project "m-$m"); pre "$D" s1 toolu_I "$BAD" default >/dev/null; post "$D" "$(postjson s1 toolu_I "$m")" >/dev/null
  expect "mode $m: recorded, not default" "$m False" "$(field "$D" permission_mode) $(field "$D" mode_is_default)"
  has "mode $m: NOT a human approval" "$(field "$D" reason)" "NOT a human approval"
done
D=$(project nomode); pre "$D" s1 toolu_J "$BAD" default >/dev/null; r=$(post "$D" "$(postjson s1 toolu_J NONE)")
expect "missing mode: event recorded, exit 0" "0 1" "${r%%|*} $(executed "$D")"; expect "missing mode: permission_mode null" "None" "$(field "$D" permission_mode)"
expect "missing mode: mode_is_default false" "False" "$(field "$D" mode_is_default)"; has "missing mode: NOT a human approval" "$(field "$D" reason)" "NOT a human approval"
D=$(project listmode); pre "$D" s1 toolu_K "$BAD" default >/dev/null
post "$D" '{"session_id":"s1","tool_use_id":"toolu_K","permission_mode":["default"]}' >/dev/null
expect "non-string mode: recorded as null, not default" "None False" "$(field "$D" permission_mode) $(field "$D" mode_is_default)"

# 5. malformed or empty stdin, wrong shapes: exit 0, ledger untouched, nothing on stdout
D=$(project bad); pre "$D" s1 toolu_L "$BAD" >/dev/null; B=$(sha "$(ledger "$D")")
for bad in '' 'not json' '[]' 'null' '"x"' '{}' '{"tool_use_id":5}' '{"tool_use_id":""}' '{"tool_use_id":"toolu_L","hook_event_name":"PreToolUse","session_id":"s1"}' '{"tool_use_id":"toolu_L","hook_event_name":"PostToolUseFailure","session_id":"s1"}'; do
  r=$(post "$D" "$bad"); expect "input '$bad': exit 0, no stdout" "0|" "$r"
done
expect "malformed inputs: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
r=$(printf '\377\376\000bad' | CLAUDE_PROJECT_DIR="$D" "$PY" "$P" 2>/dev/null); expect "binary garbage: exit 0" 0 "$?"
expect "binary garbage: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"

# 6. a project with no manifest: no-op, and no state is created
F="$T/free"; mkdir -p "$F"; r=$(post "$F" "$(postjson s1 toolu_A default)")
expect "no manifest: exit 0, no stdout" "0|" "$r"; [ -e "$F/.claude" ] && expect "no manifest: no .claude/ created" y n || expect "no manifest: no .claude/ created" y y
D=$(project nomanifest); pre "$D" s1 toolu_M "$BAD" >/dev/null; rm "$D/field-manifest.yaml"; B=$(sha "$(ledger "$D")")
r=$(post "$D" "$(postjson s1 toolu_M default)"); expect "ledger present but manifest gone: exit 0" 0 "${r%%|*}"; expect "ledger present but manifest gone: unchanged" "$B" "$(sha "$(ledger "$D")")"
D=$(project badmanifest); pre "$D" s1 toolu_N "$BAD" >/dev/null; printf 'enforcement: [unclosed' > "$D/field-manifest.yaml"; B=$(sha "$(ledger "$D")")
r=$(post "$D" "$(postjson s1 toolu_N default)"); expect "unparsable manifest: exit 0 (fail-open, evidence only)" "0|" "$r"; expect "unparsable manifest: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
D=$(project noledger); r=$(post "$D" "$(postjson s1 toolu_A default)"); expect "no ledger yet: exit 0" "0|" "$r"
[ -e "$(ledger "$D")" ] && expect "no ledger yet: none is created" y n || expect "no ledger yet: none is created" y y

# 7. duplicates and look-alikes append once / not at all
D=$(project dup); pre "$D" s1 toolu_O "$BAD" >/dev/null; J=$(postjson s1 toolu_O default)
post "$D" "$J" >/dev/null; post "$D" "$J" >/dev/null; post "$D" "$(postjson s1 toolu_O auto)" >/dev/null
expect "duplicate PostToolUse for the same id: appended once" 1 "$(executed "$D")"; expect "duplicate: ledger is ask + one event" 2 "$(lines "$D")"
expect "duplicate: first record kept (mode default)" "default" "$(field "$D" permission_mode)"; expect "duplicate: verify-ledger passes" 0 "$(verify "$D")"
D=$(project xsess); pre "$D" s1 toolu_P "$BAD" >/dev/null; B=$(sha "$(ledger "$D")")
post "$D" "$(postjson s2 toolu_P default)" >/dev/null; expect "same id, other session: nothing appended" "$B" "$(sha "$(ledger "$D")")"
D=$(project twoasks); pre "$D" s1 toolu_Q1 "$BAD" >/dev/null; pre "$D" s1 toolu_Q2 "$BAD" >/dev/null; pre "$D" s1 toolu_Q3 "$BAD" >/dev/null
post "$D" "$(postjson s1 toolu_Q2 default)" >/dev/null
expect "three asks, the middle one ran: one event, for that id" "1 toolu_Q2" "$(executed "$D") $(field "$D" tool_use_id)"
post "$D" "$(postjson s1 toolu_Q1 default)" >/dev/null; post "$D" "$(postjson s1 toolu_Q3 default)" >/dev/null
expect "the other two ran later: three events in all" 3 "$(executed "$D")"; expect "three events: verify-ledger passes" 0 "$(verify "$D")"
# an id that is a prefix of another is not the same id
D=$(project prefix); pre "$D" s1 toolu_R10 "$BAD" >/dev/null; B=$(sha "$(ledger "$D")")
post "$D" "$(postjson s1 toolu_R1 default)" >/dev/null; expect "id that is a prefix of an ask's id: no match" "$B" "$(sha "$(ledger "$D")")"

# 8. fail-open on an internal error: a ledger whose last line is not a record
D=$(project corrupt); pre "$D" s1 toolu_S "$BAD" >/dev/null; printf 'garbage\n' >> "$(ledger "$D")"; B=$(sha "$(ledger "$D")")
r=$(post "$D" "$(postjson s1 toolu_S default)"); expect "corrupt ledger tail: exit 0, no stdout" "0|" "$r"; expect "corrupt ledger tail: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
# a stdout or stderr that cannot be written is still exit 0
D=$(project closed); pre "$D" s1 toolu_T "$BAD" >/dev/null
postjson s1 toolu_T default | CLAUDE_PROJECT_DIR="$D" "$PY" "$P" >&- 2>&-; expect "closed stdout and stderr: exit 0" 0 "$?"; expect "closed stdout and stderr: event still written" 1 "$(executed "$D")"

# 9. size: a large tool_response is fine; input past the cap is skipped, exit 0
D=$(project big); pre "$D" s1 toolu_U "$BAD" >/dev/null
"$PY" -c '
import json,sys
d=json.loads(sys.argv[1]); d["tool_response"]={"stdout":"x"*(3*1024*1024)}; print(json.dumps(d))' "$(postjson s1 toolu_U default)" > "$T/big.json"
r=$(CLAUDE_PROJECT_DIR="$D" "$PY" "$P" < "$T/big.json" 2>/dev/null); expect "3 MiB PostToolUse input: exit 0, no stdout" "0" "$?$r"; expect "3 MiB PostToolUse input: recorded" 1 "$(executed "$D")"
D=$(project huge); pre "$D" s1 toolu_V "$BAD" >/dev/null; B=$(sha "$(ledger "$D")")
"$PY" -c '
import json,sys
d=json.loads(sys.argv[1]); d["tool_response"]={"stdout":"x"*(9*1024*1024)}; print(json.dumps(d))' "$(postjson s1 toolu_V default)" > "$T/huge.json"
r=$(CLAUDE_PROJECT_DIR="$D" "$PY" "$P" < "$T/huge.json" 2>/dev/null); expect "9 MiB input: exit 0, no stdout" "0" "$?$r"; expect "9 MiB input: skipped, ledger unchanged" "$B" "$(sha "$(ledger "$D")")"

# 10. the gate's lock: a post waits for a held lock, and parallel posts append once
D=$(project lock); pre "$D" s1 toolu_W "$BAD" >/dev/null; B=$(lines "$D")
"$PY" - "$HERE/../field-gate.py" "$D" "$T/held" <<'PYEOF' &
import importlib.util, pathlib, sys, time
spec = importlib.util.spec_from_file_location("g", sys.argv[1]); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
fh = g.gate_lock(pathlib.Path(sys.argv[2])); open(sys.argv[3], "w").close(); time.sleep(2.5)
PYEOF
HOLD=$!; for _ in $(seq 1 50); do [ -e "$T/held" ] && break; sleep 0.1; done
( postjson s1 toolu_W default | CLAUDE_PROJECT_DIR="$D" "$PY" "$P" >/dev/null 2>&1 ) & POSTP=$!
sleep 1; expect "lock held by another process: post has not appended yet" "$B" "$(lines "$D")"
wait $POSTP; wait $HOLD; expect "lock released: post appended once" "$((B + 1))" "$(lines "$D")"
D=$(project par); pre "$D" s1 toolu_X "$BAD" >/dev/null; J=$(postjson s1 toolu_X default)
for _ in 1 2 3 4 5 6; do ( printf %s "$J" | CLAUDE_PROJECT_DIR="$D" "$PY" "$P" >/dev/null 2>&1 ) & done; wait
expect "six parallel posts for one id: one event" 1 "$(executed "$D")"; expect "six parallel posts: verify-ledger passes" 0 "$(verify "$D")"

# 11. a manifest-named ledger store is the ledger the hook reads and appends to
D="$T/store"; mkdir -p "$D"
"$PY" - "$HERE/field-manifest.yaml" "$D/field-manifest.yaml" <<'PYEOF'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
d["enforcement"]["irreversible_actions"]["deny_patterns_verdict"] = "policy"
d["enforcement"]["irreversible_action_policy"] = "require_human_approval"
d.setdefault("ledger", {})["store"] = "audit/field.jsonl"
yaml.safe_dump(d, open(sys.argv[2], "w"), sort_keys=False)
PYEOF
pre "$D" s1 toolu_Y "$BAD" >/dev/null; post "$D" "$(postjson s1 toolu_Y default)" >/dev/null
expect "ledger.store path: ask + event land in it" "2 1" "$(wc -l < "$D/audit/field.jsonl" | tr -d ' ') $(grep -c E3-policy-executed "$D/audit/field.jsonl")"
expect "ledger.store path: verify-ledger passes" 0 "$("$PY" "$V" "$D/audit/field.jsonl" >/dev/null; echo $?)"

# 12. the launcher: always exit 0, no stdout; no Python, a broken Python, or a bad input changes nothing
D=$(project launch); pre "$D" s1 toolu_Z "$BAD" >/dev/null
out=$(postjson s1 toolu_Z default | CLAUDE_PROJECT_DIR="$D" sh "$PL" 2>/dev/null); rc=$?
expect "launcher: exit 0, no stdout" "0|" "$rc|$out"; expect "launcher: event appended" 1 "$(executed "$D")"
out=$(printf 'garbage' | CLAUDE_PROJECT_DIR="$D" sh "$PL" 2>/dev/null); expect "launcher: garbage input exit 0, no stdout" "0|" "$?|$out"
SH=$(command -v sh); NB="$T/nobin"; mkdir -p "$NB"
for u in dirname cat; do printf '#!%s\nexec %s "$@"\n' "$SH" "$(command -v $u)" > "$NB/$u"; chmod +x "$NB/$u"; done
D=$(project launch2); pre "$D" s1 toolu_Z "$BAD" >/dev/null; B=$(sha "$(ledger "$D")")
out=$(postjson s1 toolu_Z default | env -i PATH="$NB" CLAUDE_PROJECT_DIR="$D" "$SH" "$PL" 2>/dev/null); rc=$?
expect "launcher, no Python: exit 0, no stdout" "0|" "$rc|$out"; expect "launcher, no Python: ledger unchanged" "$B" "$(sha "$(ledger "$D")")"
printf '#!%s\necho "Python was not found" >&2; exit 9009\n' "$SH" > "$NB/python3"; chmod +x "$NB/python3"
out=$(postjson s1 toolu_Z default | env -i PATH="$NB" CLAUDE_PROJECT_DIR="$D" "$SH" "$PL" 2>/dev/null); rc=$?
expect "launcher, stub Python (exit 9009): exit 0, no stdout" "0|" "$rc|$out"
printf '#!%s\nprintf %%s "{\\"decision\\":\\"block\\"}"; exit 1\n' "$SH" > "$NB/python3"
out=$(postjson s1 toolu_Z default | env -i PATH="$NB" CLAUDE_PROJECT_DIR="$D" "$SH" "$PL" 2>/dev/null); rc=$?
expect "launcher, Python that prints a decision and exits 1: exit 0, stdout dropped" "0|" "$rc|$out"
# every interpreter fails (the last attempt's status must not become the launcher's)
for n in py python; do printf '#!%s\nexit 9009\n' "$SH" > "$NB/$n"; chmod +x "$NB/$n"; done
printf '#!%s\nexit 9009\n' "$SH" > "$NB/python3"
out=$(postjson s1 toolu_Z default | env -i PATH="$NB" CLAUDE_PROJECT_DIR="$D" "$SH" "$PL" 2>/dev/null); rc=$?
expect "launcher, python3 / py / python all fail (9009): exit 0, no stdout" "0|" "$rc|$out"

# 13. registration: PostToolUse "*" runs the launcher, PreToolUse is unchanged
"$PY" - "$HERE/../hooks.json" <<'PYEOF' && expect "hooks.json registration" ok ok || expect "hooks.json registration" ok bad
import json, sys
h = json.load(open(sys.argv[1]))["hooks"]
assert set(h) == {"PreToolUse", "PostToolUse"}, set(h)
pre, post = h["PreToolUse"], h["PostToolUse"]
assert len(pre) == 1 and pre[0]["matcher"] == "*" and len(pre[0]["hooks"]) == 1
assert pre[0]["hooks"][0]["command"] == 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh"' and pre[0]["hooks"][0]["timeout"] == 10
assert len(post) == 1 and post[0]["matcher"] == "*" and len(post[0]["hooks"]) == 1
assert post[0]["hooks"][0]["type"] == "command" and post[0]["hooks"][0]["timeout"] == 10
assert post[0]["hooks"][0]["command"] == 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-post.sh"'
PYEOF
# the gate is untouched by the post hook: its own ask path still writes the ask record the hook reads
D=$(project gate); pre "$D" s1 toolu_G1 "$BAD" >/dev/null
expect "gate ask record shape the hook relies on" "ask E3-policy toolu_G1 s1" "$(head -n 1 "$(ledger "$D")" | "$PY" -c 'import sys,json;r=json.loads(sys.stdin.read());print(r["decision"],r["rule"],r["tool_use_id"],r["session"])')"

if [ "$fail" = 0 ]; then echo "ALL POST-HOOK TESTS PASSED"; else echo "POST-HOOK TESTS FAILED"; exit 1; fi
