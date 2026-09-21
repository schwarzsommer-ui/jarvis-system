"""Bounded multi-agent paper-trading simulation.

This module never connects to a broker, places orders, executes code, or
modifies its own source. "Self improvement" means selecting better parameters
inside this simulation only.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Agent:
    strategy: str
    lookback: int
    risk_fraction: float


@dataclass
class SimulationResult:
    agents: int
    steps: int
    start_balance: float
    final_balance: float
    best_strategy: str
    best_return_percent: float
    max_drawdown_percent: float
    survived: bool


class PaperSwarm:
    """Run a reproducible, offline paper-trading swarm."""

    MAX_AGENTS = 500
    MIN_START_BALANCE = 1.0
    MAX_RISK_FRACTION = 0.02

    def __init__(self, seed: int = 42):
        self.seed = seed

    @staticmethod
    def _prices(steps: int, rng: random.Random) -> list[float]:
        price = 100.0
        prices = [price]
        for index in range(steps):
            cycle = math.sin(index / 11.0) * 0.004
            drift = 0.0002 if index % 37 < 19 else -0.0001
            shock = rng.gauss(0.0, 0.008)
            price *= max(0.5, 1.0 + drift + cycle + shock)
            prices.append(price)
        return prices

    @staticmethod
    def _signal(strategy: str, prices: list[float], index: int, lookback: int) -> int:
        window = prices[max(0, index - lookback):index]
        if len(window) < 2:
            return 0
        change = (window[-1] / window[0]) - 1.0
        if strategy == "momentum":
            return 1 if change > 0.002 else -1 if change < -0.002 else 0
        if strategy == "mean_reversion":
            return -1 if change > 0.004 else 1 if change < -0.004 else 0
        return 0

    @classmethod
    def _agents(cls, count: int) -> list[Agent]:
        templates = (
            ("momentum", 8, 0.01),
            ("momentum", 21, 0.015),
            ("mean_reversion", 8, 0.01),
            ("mean_reversion", 21, 0.015),
        )
        return [
            Agent(*templates[index % len(templates)])
            for index in range(count)
        ]

    @staticmethod
    def _average(values: Iterable[float], fallback: float) -> float:
        values = list(values)
        return statistics.fmean(values) if values else fallback

    def run(
        self,
        start_balance: float = 50.0,
        agent_count: int = 500,
        steps: int = 240,
    ) -> SimulationResult:
        if not 1 <= agent_count <= self.MAX_AGENTS:
            raise ValueError(f"Die Agentenzahl muss zwischen 1 und {self.MAX_AGENTS} liegen.")
        if not self.MIN_START_BALANCE <= start_balance:
            raise ValueError("Das Startkapital muss mindestens 1,00 € betragen.")
        if not 20 <= steps <= 2000:
            raise ValueError("Die Simulationsdauer muss zwischen 20 und 2000 Schritten liegen.")

        rng = random.Random(self.seed)
        prices = self._prices(steps, rng)
        agents = self._agents(agent_count)
        balances = [start_balance for _ in agents]
        peaks = balances.copy()
        max_drawdown = 0.0
        best_strategy = "unentschieden"

        for index in range(1, len(prices)):
            price_return = prices[index] / prices[index - 1] - 1.0
            for agent_index, agent in enumerate(agents):
                signal = self._signal(agent.strategy, prices, index, agent.lookback)
                exposure = signal * min(agent.risk_fraction, self.MAX_RISK_FRACTION)
                balances[agent_index] *= max(0.0, 1.0 + exposure * price_return)
                peaks[agent_index] = max(peaks[agent_index], balances[agent_index])
                drawdown = (peaks[agent_index] - balances[agent_index]) / peaks[agent_index]
                max_drawdown = max(max_drawdown, drawdown)

        strategy_scores = {}
        for agent, balance in zip(agents, balances):
            strategy_scores.setdefault(agent.strategy, []).append(balance)
        best_strategy = max(
            strategy_scores,
            key=lambda strategy: self._average(strategy_scores[strategy], start_balance),
        )
        final_balance = self._average(balances, start_balance)
        best_balance = max(balances)
        return SimulationResult(
            agents=agent_count,
            steps=steps,
            start_balance=start_balance,
            final_balance=final_balance,
            best_strategy=best_strategy,
            best_return_percent=(best_balance / start_balance - 1.0) * 100.0,
            max_drawdown_percent=max_drawdown * 100.0,
            survived=final_balance > 0.0,
        )

    def optimize(self, generations: int = 3) -> str:
        """Bounded parameter search; it does not edit code or enable live trading."""
        if not 1 <= generations <= 10:
            raise ValueError("Die Zahl der Optimierungsrunden muss zwischen 1 und 10 liegen.")
        results = [
            self.run(agent_count=500, steps=240 + generation * 10)
            for generation in range(generations)
        ]
        best = max(results, key=lambda result: result.final_balance)
        return (
            f"Optimierung abgeschlossen: beste virtuelle Strategie {best.best_strategy}, "
            f"Durchschnitt {best.final_balance:.2f} € bei maximalem Drawdown "
            f"{best.max_drawdown_percent:.2f} %. Änderungen bleiben auf den Simulator begrenzt."
        )


def format_result(result: SimulationResult) -> str:
    status = "überlebt" if result.survived else "ausgefallen"
    return (
        f"Paper-Schwarm abgeschlossen: {result.agents} Agenten, {result.steps} Schritte, "
        f"{result.start_balance:.2f} € -> {result.final_balance:.2f} € Durchschnitt "
        f"({status}). Beste Strategie: {result.best_strategy}; bester Einzelreturn "
        f"{result.best_return_percent:.2f} %; maximaler Drawdown "
        f"{result.max_drawdown_percent:.2f} %. Keine echte Order wurde platziert."
    )
