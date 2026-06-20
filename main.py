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
