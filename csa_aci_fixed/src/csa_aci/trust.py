from dataclasses import dataclass, field


@dataclass
class TrustDecayModel:
    """
    Trust Decay Model — adds memory to the per-step trust score.

    Trust starts at 1.0 and:
    - Decays when agents conflict repeatedly
    - Recovers when agents agree and evidence aligns
    - Floors at 0.1 — never hits zero

    This produces a smooth curve that shows the system losing
    confidence during conflict storms and recovering during
    stable periods.
    """
    decay_factor: float = 0.92
    recovery_rate: float = 0.05
    floor: float = 0.1

    trust: float = field(default=1.0, init=False)
    history: list = field(default_factory=list, init=False)

    def step(self, conflict: bool, evidence_accepted: bool) -> float:
        """
        Update trust based on what happened this step.

        conflict         — True if agents disagreed
        evidence_accepted — True if CCE accepted the proposed intent
        """
        if conflict and not evidence_accepted:
            # worst case — conflict AND evidence rejected
            self.trust = self.trust * self.decay_factor * 0.95
        elif conflict:
            # conflict but evidence accepted — mild decay
            self.trust = self.trust * self.decay_factor
        else:
            # no conflict — recover toward 1.0
            self.trust = self.trust + self.recovery_rate * (1.0 - self.trust)

        # floor
        self.trust = max(self.trust, self.floor)
        self.trust = round(self.trust, 4)

        self.history.append(self.trust)
        return self.trust

    def current(self) -> float:
        return self.trust

    def summary(self) -> dict:
        if not self.history:
            return {"min": 0.0, "max": 0.0, "final": 0.0, "avg": 0.0}
        return {
            "min": round(min(self.history), 4),
            "max": round(max(self.history), 4),
            "final": self.history[-1],
            "avg": round(sum(self.history) / len(self.history), 4),
        }