"""Tests for approval_gate.py: tracking, expiry, replay, wrong user, changed details."""

import threading
import unittest

from approval_gate import APPROVAL_TTL_SECONDS, ApprovalGate, ApprovalStatus, action_fingerprint

OWNER = 111
OTHER = 222
ACTION = {"kind": "click", "site": "shop.example", "url": "https://shop.example/cart", "target_label": "Place order"}


class FakeClock:
    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.gate = ApprovalGate(clock=self.clock)

    def test_request_contains_required_fields(self):
        req = self.gate.create(OWNER, ACTION)
        self.assertTrue(req.request_id)
        self.assertEqual(req.user_id, OWNER)
        self.assertEqual(req.action, ACTION)
        self.assertEqual(req.action_hash, action_fingerprint(ACTION))
        self.assertEqual(req.created_at, self.clock.now)
        self.assertEqual(req.expires_at, self.clock.now + 30 * 60)
        self.assertEqual(req.status, ApprovalStatus.PENDING)
        self.assertFalse(req.used)
        self.assertFalse(req.executed)

    def test_default_ttl_is_thirty_minutes(self):
        self.assertEqual(APPROVAL_TTL_SECONDS, 1800)

    def test_request_ids_are_unique(self):
        ids = {self.gate.create(OWNER, ACTION).request_id for _ in range(200)}
        self.assertEqual(len(ids), 200)

    def test_action_is_copied_not_referenced(self):
        action = dict(ACTION)
        req = self.gate.create(OWNER, action)
        action["target_label"] = "Something else"
        self.assertEqual(req.action["target_label"], "Place order")

    def test_approve_then_execute_once(self):
        req = self.gate.create(OWNER, ACTION)
        self.assertEqual(self.gate.decide(req.request_id, OWNER, True), (True, "approved"))
        ok, _ = self.gate.authorize_execution(req.request_id, dict(ACTION))
        self.assertTrue(ok)
        ok, reason = self.gate.authorize_execution(req.request_id, dict(ACTION))
        self.assertFalse(ok)
        self.assertIn("already used", reason)

    def test_replay_of_decision_is_rejected(self):
        req = self.gate.create(OWNER, ACTION)
        self.assertTrue(self.gate.decide(req.request_id, OWNER, True)[0])
        accepted, reason = self.gate.decide(req.request_id, OWNER, True)
        self.assertFalse(accepted)
        self.assertIn("already approved", reason)
        # A replayed reject cannot flip an approval either.
        self.assertFalse(self.gate.decide(req.request_id, OWNER, False)[0])
        self.assertEqual(self.gate.get(req.request_id).status, ApprovalStatus.APPROVED)

    def test_wrong_user_cannot_decide(self):
        req = self.gate.create(OWNER, ACTION)
        accepted, reason = self.gate.decide(req.request_id, OTHER, True)
        self.assertFalse(accepted)
        self.assertIn("different user", reason)
        # The real owner can still decide afterwards.
        self.assertEqual(self.gate.get(req.request_id).status, ApprovalStatus.PENDING)
        self.assertTrue(self.gate.decide(req.request_id, OWNER, True)[0])

    def test_unknown_request_is_rejected(self):
        self.assertFalse(self.gate.decide("does-not-exist", OWNER, True)[0])
        self.assertFalse(self.gate.authorize_execution("does-not-exist", ACTION)[0])

    def test_changed_action_details_are_cancelled(self):
        req = self.gate.create(OWNER, ACTION)
        self.gate.decide(req.request_id, OWNER, True)
        changed = dict(ACTION, target_label="Buy 10 more")
        ok, reason = self.gate.authorize_execution(req.request_id, changed)
        self.assertFalse(ok)
        self.assertIn("changed", reason)
        # And the original can no longer be run after a mismatch.
        self.assertFalse(self.gate.authorize_execution(req.request_id, dict(ACTION))[0])

    def test_rejected_action_cannot_execute(self):
        req = self.gate.create(OWNER, ACTION)
        self.gate.decide(req.request_id, OWNER, False)
        self.assertFalse(self.gate.authorize_execution(req.request_id, dict(ACTION))[0])

    def test_expired_request_cannot_be_approved(self):
        req = self.gate.create(OWNER, ACTION)
        self.clock.advance(30 * 60)
        accepted, reason = self.gate.decide(req.request_id, OWNER, True)
        self.assertFalse(accepted)
        self.assertIn("expired", reason)
        self.assertEqual(self.gate.get(req.request_id).status, ApprovalStatus.EXPIRED)
        self.assertFalse(self.gate.authorize_execution(req.request_id, dict(ACTION))[0])

    def test_request_is_still_valid_just_before_expiry(self):
        req = self.gate.create(OWNER, ACTION)
        self.clock.advance(30 * 60 - 1)
        self.assertTrue(self.gate.decide(req.request_id, OWNER, True)[0])

    def test_wait_returns_expired_after_timeout(self):
        req = self.gate.create(OWNER, ACTION)
        self.clock.advance(31 * 60)
        self.assertEqual(self.gate.wait(req.request_id, poll_seconds=0.01), ApprovalStatus.EXPIRED)

    def test_wait_times_out_with_real_clock(self):
        gate = ApprovalGate(ttl_seconds=0.05)
        req = gate.create(OWNER, ACTION)
        self.assertEqual(gate.wait(req.request_id, poll_seconds=0.01), ApprovalStatus.EXPIRED)
        self.assertFalse(gate.decide(req.request_id, OWNER, True)[0])

    def test_wait_wakes_up_on_decision(self):
        gate = ApprovalGate(ttl_seconds=5)
        req = gate.create(OWNER, ACTION)
        threading.Timer(0.05, lambda: gate.decide(req.request_id, OWNER, True)).start()
        self.assertEqual(gate.wait(req.request_id, poll_seconds=1), ApprovalStatus.APPROVED)

    def test_wait_cancels_when_aborted(self):
        req = self.gate.create(OWNER, ACTION)
        status = self.gate.wait(req.request_id, should_abort=lambda: True, poll_seconds=0.01)
        self.assertEqual(status, ApprovalStatus.CANCELLED)
        self.assertFalse(self.gate.decide(req.request_id, OWNER, True)[0])

    def test_expire_stale_sweeps_only_old_pending_requests(self):
        old = self.gate.create(OWNER, ACTION)
        self.clock.advance(20 * 60)
        fresh = self.gate.create(OWNER, ACTION)
        self.clock.advance(15 * 60)
        expired = self.gate.expire_stale()
        self.assertEqual([r.request_id for r in expired], [old.request_id])
        self.assertEqual(self.gate.get(fresh.request_id).status, ApprovalStatus.PENDING)

    def test_create_requires_user(self):
        with self.assertRaises(ValueError):
            self.gate.create(None, ACTION)


if __name__ == "__main__":
    unittest.main()
