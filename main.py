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
