"""
TFT Set 16 Champion Ability Implementations

Facade module -- all implementation lives in _abilities_*.py sub-modules.
"""

from ._abilities_alphabetical import _AbilitiesAlphabeticalMixin
from ._abilities_base import _AbilitiesBaseMixin
from ._abilities_cost_tiers import _AbilitiesCostTiersMixin
from ._abilities_hero_augments import _AbilitiesHeroAugmentsMixin
from ._abilities_systems import _AbilitiesSystemsMixin


class ChampionAbilities(
    _AbilitiesCostTiersMixin,
    _AbilitiesAlphabeticalMixin,
    _AbilitiesHeroAugmentsMixin,
    _AbilitiesSystemsMixin,
    _AbilitiesBaseMixin,
):
    """Handler for champion-specific ability mechanics.

    Composed from 5 mixins via MRO:
    - _AbilitiesBaseMixin (rightmost): __init__, cast(), helpers, _deal_damage, _apply_stun
    - _AbilitiesSystemsMixin: named special systems + named passives
    - _AbilitiesHeroAugmentsMixin: hero augment ability handlers
    - _AbilitiesAlphabeticalMixin: main alphabetical champion handlers
    - _AbilitiesCostTiersMixin (leftmost): cost-tier champion abilities
    """

    pass
