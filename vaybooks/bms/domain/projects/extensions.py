"""Extension hooks for optional Boutique-as-project-type integration.

Boutique orders remain on their own domain; these hooks allow future
cross-linking without merging data stores.
"""

from __future__ import annotations

from typing import Optional, Protocol


class BoutiqueProjectBridge(Protocol):
    """Optional adapter — not wired by default."""

    def link_order_to_project(self, order_id: str, project_id: str) -> None: ...

    def find_project_for_order(self, order_id: str) -> Optional[str]: ...


class NoOpBoutiqueProjectBridge:
    def link_order_to_project(self, order_id: str, project_id: str) -> None:
        return None

    def find_project_for_order(self, order_id: str) -> Optional[str]:
        return None
