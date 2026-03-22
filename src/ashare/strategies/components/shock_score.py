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
class ShockScoreComponents:
    """Shared shock-score component breakdown before any weight set is applied."""

    excursion: float
    depth_raw: float
    depth_score: float
    speed_ret: float
    speed_score: float
    stabilization_score: float
    noise_base: float
    noise_ratio: float
    noise_penalty: float

    def to_dict(self) -> dict[str, float]:
        """Return a stable flat mapping for diagnostics and CSV export."""
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
        }


@dataclass(frozen=True)
class ShockScoreBreakdown(ShockScoreComponents):
    """Backward-compatible single-score breakdown for legacy callers/tests."""

    shock_score: float

    def to_dict(self) -> dict[str, float]:
        payload = super().to_dict()
        payload["shock_score"] = float(self.shock_score)
        return payload


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


def compute_shock_components(
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
) -> ShockScoreComponents:
    """Compute the locked v1 shared shock-score components."""
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

    return ShockScoreComponents(
        excursion=float(excursion),
        depth_raw=depth_raw,
        depth_score=depth_score,
        speed_ret=speed_ret,
        speed_score=speed_score,
        stabilization_score=stabilization_score,
        noise_base=noise_base,
        noise_ratio=noise_ratio,
        noise_penalty=noise_penalty,
    )


def compute_weighted_score(
    components: ShockScoreComponents,
    weights: dict[str, float] | None = None,
) -> float:
    """Apply a weight set to shared components and clip the final score to [0, 100]."""
    resolved_weights = {**DEFAULT_SCORE_WEIGHTS, **(weights or {})}
    raw_score = 100.0 * (
        (resolved_weights["depth"] * float(components.depth_score))
        + (resolved_weights["speed"] * float(components.speed_score))
        + (resolved_weights["stabilization"] * float(components.stabilization_score))
        - (resolved_weights["noise_penalty"] * float(components.noise_penalty))
    )
    return clip(raw_score, 0.0, 100.0)


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
    """Compute the legacy single-score breakdown on top of shared components."""
    components = compute_shock_components(
        close_now=close_now,
        close_prev=close_prev,
        close_minus_two=close_minus_two,
        high_now=high_now,
        low_now=low_now,
        excursion=excursion,
        excursion_threshold=excursion_threshold,
        close_history=close_history,
        speed_scale=speed_scale,
        noise_lookback=noise_lookback,
        noise_ratio_scale=noise_ratio_scale,
    )
    shock_score = compute_weighted_score(components, score_weights)

    return ShockScoreBreakdown(
        **components.to_dict(),
        shock_score=shock_score,
    )
