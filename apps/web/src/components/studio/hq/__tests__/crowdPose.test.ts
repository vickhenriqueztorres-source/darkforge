import assert from "node:assert/strict";
import { figurePose, hashPhase, targetLocationForStatus } from "../crowdPose";

export function runCrowdPoseTests(): number {
  let passed = 0;

  // 1. Status -> location mapping
  assert.equal(targetLocationForStatus("disabled", true), "hidden");
  assert.equal(targetLocationForStatus("working", false), "hidden");
  assert.equal(targetLocationForStatus("waiting_approval", true), "meeting");
  assert.equal(targetLocationForStatus("needs_review", true), "meeting");
  assert.equal(targetLocationForStatus("waiting_input", true), "meeting");
  assert.equal(targetLocationForStatus("working", true), "desk");
  assert.equal(targetLocationForStatus("idle", true), "desk");
  assert.equal(targetLocationForStatus("failed", true), "desk");
  passed++;

  // 2. Distinct poses for every status & reducedMotion freezes oscillation
  const pDisabled = figurePose("disabled", false, 1.2, 0.5, false);
  assert.equal(pDisabled.visible, false);

  const pWorkA = figurePose("working", true, 0.1, 0, false);
  const pWorkB = figurePose("working", true, 0.2, 0, false);
  assert.equal(pWorkA.visible, true);
  assert.equal(pWorkA.seated, true);
  assert.notEqual(pWorkA.typingPulse, pWorkB.typingPulse);
  const pWorkReduced = figurePose("working", true, 0.1, 0, true);
  assert.equal(pWorkReduced.typingPulse, 0);

  const pWait = figurePose("waiting_approval", true, 0.5, 0, false);
  assert.equal(pWait.seated, false);

  const pQueued = figurePose("queued", true, 0.5, 0, false);
  assert.ok(pQueued.headYaw > 0.3, "queued figure looks toward door");

  const pFailed = figurePose("failed", true, 0.5, 0, false);
  assert.ok(pFailed.headTiltX > 0.3, "failed figure drops head");

  const pDoneMid = figurePose("done", true, 1.0, 0, false, 0.35);
  assert.ok(pDoneMid.yOffset > 0.14 && pDoneMid.yOffset <= 0.151);
  const pDoneSettled = figurePose("done", true, 1.0, 0, false, 1.2);
  assert.equal(pDoneSettled.yOffset, 0);
  passed++;

  // 3. Different agents get different deterministic phases
  const ph1 = hashPhase("ch-1dados");
  const ph2 = hashPhase("ch-1roteiro");
  assert.equal(ph1, hashPhase("ch-1dados"));
  assert.notEqual(ph1, ph2);
  passed++;

  return passed;
}
