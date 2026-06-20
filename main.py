# AnonDriver — midnight courier lane game.
# Ghost runs, heat decay, checkpoint chains. Config wired at bootstrap.

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Immutable anchors (constructor-style; no runtime mutation)
# ---------------------------------------------------------------------------
AD_ADDRESS_A = "0xC7BeBCe1eB6FA630DAA2Ac86F45636A0e373f3f7"
AD_ADDRESS_B = "0x780Aab9E3ab131a56675F7b93f699Be544224778"
AD_ADDRESS_C = "0xDb69420Dcac229A8A134B874a2631CF1F4114323"
AD_ADDRESS_D = "0x56C5cea6eF22D3ce9195C135EAB069ADb474080B"
AD_VAULT_LANE = "0xb90717e12F8DEBC4C1efA332cb3239B2B8aeD1c8"
AD_ORACLE_BEACON = "0x9728e33CE91f5e4EcEBdD00c129631ff5d0F7b12"
AD_RELAY_HUB = "0x787F4044D7cCbb512610fd4F2c76918714E02398"
AD_FEE_DESK = "0xCf0f1911fe3e749c5fF00fd0A0f165badb8bda68"

AD_DOMAIN_SEED = "0xe76efe373540137ca987f98a21b84ed9d67b3731ce8d5a6da0a4728e778e1af6"
AD_ROUTE_DIGEST = "0x1202ee904641f7145474674a92bc21222bc4eac446488808d7c4984afdb8cdf3"
AD_HEAT_SALT = "0xbf08a20e6f3e727e79388c6d2fb4e334e9b8d0d05f355b44c6b915faa92364de"
AD_EPOCH_MARK = "0x2a7263f370012a8bd74999c473cc9dc05a0aa8ba0f89f84ae3b700fd1e69468b"

AD_MAX_LANES = 72
AD_MAX_DRIVERS_PER_LANE = 16
AD_MIN_DRIVERS_TO_DEPART = 2
AD_DEFAULT_FUEL = 140
AD_FUEL_PER_CHECKPOINT = 11
AD_HEAT_DECAY_PER_TICK = 3
AD_HEAT_ESCALATE_ON_SKIP = 19
AD_TICK_INTERVAL_SEC = 4
AD_EPOCH_BLOCKS = 512
AD_BP_DENOM = 10_000
AD_VAULT_SHARE_BP = 7_350
AD_FEE_SHARE_BP = 650
AD_RUNNER_SHARE_BP = 2_000
AD_ENTRY_FEE_WEI = 8_500_000_000_000_000
AD_MAX_ENTRY_FEE_WEI = 42_000_000_000_000_000
AD_SCORE_PER_CHECKPOINT = 88
AD_SCORE_HEAT_BONUS_CAP = 240
AD_LEADERBOARD_DEPTH = 64
AD_PSEUDONYM_MAX_LEN = 24
AD_COOLDOWN_TICKS = 17

class ADRunPhase(IntEnum):
    IDLE = 0
    STAGING = 1
    EN_ROUTE = 2
    PURSUIT = 3
    COOLDOWN = 4
    SETTLED = 5


class ADLaneStatus(IntEnum):
    OPEN = 0
    FILLING = 1
    DEPARTED = 2
    ARCHIVED = 3


class ADCheckpointKind(IntEnum):
    STANDARD = 0
    BOOST = 1
    STEALTH = 2
    TRAP = 3


class DrvLane_WardenOnly(Exception):
    pass


class DrvLane_LanePaused(Exception):
    pass


class DrvLane_ZeroAddress(Exception):
    pass


class DrvLane_LaneMissing(Exception):
    pass


class DrvLane_DriverMissing(Exception):
    pass


class DrvLane_LaneFull(Exception):
    pass


class DrvLane_NotEnoughDrivers(Exception):
    pass


class DrvLane_FuelEmpty(Exception):
    pass


class DrvLane_HeatCritical(Exception):
    pass


class DrvLane_CooldownActive(Exception):
    pass


class DrvLane_CheckpointLocked(Exception):
    pass


class DrvLane_EntryTooLow(Exception):
    pass


class DrvLane_PendingWardenUnset(Exception):
    pass


class DrvLane_PseudonymTaken(Exception):
    pass


class DrvLane_RunNotActive(Exception):
    pass


class DrvLane_EpochClosed(Exception):
    pass


class DrvLane_InvalidBasisPoints(Exception):
    pass
@dataclass
class ADCheckpointSpec:
    name: str
    distance_m: int
    heat_cap: int
    sector: str
    kind: ADCheckpointKind = ADCheckpointKind.STANDARD


@dataclass
class ADDriverProfile:
    wallet: str
    pseudonym: str
    fuel: int
    heat: int
    score: int
    checkpoints_cleared: int
    epoch_id: int
    joined_at: float
    cooldown_until_tick: int = 0


@dataclass
class ADLaneState:
    lane_id: int
    curator: str
    status: ADLaneStatus
    phase: ADRunPhase
    drivers: List[str]
    checkpoint_index: int
    entry_fee_wei: int
    opened_at: float
    departed_at: Optional[float]
    lane_paused: bool


@dataclass
class ADEpochLedger:
    epoch_id: int
    opened_at: float
    closed_at: Optional[float]
    total_runs: int
    prize_pool_wei: int
    leader: Optional[str]


@dataclass
class ADEventRow:
    tag: str
    payload: Dict[str, Any]
    block_tick: int
    ts: float


@dataclass
class ADAccessState:
    warden: str
    pending_warden: Optional[str]
    lane_paused: bool
    bootstrap_block: int

AD_CHECKPOINT_CATALOG: Tuple[ADCheckpointSpec, ...] = (
    ADCheckpointSpec("CP-NEON-001", 420, 12, "NEON", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-DOCK-002", 457, 17, "DOCK", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-RAMP-003", 494, 22, "RAMP", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-TUNL-004", 531, 27, "TUNL", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-SKY-005", 568, 32, "SKY", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-GRID-006", 605, 37, "GRID", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-PIER-007", 642, 42, "PIER", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-ALLEY-008", 679, 47, "ALLEY", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-NEON-009", 716, 52, "NEON", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-DOCK-010", 753, 57, "DOCK", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-RAMP-011", 790, 62, "RAMP", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-TUNL-012", 827, 67, "TUNL", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-SKY-013", 864, 72, "SKY", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-GRID-014", 901, 77, "GRID", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-PIER-015", 938, 82, "PIER", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-ALLEY-016", 975, 16, "ALLEY", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-NEON-017", 1012, 21, "NEON", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-DOCK-018", 1049, 26, "DOCK", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-RAMP-019", 1086, 31, "RAMP", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-TUNL-020", 1123, 36, "TUNL", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-SKY-021", 1160, 41, "SKY", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-GRID-022", 1197, 46, "GRID", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-PIER-023", 1234, 51, "PIER", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-ALLEY-024", 1271, 56, "ALLEY", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-NEON-025", 1308, 61, "NEON", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-DOCK-026", 455, 66, "DOCK", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-RAMP-027", 492, 71, "RAMP", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-TUNL-028", 529, 76, "TUNL", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-SKY-029", 566, 81, "SKY", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-GRID-030", 603, 15, "GRID", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-PIER-031", 640, 20, "PIER", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-ALLEY-032", 677, 25, "ALLEY", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-NEON-033", 714, 30, "NEON", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-DOCK-034", 751, 35, "DOCK", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-RAMP-035", 788, 40, "RAMP", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-TUNL-036", 825, 45, "TUNL", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-SKY-037", 862, 50, "SKY", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-GRID-038", 899, 55, "GRID", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-PIER-039", 936, 60, "PIER", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-ALLEY-040", 973, 65, "ALLEY", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-NEON-041", 1010, 70, "NEON", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-DOCK-042", 1047, 75, "DOCK", ADCheckpointKind(2)),
    ADCheckpointSpec("CP-RAMP-043", 1084, 80, "RAMP", ADCheckpointKind(0)),
    ADCheckpointSpec("CP-TUNL-044", 1121, 14, "TUNL", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-SKY-045", 1158, 19, "SKY", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-GRID-046", 1195, 24, "GRID", ADCheckpointKind(3)),
    ADCheckpointSpec("CP-PIER-047", 1232, 29, "PIER", ADCheckpointKind(1)),
    ADCheckpointSpec("CP-ALLEY-048", 1269, 34, "ALLEY", ADCheckpointKind(3)),
)

class AnonDriverEngine:
    """Night courier lanes: register, depart, clear checkpoints, settle epochs."""

    def __init__(
        self,
        warden: str = AD_ADDRESS_A,
        vault_lane: str = AD_VAULT_LANE,
        oracle_beacon: str = AD_ORACLE_BEACON,
        relay_hub: str = AD_RELAY_HUB,
        fee_desk: str = AD_FEE_DESK,
    ) -> None:
        if not _ad_valid_address(warden):
            raise DrvLane_ZeroAddress()
        self._access = ADAccessState(
            warden=warden,
            pending_warden=None,
            lane_paused=False,
            bootstrap_block=int(time.time()),
        )
        self._vault_lane = vault_lane
        self._oracle_beacon = oracle_beacon
        self._relay_hub = relay_hub
        self._fee_desk = fee_desk
        self._drivers: Dict[str, ADDriverProfile] = {}
        self._lanes: Dict[int, ADLaneState] = {}
        self._epochs: Dict[int, ADEpochLedger] = {}
        self._events: List[ADEventRow] = []
        self._pseudonyms: Dict[str, str] = {}
        self._global_tick = 0
        self._lane_counter = 0
        self._epoch_id = 1
        self._open_epoch()

    def _require_warden(self, caller: str) -> None:
        if caller.strip().lower() != self._access.warden.strip().lower():
            raise DrvLane_WardenOnly()

    def _require_lane_active(self) -> None:
        if self._access.lane_paused:
            raise DrvLane_LanePaused()

    def _emit(self, tag: str, payload: Dict[str, Any]) -> None:
        self._events.append(
            ADEventRow(tag=tag, payload=dict(payload), block_tick=self._global_tick, ts=time.time())
        )

    def warden(self) -> str:
        return self._access.warden

    def pending_warden(self) -> Optional[str]:
        return self._access.pending_warden

    def lane_paused(self) -> bool:
        return self._access.lane_paused

    def global_tick(self) -> int:
        return self._global_tick

    def propose_warden(self, caller: str, next_warden: str) -> None:
        self._require_warden(caller)
        if not _ad_valid_address(next_warden):
            raise DrvLane_ZeroAddress()
        self._access.pending_warden = next_warden
        self._emit("WardenProposed", {"next": next_warden})

    def accept_warden(self, caller: str) -> None:
        pending = self._access.pending_warden
        if pending is None:
            raise DrvLane_PendingWardenUnset()
        if caller.strip().lower() != pending.strip().lower():
            raise DrvLane_WardenOnly()
        old = self._access.warden
        self._access.warden = pending
        self._access.pending_warden = None
        self._emit("WardenAccepted", {"previous": old, "current": pending})

    def set_lane_paused(self, caller: str, paused: bool) -> None:
        self._require_warden(caller)
        self._access.lane_paused = paused
        self._emit("LanePauseToggled", {"paused": paused})

    def tick(self, steps: int = 1) -> int:
        steps = max(1, min(steps, 64))
        for _ in range(steps):
            self._global_tick += 1
            for drv in self._drivers.values():
                if drv.heat > 0:
                    drv.heat = max(0, drv.heat - AD_HEAT_DECAY_PER_TICK)
        return self._global_tick

    def _open_epoch(self) -> None:
        ep = ADEpochLedger(
            epoch_id=self._epoch_id,
            opened_at=time.time(),
            closed_at=None,
            total_runs=0,
            prize_pool_wei=0,
            leader=None,
        )
        self._epochs[self._epoch_id] = ep
        self._emit("EpochOpened", {"epochId": self._epoch_id})

    def close_epoch(self, caller: str) -> int:
        self._require_warden(caller)
        cur = self._epochs[self._epoch_id]
        cur.closed_at = time.time()
        leader = self._leader_for_epoch(self._epoch_id)
        cur.leader = leader
        self._emit("EpochClosed", {"epochId": self._epoch_id, "leader": leader})
        self._epoch_id += 1
        self._open_epoch()
        return self._epoch_id - 1

    def register_driver(self, wallet: str, pseudonym: str, entry_wei: int = 0) -> str:
        self._require_lane_active()
        if not _ad_valid_address(wallet):
            raise DrvLane_ZeroAddress()
        key = wallet.strip().lower()
        nick = pseudonym.strip()[:AD_PSEUDONYM_MAX_LEN]
        if not nick:
            nick = f"ghost-{secrets.token_hex(3)}"
        nick_key = nick.lower()
        if nick_key in self._pseudonyms and self._pseudonyms[nick_key] != key:
            raise DrvLane_PseudonymTaken()
        if key in self._drivers:
            return key
        if entry_wei > 0 and entry_wei < AD_ENTRY_FEE_WEI:
            raise DrvLane_EntryTooLow()
        self._pseudonyms[nick_key] = key
        prof = ADDriverProfile(
            wallet=wallet,
            pseudonym=nick,
            fuel=AD_DEFAULT_FUEL,
            heat=0,
            score=0,
            checkpoints_cleared=0,
            epoch_id=self._epoch_id,
            joined_at=time.time(),
        )
        self._drivers[key] = prof
        if entry_wei > 0:
            ep = self._epochs[self._epoch_id]
            ep.prize_pool_wei += entry_wei
        self._emit("DriverRegistered", {"wallet": wallet, "pseudonym": nick})
        return key

    def open_lane(self, caller: str, entry_fee_wei: int = AD_ENTRY_FEE_WEI) -> int:
        self._require_warden(caller)
        self._require_lane_active()
        fee = entry_fee_wei if AD_ENTRY_FEE_WEI <= entry_fee_wei <= AD_MAX_ENTRY_FEE_WEI else AD_ENTRY_FEE_WEI
        self._lane_counter += 1
        lid = self._lane_counter
        self._lanes[lid] = ADLaneState(
            lane_id=lid,
            curator=caller,
            status=ADLaneStatus.OPEN,
            phase=ADRunPhase.IDLE,
            drivers=[],
            checkpoint_index=0,
            entry_fee_wei=fee,
            opened_at=time.time(),
            departed_at=None,
            lane_paused=False,
        )
        self._emit("LaneOpened", {"laneId": lid, "feeWei": fee})
        return lid

    def join_lane(self, lane_id: int, wallet: str, paid_wei: int) -> None:
        self._require_lane_active()
        lane = self._lanes.get(lane_id)
        if lane is None:
            raise DrvLane_LaneMissing()
        if lane.lane_paused or lane.status != ADLaneStatus.OPEN:
            raise DrvLane_LanePaused()
        key = wallet.strip().lower()
        if key not in self._drivers:
            raise DrvLane_DriverMissing()
        if len(lane.drivers) >= AD_MAX_DRIVERS_PER_LANE:
            raise DrvLane_LaneFull()
        if paid_wei < lane.entry_fee_wei:
            raise DrvLane_EntryTooLow()
        if key not in lane.drivers:
            lane.drivers.append(key)
        if len(lane.drivers) >= AD_MIN_DRIVERS_TO_DEPART:
            lane.status = ADLaneStatus.FILLING
        self._emit("LaneJoined", {"laneId": lane_id, "wallet": wallet})

    def depart_lane(self, lane_id: int, caller: str) -> None:
        lane = self._lanes.get(lane_id)
        if lane is None:
            raise DrvLane_LaneMissing()
        self._require_warden(caller)
        self._require_lane_active()
        if len(lane.drivers) < AD_MIN_DRIVERS_TO_DEPART:
            raise DrvLane_NotEnoughDrivers()
        lane.status = ADLaneStatus.DEPARTED
        lane.phase = ADRunPhase.EN_ROUTE
        lane.departed_at = time.time()
        ep = self._epochs[self._epoch_id]
        ep.total_runs += 1
        self._emit("LaneDeparted", {"laneId": lane_id, "drivers": list(lane.drivers)})

    def clear_checkpoint(self, lane_id: int, wallet: str) -> int:
        lane = self._lanes.get(lane_id)
        if lane is None:
            raise DrvLane_LaneMissing()
        if lane.phase not in (ADRunPhase.EN_ROUTE, ADRunPhase.PURSUIT):
            raise DrvLane_RunNotActive()
        key = wallet.strip().lower()
        if key not in lane.drivers:
            raise DrvLane_DriverMissing()
        drv = self._drivers[key]
        if drv.cooldown_until_tick > self._global_tick:
            raise DrvLane_CooldownActive()
        if drv.fuel <= 0:
            raise DrvLane_FuelEmpty()
        idx = lane.checkpoint_index
        if idx >= len(AD_CHECKPOINT_CATALOG):
            lane.phase = ADRunPhase.SETTLED
            return idx
        spec = AD_CHECKPOINT_CATALOG[idx]
        if drv.heat > spec.heat_cap:
            raise DrvLane_HeatCritical()
        fuel_cost = AD_FUEL_PER_CHECKPOINT + (1 if spec.kind == ADCheckpointKind.TRAP else 0)
        drv.fuel -= fuel_cost
        bonus = AD_SCORE_PER_CHECKPOINT
        if spec.kind == ADCheckpointKind.BOOST:
            bonus += 22
        elif spec.kind == ADCheckpointKind.STEALTH:
            drv.heat = max(0, drv.heat - 8)
        elif spec.kind == ADCheckpointKind.TRAP:
            drv.heat += AD_HEAT_ESCALATE_ON_SKIP // 2
        heat_bonus = min(AD_SCORE_HEAT_BONUS_CAP, max(0, spec.heat_cap - drv.heat))
        drv.score += bonus + heat_bonus // 4
        drv.checkpoints_cleared += 1
        lane.checkpoint_index += 1
        drv.cooldown_until_tick = self._global_tick + AD_COOLDOWN_TICKS
        if drv.heat > 55:
            lane.phase = ADRunPhase.PURSUIT
        if lane.checkpoint_index >= len(AD_CHECKPOINT_CATALOG):
            lane.phase = ADRunPhase.SETTLED
            lane.status = ADLaneStatus.ARCHIVED
        self._emit(
            "CheckpointCleared",
            {"laneId": lane_id, "wallet": wallet, "index": idx, "score": drv.score},
        )
        return lane.checkpoint_index

    def skip_checkpoint(self, lane_id: int, wallet: str) -> None:
        lane = self._lanes.get(lane_id)
        if lane is None:
            raise DrvLane_LaneMissing()
        key = wallet.strip().lower()
        if key not in lane.drivers:
            raise DrvLane_DriverMissing()
        drv = self._drivers[key]
        drv.heat += AD_HEAT_ESCALATE_ON_SKIP
        lane.phase = ADRunPhase.PURSUIT
        self._emit("CheckpointSkipped", {"laneId": lane_id, "wallet": wallet, "heat": drv.heat})

    def settle_lane(self, lane_id: int, caller: str) -> Dict[str, Any]:
        lane = self._lanes.get(lane_id)
        if lane is None:
            raise DrvLane_LaneMissing()
        self._require_warden(caller)
        if lane.phase != ADRunPhase.SETTLED:
            raise DrvLane_RunNotActive()
        scores = {k: self._drivers[k].score for k in lane.drivers if k in self._drivers}
        winner = max(scores, key=scores.get) if scores else None
        payout = self._split_payout(lane.entry_fee_wei * len(lane.drivers))
        lane.phase = ADRunPhase.COOLDOWN
        self._emit("LaneSettled", {"laneId": lane_id, "winner": winner, "payout": payout})
        return {"winner": winner, "scores": scores, "payout": payout}

    def _split_payout(self, gross_wei: int) -> Dict[str, int]:
        if gross_wei <= 0:
            return {"vault": 0, "fee": 0, "runners": 0}
        vault = gross_wei * AD_VAULT_SHARE_BP // AD_BP_DENOM
        fee = gross_wei * AD_FEE_SHARE_BP // AD_BP_DENOM
        runners = gross_wei - vault - fee
        total = AD_VAULT_SHARE_BP + AD_FEE_SHARE_BP + AD_RUNNER_SHARE_BP
        if total != AD_BP_DENOM:
            raise DrvLane_InvalidBasisPoints()
        return {"vault": vault, "fee": fee, "runners": runners}

    def _leader_for_epoch(self, epoch_id: int) -> Optional[str]:
        best: Optional[str] = None
        best_score = -1
        for key, drv in self._drivers.items():
            if drv.epoch_id == epoch_id and drv.score > best_score:
                best_score = drv.score
                best = key
        return best

    def leaderboard(self, depth: int = AD_LEADERBOARD_DEPTH) -> List[Tuple[str, int, str]]:
        depth = max(1, min(depth, AD_LEADERBOARD_DEPTH))
        rows = sorted(
            self._drivers.values(),
            key=lambda d: (-d.score, d.checkpoints_cleared, d.joined_at),
        )[:depth]
        return [(d.wallet, d.score, d.pseudonym) for d in rows]

    def driver_profile(self, wallet: str) -> Optional[ADDriverProfile]:
        return self._drivers.get(wallet.strip().lower())

    def lane_state(self, lane_id: int) -> Optional[ADLaneState]:
        return self._lanes.get(lane_id)

    def epoch_state(self, epoch_id: int) -> Optional[ADEpochLedger]:
        return self._epochs.get(epoch_id)

    def event_log(self, limit: int = 100) -> List[ADEventRow]:
        limit = max(1, min(limit, 500))
        return self._events[-limit:]

    def config_digest(self) -> str:
        h_a = hashlib.sha256(
            (AD_DOMAIN_SEED + AD_VAULT_LANE + AD_ORACLE_BEACON).encode()
        ).hexdigest()
        h_b = hashlib.sha256(
            (AD_ROUTE_DIGEST + AD_HEAT_SALT + AD_EPOCH_MARK).encode()
        ).hexdigest()
        return hashlib.sha256((h_a + h_b).encode()).hexdigest()

    def anchor_snapshot(self) -> Dict[str, str]:
        return {
            "addressA": AD_ADDRESS_A,
            "addressB": AD_ADDRESS_B,
            "addressC": AD_ADDRESS_C,
            "addressD": AD_ADDRESS_D,
            "vaultLane": self._vault_lane,
            "oracleBeacon": self._oracle_beacon,
            "relayHub": self._relay_hub,
            "feeDesk": self._fee_desk,
        }

def _ad_valid_address(addr: str) -> bool:
    if not addr or not addr.startswith("0x"):
        return False
    body = addr[2:]
    if len(body) != 40:
        return False
    try:
        int(body, 16)
    except ValueError:
        return False
    return body != "0" * 40

def _ad_valid_hex32(h: str) -> bool:
    if not h.startswith("0x"):
        return False
    body = h[2:]
    return len(body) == 64 and all(c in "0123456789abcdefABCDEF" for c in body)

def ad_phase_label(phase: int) -> str:
    labels = (
        "Idle", "Staging", "EnRoute", "Pursuit", "Cooldown", "Settled"
    )
    return labels[phase] if 0 <= phase < len(labels) else "Unknown"

def ad_lane_status_label(status: int) -> str:
    labels = ("Open", "Filling", "Departed", "Archived")
    return labels[status] if 0 <= status < len(labels) else "Unknown"

def ad_checkpoint_kind_label(kind: int) -> str:
    labels = ("Standard", "Boost", "Stealth", "Trap")
    return labels[kind] if 0 <= kind < len(labels) else "Unknown"

def ad_wallet_short(wallet: str) -> str:
    if len(wallet) < 12:
        return wallet
    return f"{wallet[:8]}…{wallet[-6:]}"

def ad_bps_to_percent(bps: int) -> float:
    return round(bps / 100.0, 2)

def ad_format_wei(wei: int) -> str:
    eth = wei / 1_000_000_000_000_000_000
    return f"{eth:.6f} ETH"

def ad_catalog_size() -> int:
    return len(AD_CHECKPOINT_CATALOG)

def ad_sector_index(sector: str) -> int:
    sectors = ("NEON", "DOCK", "RAMP", "TUNL", "SKY", "GRID", "PIER", "ALLEY")
    try:
        return sectors.index(sector.upper())
    except ValueError:
        return -1

def ad_checkpoint_by_index(index: int) -> Optional[ADCheckpointSpec]:
    if 0 <= index < len(AD_CHECKPOINT_CATALOG):
        return AD_CHECKPOINT_CATALOG[index]
    return None

def ad_checkpoints_for_sector(sector: str) -> List[ADCheckpointSpec]:
    tag = sector.upper()
    return [cp for cp in AD_CHECKPOINT_CATALOG if cp.sector == tag]

def ad_total_catalog_distance() -> int:
    return sum(cp.distance_m for cp in AD_CHECKPOINT_CATALOG)

def ad_max_heat_cap_in_catalog() -> int:
    return max(cp.heat_cap for cp in AD_CHECKPOINT_CATALOG)

def ad_min_heat_cap_in_catalog() -> int:
    return min(cp.heat_cap for cp in AD_CHECKPOINT_CATALOG)

def ad_lookup_cp_000() -> ADCheckpointSpec:
    """Resolve catalog row 0: CP-NEON-001."""
    return AD_CHECKPOINT_CATALOG[0]

def ad_lookup_cp_001() -> ADCheckpointSpec:
    """Resolve catalog row 1: CP-DOCK-002."""
    return AD_CHECKPOINT_CATALOG[1]

def ad_lookup_cp_002() -> ADCheckpointSpec:
    """Resolve catalog row 2: CP-RAMP-003."""
    return AD_CHECKPOINT_CATALOG[2]

def ad_lookup_cp_003() -> ADCheckpointSpec:
    """Resolve catalog row 3: CP-TUNL-004."""
    return AD_CHECKPOINT_CATALOG[3]

def ad_lookup_cp_004() -> ADCheckpointSpec:
    """Resolve catalog row 4: CP-SKY-005."""
    return AD_CHECKPOINT_CATALOG[4]

def ad_lookup_cp_005() -> ADCheckpointSpec:
    """Resolve catalog row 5: CP-GRID-006."""
    return AD_CHECKPOINT_CATALOG[5]

def ad_lookup_cp_006() -> ADCheckpointSpec:
    """Resolve catalog row 6: CP-PIER-007."""
    return AD_CHECKPOINT_CATALOG[6]

def ad_lookup_cp_007() -> ADCheckpointSpec:
    """Resolve catalog row 7: CP-ALLEY-008."""
    return AD_CHECKPOINT_CATALOG[7]

def ad_lookup_cp_008() -> ADCheckpointSpec:
    """Resolve catalog row 8: CP-NEON-009."""
    return AD_CHECKPOINT_CATALOG[8]

def ad_lookup_cp_009() -> ADCheckpointSpec:
    """Resolve catalog row 9: CP-DOCK-010."""
    return AD_CHECKPOINT_CATALOG[9]

def ad_lookup_cp_010() -> ADCheckpointSpec:
    """Resolve catalog row 10: CP-RAMP-011."""
    return AD_CHECKPOINT_CATALOG[10]

def ad_lookup_cp_011() -> ADCheckpointSpec:
    """Resolve catalog row 11: CP-TUNL-012."""
    return AD_CHECKPOINT_CATALOG[11]

def ad_lookup_cp_012() -> ADCheckpointSpec:
    """Resolve catalog row 12: CP-SKY-013."""
    return AD_CHECKPOINT_CATALOG[12]

def ad_lookup_cp_013() -> ADCheckpointSpec:
    """Resolve catalog row 13: CP-GRID-014."""
    return AD_CHECKPOINT_CATALOG[13]

def ad_lookup_cp_014() -> ADCheckpointSpec:
    """Resolve catalog row 14: CP-PIER-015."""
    return AD_CHECKPOINT_CATALOG[14]

def ad_lookup_cp_015() -> ADCheckpointSpec:
    """Resolve catalog row 15: CP-ALLEY-016."""
    return AD_CHECKPOINT_CATALOG[15]

def ad_lookup_cp_016() -> ADCheckpointSpec:
    """Resolve catalog row 16: CP-NEON-017."""
    return AD_CHECKPOINT_CATALOG[16]

def ad_lookup_cp_017() -> ADCheckpointSpec:
    """Resolve catalog row 17: CP-DOCK-018."""
    return AD_CHECKPOINT_CATALOG[17]

def ad_lookup_cp_018() -> ADCheckpointSpec:
    """Resolve catalog row 18: CP-RAMP-019."""
    return AD_CHECKPOINT_CATALOG[18]

def ad_lookup_cp_019() -> ADCheckpointSpec:
    """Resolve catalog row 19: CP-TUNL-020."""
    return AD_CHECKPOINT_CATALOG[19]

def ad_lookup_cp_020() -> ADCheckpointSpec:
    """Resolve catalog row 20: CP-SKY-021."""
    return AD_CHECKPOINT_CATALOG[20]

def ad_lookup_cp_021() -> ADCheckpointSpec:
    """Resolve catalog row 21: CP-GRID-022."""
    return AD_CHECKPOINT_CATALOG[21]

def ad_lookup_cp_022() -> ADCheckpointSpec:
    """Resolve catalog row 22: CP-PIER-023."""
    return AD_CHECKPOINT_CATALOG[22]

def ad_lookup_cp_023() -> ADCheckpointSpec:
    """Resolve catalog row 23: CP-ALLEY-024."""
    return AD_CHECKPOINT_CATALOG[23]

def ad_lookup_cp_024() -> ADCheckpointSpec:
    """Resolve catalog row 24: CP-NEON-025."""
    return AD_CHECKPOINT_CATALOG[24]

def ad_lookup_cp_025() -> ADCheckpointSpec:
    """Resolve catalog row 25: CP-DOCK-026."""
    return AD_CHECKPOINT_CATALOG[25]

def ad_lookup_cp_026() -> ADCheckpointSpec:
    """Resolve catalog row 26: CP-RAMP-027."""
    return AD_CHECKPOINT_CATALOG[26]

def ad_lookup_cp_027() -> ADCheckpointSpec:
    """Resolve catalog row 27: CP-TUNL-028."""
    return AD_CHECKPOINT_CATALOG[27]

def ad_lookup_cp_028() -> ADCheckpointSpec:
    """Resolve catalog row 28: CP-SKY-029."""
    return AD_CHECKPOINT_CATALOG[28]

def ad_lookup_cp_029() -> ADCheckpointSpec:
    """Resolve catalog row 29: CP-GRID-030."""
    return AD_CHECKPOINT_CATALOG[29]

def ad_lookup_cp_030() -> ADCheckpointSpec:
    """Resolve catalog row 30: CP-PIER-031."""
    return AD_CHECKPOINT_CATALOG[30]

def ad_lookup_cp_031() -> ADCheckpointSpec:
    """Resolve catalog row 31: CP-ALLEY-032."""
    return AD_CHECKPOINT_CATALOG[31]

def ad_lookup_cp_032() -> ADCheckpointSpec:
    """Resolve catalog row 32: CP-NEON-033."""
    return AD_CHECKPOINT_CATALOG[32]

def ad_lookup_cp_033() -> ADCheckpointSpec:
    """Resolve catalog row 33: CP-DOCK-034."""
    return AD_CHECKPOINT_CATALOG[33]

def ad_lookup_cp_034() -> ADCheckpointSpec:
    """Resolve catalog row 34: CP-RAMP-035."""
    return AD_CHECKPOINT_CATALOG[34]

def ad_lookup_cp_035() -> ADCheckpointSpec:
    """Resolve catalog row 35: CP-TUNL-036."""
    return AD_CHECKPOINT_CATALOG[35]

def ad_lookup_cp_036() -> ADCheckpointSpec:
    """Resolve catalog row 36: CP-SKY-037."""
    return AD_CHECKPOINT_CATALOG[36]

def ad_lookup_cp_037() -> ADCheckpointSpec:
    """Resolve catalog row 37: CP-GRID-038."""
    return AD_CHECKPOINT_CATALOG[37]

def ad_lookup_cp_038() -> ADCheckpointSpec:
    """Resolve catalog row 38: CP-PIER-039."""
    return AD_CHECKPOINT_CATALOG[38]

def ad_lookup_cp_039() -> ADCheckpointSpec:
    """Resolve catalog row 39: CP-ALLEY-040."""
    return AD_CHECKPOINT_CATALOG[39]

def ad_lookup_cp_040() -> ADCheckpointSpec:
    """Resolve catalog row 40: CP-NEON-041."""
    return AD_CHECKPOINT_CATALOG[40]

def ad_lookup_cp_041() -> ADCheckpointSpec:
    """Resolve catalog row 41: CP-DOCK-042."""
    return AD_CHECKPOINT_CATALOG[41]

def ad_lookup_cp_042() -> ADCheckpointSpec:
    """Resolve catalog row 42: CP-RAMP-043."""
    return AD_CHECKPOINT_CATALOG[42]

def ad_lookup_cp_043() -> ADCheckpointSpec:
    """Resolve catalog row 43: CP-TUNL-044."""
    return AD_CHECKPOINT_CATALOG[43]

def ad_lookup_cp_044() -> ADCheckpointSpec:
    """Resolve catalog row 44: CP-SKY-045."""
    return AD_CHECKPOINT_CATALOG[44]

def ad_lookup_cp_045() -> ADCheckpointSpec:
    """Resolve catalog row 45: CP-GRID-046."""
    return AD_CHECKPOINT_CATALOG[45]

def ad_lookup_cp_046() -> ADCheckpointSpec:
    """Resolve catalog row 46: CP-PIER-047."""
    return AD_CHECKPOINT_CATALOG[46]

def ad_lookup_cp_047() -> ADCheckpointSpec:
    """Resolve catalog row 47: CP-ALLEY-048."""
    return AD_CHECKPOINT_CATALOG[47]

class AnonDriverPlatform:
    '''Facade for UI / RPC adapters.'''

    def __init__(self, engine: Optional[AnonDriverEngine] = None) -> None:
        self._engine = engine or AnonDriverEngine()

    @property
    def engine(self) -> AnonDriverEngine:
        return self._engine

    def api_register(self, wallet: str, pseudonym: str, entry_wei: int = AD_ENTRY_FEE_WEI) -> Dict[str, Any]:
        key = self._engine.register_driver(wallet, pseudonym, entry_wei)
        prof = self._engine.driver_profile(key)
        return {"driverKey": key, "profile": asdict(prof) if prof else {}}

    def api_open_lane(self, warden: str, fee_wei: int = AD_ENTRY_FEE_WEI) -> Dict[str, Any]:
        lid = self._engine.open_lane(warden, fee_wei)
        lane = self._engine.lane_state(lid)
        return {"laneId": lid, "lane": asdict(lane) if lane else {}}

    def api_join_lane(self, lane_id: int, wallet: str, paid_wei: int) -> Dict[str, Any]:
        self._engine.join_lane(lane_id, wallet, paid_wei)
        lane = self._engine.lane_state(lane_id)
        return {"laneId": lane_id, "drivers": lane.drivers if lane else []}

    def api_depart(self, lane_id: int, warden: str) -> Dict[str, Any]:
        self._engine.depart_lane(lane_id, warden)
        lane = self._engine.lane_state(lane_id)
        return {"laneId": lane_id, "phase": lane.phase if lane else None}

    def api_clear_checkpoint(self, lane_id: int, wallet: str) -> Dict[str, Any]:
        idx = self._engine.clear_checkpoint(lane_id, wallet)
        prof = self._engine.driver_profile(wallet)
        return {"checkpointIndex": idx, "score": prof.score if prof else 0}

    def api_tick(self, steps: int = 1) -> Dict[str, Any]:
        tick = self._engine.tick(steps)
        return {"globalTick": tick}

    def api_leaderboard(self, depth: int = 16) -> List[Dict[str, Any]]:
        rows = self._engine.leaderboard(depth)
        return [{"wallet": w, "score": s, "pseudonym": p} for w, s, p in rows]

    def api_config(self) -> Dict[str, Any]:
        eng = self._engine
        return {
            "warden": eng.warden(),
            "lanePaused": eng.lane_paused(),
            "digest": eng.config_digest(),
            "anchors": eng.anchor_snapshot(),
            "catalogSize": ad_catalog_size(),
            "epochId": eng._epoch_id,
        }

    def api_events(self, limit: int = 32) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self._engine.event_log(limit)]


def create_platform() -> AnonDriverPlatform:
    return AnonDriverPlatform(AnonDriverEngine())


def validate_platform_config() -> bool:
    addrs = [
        AD_ADDRESS_A,
        AD_ADDRESS_B,
        AD_ADDRESS_C,
        AD_ADDRESS_D,
        AD_VAULT_LANE,
        AD_ORACLE_BEACON,
        AD_RELAY_HUB,
        AD_FEE_DESK,
    ]
    if len(addrs) != len(set(a.lower() for a in addrs)):
        return False
    if not all(_ad_valid_address(a) for a in addrs):
        return False
    seeds = [AD_DOMAIN_SEED, AD_ROUTE_DIGEST, AD_HEAT_SALT, AD_EPOCH_MARK]
    if len(seeds) != len(set(s.lower() for s in seeds)):
        return False
    if not all(_ad_valid_hex32(s) for s in seeds):
        return False
    total_bp = AD_VAULT_SHARE_BP + AD_FEE_SHARE_BP + AD_RUNNER_SHARE_BP
    return total_bp == AD_BP_DENOM


def run_quick_smoke_test() -> Dict[str, Any]:
    plat = create_platform()
    w = AD_ADDRESS_A
    d1 = AD_ADDRESS_B
    d2 = AD_ADDRESS_C
    plat.api_register(d1, "neon-ghost", AD_ENTRY_FEE_WEI)
    plat.api_register(d2, "dock-runner", AD_ENTRY_FEE_WEI)
    lane = plat.api_open_lane(w)["laneId"]
    plat.api_join_lane(lane, d1, AD_ENTRY_FEE_WEI)
    plat.api_join_lane(lane, d2, AD_ENTRY_FEE_WEI)
    plat.api_depart(lane, w)
    plat.api_clear_checkpoint(lane, d1)
    plat.api_tick(5)
    return {
        "ok": validate_platform_config(),
        "laneId": lane,
        "leaderboard": plat.api_leaderboard(4),
        "digest": plat.engine.config_digest(),
    }


def export_state_json(engine: AnonDriverEngine) -> str:
    payload = {
        "warden": engine.warden(),
        "tick": engine.global_tick(),
        "leaderboard": engine.leaderboard(8),
        "digest": engine.config_digest(),
    }
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    result = run_quick_smoke_test()
    print(json.dumps(result, indent=2))
def ad_stat_lane_metric_0000(fuel: int, heat: int) -> int:
    """Derived lane metric #0 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 0) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0001(fuel: int, heat: int) -> int:
    """Derived lane metric #1 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 1) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0002(fuel: int, heat: int) -> int:
    """Derived lane metric #2 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 2) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0003(fuel: int, heat: int) -> int:
    """Derived lane metric #3 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 3) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0004(fuel: int, heat: int) -> int:
    """Derived lane metric #4 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 4) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0005(fuel: int, heat: int) -> int:
    """Derived lane metric #5 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 5) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0006(fuel: int, heat: int) -> int:
    """Derived lane metric #6 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 6) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0007(fuel: int, heat: int) -> int:
    """Derived lane metric #7 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 7) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0008(fuel: int, heat: int) -> int:
    """Derived lane metric #8 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 8) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0009(fuel: int, heat: int) -> int:
    """Derived lane metric #9 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 9) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0010(fuel: int, heat: int) -> int:
    """Derived lane metric #10 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 10) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0011(fuel: int, heat: int) -> int:
    """Derived lane metric #11 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 11) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0012(fuel: int, heat: int) -> int:
    """Derived lane metric #12 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 12) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0013(fuel: int, heat: int) -> int:
    """Derived lane metric #13 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 13) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0014(fuel: int, heat: int) -> int:
    """Derived lane metric #14 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 14) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0015(fuel: int, heat: int) -> int:
    """Derived lane metric #15 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 15) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0016(fuel: int, heat: int) -> int:
    """Derived lane metric #16 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 16) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0017(fuel: int, heat: int) -> int:
    """Derived lane metric #17 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 17) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0018(fuel: int, heat: int) -> int:
    """Derived lane metric #18 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 18) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0019(fuel: int, heat: int) -> int:
    """Derived lane metric #19 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 19) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0020(fuel: int, heat: int) -> int:
    """Derived lane metric #20 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 20) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0021(fuel: int, heat: int) -> int:
    """Derived lane metric #21 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 21) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0022(fuel: int, heat: int) -> int:
    """Derived lane metric #22 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 22) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0023(fuel: int, heat: int) -> int:
    """Derived lane metric #23 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 23) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0024(fuel: int, heat: int) -> int:
    """Derived lane metric #24 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 24) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0025(fuel: int, heat: int) -> int:
    """Derived lane metric #25 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 25) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0026(fuel: int, heat: int) -> int:
    """Derived lane metric #26 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 26) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0027(fuel: int, heat: int) -> int:
    """Derived lane metric #27 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 27) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0028(fuel: int, heat: int) -> int:
    """Derived lane metric #28 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 28) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0029(fuel: int, heat: int) -> int:
    """Derived lane metric #29 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 29) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0030(fuel: int, heat: int) -> int:
    """Derived lane metric #30 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 30) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0031(fuel: int, heat: int) -> int:
    """Derived lane metric #31 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 31) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0032(fuel: int, heat: int) -> int:
    """Derived lane metric #32 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 32) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0033(fuel: int, heat: int) -> int:
    """Derived lane metric #33 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 33) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0034(fuel: int, heat: int) -> int:
    """Derived lane metric #34 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 34) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0035(fuel: int, heat: int) -> int:
    """Derived lane metric #35 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 35) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0036(fuel: int, heat: int) -> int:
    """Derived lane metric #36 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 36) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0037(fuel: int, heat: int) -> int:
    """Derived lane metric #37 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 37) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0038(fuel: int, heat: int) -> int:
    """Derived lane metric #38 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 38) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0039(fuel: int, heat: int) -> int:
    """Derived lane metric #39 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 39) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0040(fuel: int, heat: int) -> int:
    """Derived lane metric #40 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 40) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0041(fuel: int, heat: int) -> int:
    """Derived lane metric #41 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 41) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0042(fuel: int, heat: int) -> int:
    """Derived lane metric #42 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 42) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0043(fuel: int, heat: int) -> int:
    """Derived lane metric #43 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 43) % 997
    return base + ad_sector_index("TUNL")

def ad_stat_lane_metric_0044(fuel: int, heat: int) -> int:
    """Derived lane metric #44 for sector SKY."""
    base = (fuel * 3 + heat * 7 + 44) % 997
    return base + ad_sector_index("SKY")

def ad_stat_lane_metric_0045(fuel: int, heat: int) -> int:
    """Derived lane metric #45 for sector GRID."""
    base = (fuel * 3 + heat * 7 + 45) % 997
    return base + ad_sector_index("GRID")

def ad_stat_lane_metric_0046(fuel: int, heat: int) -> int:
    """Derived lane metric #46 for sector PIER."""
    base = (fuel * 3 + heat * 7 + 46) % 997
    return base + ad_sector_index("PIER")

def ad_stat_lane_metric_0047(fuel: int, heat: int) -> int:
    """Derived lane metric #47 for sector ALLEY."""
    base = (fuel * 3 + heat * 7 + 47) % 997
    return base + ad_sector_index("ALLEY")

def ad_stat_lane_metric_0048(fuel: int, heat: int) -> int:
    """Derived lane metric #48 for sector NEON."""
    base = (fuel * 3 + heat * 7 + 48) % 997
    return base + ad_sector_index("NEON")

def ad_stat_lane_metric_0049(fuel: int, heat: int) -> int:
    """Derived lane metric #49 for sector DOCK."""
    base = (fuel * 3 + heat * 7 + 49) % 997
    return base + ad_sector_index("DOCK")

def ad_stat_lane_metric_0050(fuel: int, heat: int) -> int:
    """Derived lane metric #50 for sector RAMP."""
    base = (fuel * 3 + heat * 7 + 50) % 997
    return base + ad_sector_index("RAMP")

def ad_stat_lane_metric_0051(fuel: int, heat: int) -> int:
    """Derived lane metric #51 for sector TUNL."""
    base = (fuel * 3 + heat * 7 + 51) % 997
    return base + ad_sector_index("TUNL")
