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
