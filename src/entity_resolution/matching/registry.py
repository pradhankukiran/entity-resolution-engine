"""Pluggable strategy registry for match strategies."""

from __future__ import annotations

from entity_resolution.matching.base import MatchStrategy
from entity_resolution.matching.jaro_winkler import JaroWinklerStrategy
from entity_resolution.matching.levenshtein import LevenshteinStrategy
from entity_resolution.matching.phonetic_match import PhoneticStrategy
from entity_resolution.matching.token_sort import TokenSortStrategy


class StrategyRegistry:
    """Registry for match strategies.  Supports dynamic registration.

    Strategies are stored by their ``name`` property and can be added,
    removed, and retrieved at runtime.  The :pymeth:`default` classmethod
    creates a registry pre-loaded with all four built-in strategies.
    """

    def __init__(self):
        self._strategies: dict[str, MatchStrategy] = {}

    def register(self, strategy: MatchStrategy) -> None:
        """Register a strategy by its name.

        Args:
            strategy: A MatchStrategy instance to register.

        Raises:
            ValueError: If a strategy with the same name is already registered.
        """
        if strategy.name in self._strategies:
            raise ValueError(
                f"Strategy '{strategy.name}' is already registered. "
                "Unregister it first if you want to replace it."
            )
        self._strategies[strategy.name] = strategy

    def unregister(self, name: str) -> None:
        """Remove a strategy by name.

        Args:
            name: The name of the strategy to remove.

        Raises:
            KeyError: If no strategy with that name is registered.
        """
        if name not in self._strategies:
            raise KeyError(f"No strategy registered with name '{name}'")
        del self._strategies[name]

    def get(self, name: str) -> MatchStrategy:
        """Get a strategy by name.

        Args:
            name: The name of the strategy to retrieve.

        Returns:
            The registered MatchStrategy instance.

        Raises:
            KeyError: If no strategy with that name is registered.
        """
        if name not in self._strategies:
            raise KeyError(f"No strategy registered with name '{name}'")
        return self._strategies[name]

    def all(self) -> list[MatchStrategy]:
        """Return all registered strategies."""
        return list(self._strategies.values())

    @classmethod
    def default(cls) -> StrategyRegistry:
        """Create a registry with all built-in strategies pre-registered.

        Built-in strategies:
            - ``jaro_winkler`` (weight 0.30)
            - ``levenshtein``  (weight 0.25)
            - ``token_sort``   (weight 0.25)
            - ``phonetic``     (weight 0.20)
        """
        registry = cls()
        registry.register(JaroWinklerStrategy())
        registry.register(LevenshteinStrategy())
        registry.register(TokenSortStrategy())
        registry.register(PhoneticStrategy())
        return registry
