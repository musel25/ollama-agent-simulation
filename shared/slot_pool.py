"""
SlotPool — file-backed (pe, subinterface, ce) slot reservations per tier.

Inventory file format (JSONL, one row per tier):
{"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [
    {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
     "agreementId": null, "expiresAt": null}
]}

All reads/writes hold fcntl.LOCK_EX. Expired slots (expiresAt < now) are
reclaimed on every read so list-and-write becomes consistent.
"""
from __future__ import annotations

import fcntl
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Slot:
    pe: str
    subinterface: str
    ce: str


class SlotPool:
    def __init__(self, inventory_path: Path | str):
        self.path = Path(inventory_path)

    def available_count(self, tier: str) -> int:
        rows = self._read_and_reclaim()
        for row in rows:
            if row["tier"] == tier:
                return sum(1 for s in row["slots"] if s["agreementId"] is None)
        return 0

    def reserve(self, tier: str, agreement_id: int, duration_seconds: int) -> Optional[Slot]:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            for row in rows:
                if row["tier"] != tier:
                    continue
                for s in row["slots"]:
                    if s["agreementId"] is None:
                        s["agreementId"] = agreement_id
                        s["expiresAt"] = time.time() + duration_seconds
                        self._write_locked(f, rows)
                        return Slot(pe=s["pe"], subinterface=s["subinterface"], ce=s["ce"])
                return None
            return None

    def release(self, agreement_id: int) -> None:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            for row in rows:
                for s in row["slots"]:
                    if s["agreementId"] == agreement_id:
                        s["agreementId"] = None
                        s["expiresAt"] = None
            self._write_locked(f, rows)

    def lookup(self, agreement_id: int) -> Optional[Slot]:
        rows = self._read_and_reclaim()
        for row in rows:
            for s in row["slots"]:
                if s["agreementId"] == agreement_id:
                    return Slot(pe=s["pe"], subinterface=s["subinterface"], ce=s["ce"])
        return None

    def tiers(self) -> list[dict]:
        """Return list of {tier, mbps, durationSeconds, availableSlots} for catalog use."""
        rows = self._read_and_reclaim()
        return [
            {
                "tier": r["tier"],
                "mbps": r["mbps"],
                "durationSeconds": r["durationSeconds"],
                "availableSlots": sum(1 for s in r["slots"] if s["agreementId"] is None),
            }
            for r in rows
        ]

    def expired_agreement_ids(self) -> list[int]:
        """Return agreementIds of slots whose expiresAt has passed but slot still bound."""
        now = time.time()
        expired = []
        try:
            with open(self.path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    for s in row.get("slots", []):
                        aid = s.get("agreementId")
                        ea = s.get("expiresAt")
                        if aid is not None and ea is not None and ea < now:
                            expired.append(int(aid))
        except FileNotFoundError:
            pass
        return expired

    def _open_locked(self):
        f = open(self.path, "r+")
        fcntl.flock(f, fcntl.LOCK_EX)
        return _LockedFile(f)

    def _read_and_reclaim(self) -> list[dict]:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            self._write_locked(f, rows)
            return rows

    def _read_and_reclaim_locked(self, f) -> list[dict]:
        f.handle.seek(0)
        now = time.time()
        rows: list[dict] = []
        for line in f.handle.read().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for s in row.get("slots", []):
                if s.get("expiresAt") is not None and s["expiresAt"] < now:
                    s["agreementId"] = None
                    s["expiresAt"] = None
            rows.append(row)
        return rows

    def _write_locked(self, f, rows: list[dict]) -> None:
        f.handle.seek(0)
        f.handle.truncate()
        for row in rows:
            f.handle.write(json.dumps(row) + "\n")


class _LockedFile:
    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            self.handle.close()
        return False
