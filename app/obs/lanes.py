from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LaneStack:
    max_lanes: int = 8
    next_lane: int = 0

    def assign_lane(self) -> int:
        lane = self.next_lane
        self.next_lane = (self.next_lane + 1) % max(1, self.max_lanes)
        return lane

    def bump_existing_lane(self, lane: int) -> int:
        return min(max(0, lane) + 1, max(1, self.max_lanes) - 1)
