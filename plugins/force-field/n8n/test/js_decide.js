// Test helper: reads {manifest, inputs: [...], state?} on stdin, runs decide() over the inputs in order and
// prints {decisions: [...], ledger: [JSONL lines as pyJson wrote them]}.
"use strict";
const core = require("../field-gate-core.js");
let raw = "";
process.stdin.on("data", (d) => (raw += d)).on("end", () => {
  const req = JSON.parse(raw);
  const state = req.state || { killed: false, counts: {}, lastHash: "0".repeat(64), ledger: [] };
  let t = Date.parse("2026-11-06T12:00:00Z");
  const decisions = [];
  for (const step of req.inputs) {
    if (step.operate) decisions.push(core.operate(state, step.operate, (t += 1000)));
    else decisions.push(core.decide(req.manifest, step, state, (t += 1000)));
  }
  process.stdout.write(JSON.stringify({ decisions, ledger: state.ledger.map((r) => core.pyJson(r)) }));
});
