"""Shock strength scoring helpers for intraday downside-reversion signals."""

from __future__ import annotations

from dataclasses import dataclass

EPSILON = 1e-12
DEFAULT_SPEED_SCALE = 0.03
DEFAULT_NOISE_LOOKBACK = 10
DEFAULT_NOISE_RATIO_SCALE = 3.0
DEFAULT_SCORE_WEIGHTS = {
    "depth": 0.45,
    "speed": 0.25,
    "stabilization": 0.20,
    "noise_penalty": 0.10,
}


@dataclass(frozen=True)
class ShockScoreBreakdown:
    """Fully expanded v1 shock score output for diagnostics and filtering."""

    excursion: float
    depth_raw: float
    depth_score: float
    speed_ret: float
    speed_score: float
    stabilization_score: float
    noise_base: float
    noise_ratio: float
    noise_penalty: float
    shock_score: float

    def to_dict(self) -> dict[str, float]:
        """Return a stable flat mapping for CSV export."""
        return {
            "excursion": float(self.excursion),
            "depth_raw": float(self.depth_raw),
            "depth_score": float(self.depth_score),
            "speed_ret": float(self.speed_ret),
            "speed_score": float(self.speed_score),
            "stabilization_score": float(self.stabilization_score),
            "noise_base": float(self.noise_base),
            "noise_ratio": float(self.noise_ratio),
            "noise_penalty": float(self.noise_penalty),
            "shock_score": float(self.shock_score),
        }


def clip(value: float, lower: float, upper: float) -> float:
    """Return ``value`` constrained to ``[lower, upper]``."""
    return max(lower, min(upper, float(value)))


def compute_stabilization_score(*, close_now: float, close_prev: float, high_now: float, low_now: float) -> float:
    """Compute the discrete stabilization score in ``{0.0, 0.5, 1.0}``."""
    stabilization_score = 0.0
    if float(close_now) > float(close_prev):
        stabilization_score += 0.5

    close_location = (float(close_now) - float(low_now)) / (float(high_now) - float(low_now) + EPSILON)
    if close_location >= 0.5:
        stabilization_score += 0.5

    return stabilization_score


def compute_noise_base(close_history: list[float], noise_lookback: int = DEFAULT_NOISE_LOOKBACK) -> float:
    """Compute recent mean absolute 1-bar close return over the requested lookback."""
    if len(close_history) < 2:
        return 0.0

    recent_closes = list(close_history[-(int(noise_lookback) + 1) :])
    absolute_returns: list[float] = []
    for prev_close, close_now in zip(recent_closes[:-1], recent_closes[1:]):
        prev_close = float(prev_close)
        close_now = float(close_now)
        if prev_close == 0.0:
            absolute_returns.append(0.0)
            continue
        absolute_returns.append(abs((close_now - prev_close) / prev_close))

    return sum(absolute_returns) / len(absolute_returns) if absolute_returns else 0.0


def compute_shock_score(
    *,
    close_now: float,
    close_prev: float,
    close_minus_two: float,
    high_now: float,
    low_now: float,
    excursion: float,
    excursion_threshold: float,
    close_history: list[float],
    speed_scale: float = DEFAULT_SPEED_SCALE,
    noise_lookback: int = DEFAULT_NOISE_LOOKBACK,
    noise_ratio_scale: float = DEFAULT_NOISE_RATIO_SCALE,
    score_weights: dict[str, float] | None = None,
) -> ShockScoreBreakdown:
    """Compute the locked v1 shock strength score and all of its components."""
    weights = {**DEFAULT_SCORE_WEIGHTS, **(score_weights or {})}

    depth_raw = abs(float(excursion))
    depth_score = clip(depth_raw / (2.0 * float(excursion_threshold)), 0.0, 1.0)

    speed_ret = 0.0 if float(close_minus_two) == 0.0 else (float(close_now) - float(close_minus_two)) / float(close_minus_two)
    speed_score = clip(abs(min(speed_ret, 0.0)) / float(speed_scale), 0.0, 1.0)

    stabilization_score = compute_stabilization_score(
        close_now=float(close_now),
        close_prev=float(close_prev),
        high_now=float(high_now),
        low_now=float(low_now),
    )

    noise_base = compute_noise_base(close_history, noise_lookback=int(noise_lookback))
    noise_ratio = depth_raw / (noise_base + EPSILON)
    noise_penalty = 1.0 - clip(noise_ratio / float(noise_ratio_scale), 0.0, 1.0)

    raw_score = 100.0 * (
        (weights["depth"] * depth_score)
        + (weights["speed"] * speed_score)
        + (weights["stabilization"] * stabilization_score)
        - (weights["noise_penalty"] * noise_penalty)
    )
    shock_score = clip(raw_score, 0.0, 100.0)

    return ShockScoreBreakdown(
        excursion=float(excursion),
        depth_raw=depth_raw,
        depth_score=depth_score,
        speed_ret=speed_ret,
        speed_score=speed_score,
        stabilization_score=stabilization_score,
        noise_base=noise_base,
        noise_ratio=noise_ratio,
        noise_penalty=noise_penalty,
        shock_score=shock_score,
    )
