"""
LocalPilot — Human-in-the-Loop approval tracking (SRS Module 3)

Every state-changing action gets an ``ApprovalRequest`` with:
  * a unique, unguessable request ID
  * the authorized Telegram user ID it belongs to
  * a frozen copy of the action details plus a SHA-256 fingerprint of them
  * creation and expiration times (30 minutes, per the SRS)
  * a used/unused flag for the decision and an executed flag for the action

Rules enforced by ``ApprovalGate``:
  * only the user the request was created for can decide it
  * a request can be decided (approved or rejected) exactly once
  * an expired request is cancelled and can no longer be approved
  * an approved action can be executed exactly once, and only if the action
    about to run still matches the fingerprint that was approved
"""

import copy
import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

APPROVAL_TTL_SECONDS = 30 * 60  # SRS: abort if not approved within 30 minutes


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def action_fingerprint(action: Dict[str, Any]) -> str:
    """Stable SHA-256 fingerprint of an action's details."""
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ApprovalRequest:
    request_id: str
    user_id: int
    action: Dict[str, Any]
    action_hash: str
    created_at: float
    expires_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING
    used: bool = False        # True once Approve/Reject has been accepted
    executed: bool = False    # True once the approved action has been run
    _decided: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class ApprovalGate:
    """Thread-safe in-memory store of approval requests."""

    def __init__(self, ttl_seconds: float = APPROVAL_TTL_SECONDS, clock: Callable[[], float] = time.time):
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._requests: Dict[str, ApprovalRequest] = {}

    # ------------------------------------------------------------------ #
    def create(self, user_id: int, action: Dict[str, Any]) -> ApprovalRequest:
        """Registers a new pending request for ``user_id``."""
        if user_id is None:
            raise ValueError("An approval request must belong to a Telegram user.")
        frozen = copy.deepcopy(action)
        now = self._clock()
        with self._lock:
            request_id = secrets.token_urlsafe(12)
            while request_id in self._requests:
                request_id = secrets.token_urlsafe(12)
            req = ApprovalRequest(
                request_id=request_id,
                user_id=int(user_id),
                action=frozen,
                action_hash=action_fingerprint(frozen),
                created_at=now,
                expires_at=now + self.ttl_seconds,
            )
            self._requests[request_id] = req
        return req

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            return self._requests.get(request_id)

    # ------------------------------------------------------------------ #
    def _expire_locked(self, req: ApprovalRequest) -> None:
        req.status = ApprovalStatus.EXPIRED
        req.used = True
        req._decided.set()

    def decide(self, request_id: str, user_id: int, approve: bool) -> Tuple[bool, str]:
        """
        Records an Approve/Reject press. Returns (accepted, reason).
        A rejected attempt (wrong user, replay, expired) never changes an approved request.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                return False, "Unknown or already removed approval request."
            if user_id is None or int(user_id) != req.user_id:
                return False, "This approval request belongs to a different user."
            if req.used:
                return False, f"This approval request was already {req.status.value}."
            if req.is_expired(self._clock()):
                self._expire_locked(req)
                return False, "This approval request expired. The action was cancelled."
            req.used = True
            req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
            req._decided.set()
            return True, req.status.value

    def cancel(self, request_id: str) -> bool:
        """Cancels a pending request (e.g. the user pressed Stop)."""
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != ApprovalStatus.PENDING:
                return False
            req.status = ApprovalStatus.CANCELLED
            req.used = True
            req._decided.set()
            return True

    def expire_if_pending(self, request_id: str) -> bool:
        """Marks a request expired if it is still pending past its deadline."""
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.status != ApprovalStatus.PENDING:
                return False
            if not req.is_expired(self._clock()):
                return False
            self._expire_locked(req)
            return True

    def expire_stale(self) -> List[ApprovalRequest]:
        """Expires every pending request past its deadline; returns those requests."""
        expired = []
        with self._lock:
            now = self._clock()
            for req in self._requests.values():
                if req.status == ApprovalStatus.PENDING and req.is_expired(now):
                    self._expire_locked(req)
                    expired.append(req)
        return expired

    # ------------------------------------------------------------------ #
    def wait(
        self,
        request_id: str,
        should_abort: Optional[Callable[[], bool]] = None,
        poll_seconds: float = 1.0,
    ) -> ApprovalStatus:
        """
        Blocks (in a worker thread) until the request is decided, expires, or
        ``should_abort()`` returns True. Expiry and abort both cancel the action.
        """
        req = self.get(request_id)
        if req is None:
            return ApprovalStatus.CANCELLED
        while True:
            with self._lock:
                if req.status != ApprovalStatus.PENDING:
                    return req.status
                remaining = req.expires_at - self._clock()
                if remaining <= 0:
                    self._expire_locked(req)
                    return req.status
            if should_abort and should_abort():
                self.cancel(request_id)
                return self.get(request_id).status
            req._decided.wait(timeout=max(0.0, min(poll_seconds, remaining)))

    def authorize_execution(self, request_id: str, action: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Final check right before a state-changing action runs. Succeeds once per
        approved request, only before expiry, and only for the exact approved action.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                return False, "Unknown approval request."
            if req.status != ApprovalStatus.APPROVED:
                return False, f"Action is not approved (status: {req.status.value})."
            if req.executed:
                return False, "This approval was already used to run the action once."
            if req.is_expired(self._clock()):
                req.status = ApprovalStatus.EXPIRED
                return False, "Approval expired before execution. The action was cancelled."
            if action_fingerprint(action) != req.action_hash:
                req.status = ApprovalStatus.CANCELLED
                return False, "The action changed after approval. It was cancelled."
            req.executed = True
            return True, "authorized"


# Process-wide gate used by the Telegram bot and the browser agent.
GATE = ApprovalGate()
