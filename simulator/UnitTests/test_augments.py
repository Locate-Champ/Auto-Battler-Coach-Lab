"""
Unit tests for the TFT Combat Simulator Augment System.

Tests augment loading, categorization, and combat effects.
"""

import sys
import pytest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.combat_engine import CombatEngine, AugmentManager, _AUGMENTS_LOADED


class TestAugmentLoading:
    """Tests for augment data loading."""

    def test_augments_loaded(self):
        """Verify augment data is loaded correctly."""
        assert _AUGMENTS_LOADED, "Augment data should be loaded"

    def test_augment_manager_initialization(self):
        """Test AugmentManager initializes correctly."""
        am = AugmentManager()
        assert len(am.augment_data) > 0, "Should have augment data"
        assert len(am.active_augments) == 0, "Should start with no active augments"

    def test_augment_count(self):
        """Verify expected number of augments loaded."""
        am = AugmentManager()
        # Set 16 has around 280+ active augments
        assert len(am.augment_data) >= 250, f"Expected 250+ augments, got {len(am.augment_data)}"

    def test_combat_augments_filter(self):
        """Test filtering combat-relevant augments."""
        am = AugmentManager()
        combat_augs = am.get_combat_augments()
        assert len(combat_augs) >= 100, "Should have 100+ combat-relevant augments"


class TestAugmentCategorization:
    """Tests for augment categorization."""

    def test_team_stat_augments(self):
        """Test identification of team stat augments."""
        am = AugmentManager()
        team_stat_count = sum(1 for _, data in am.augment_data.items()
                              if am._is_team_stat_augment(data))
        assert team_stat_count >= 30, f"Expected 30+ team stat augments, got {team_stat_count}"

    def test_hex_augments(self):
        """Test identification of hex effect augments."""
        am = AugmentManager()
        hex_count = sum(1 for _, data in am.augment_data.items()
                        if am._is_hex_augment(data))
        assert hex_count >= 5, f"Expected 5+ hex augments, got {hex_count}"

    def test_event_augments(self):
        """Test identification of event-triggered augments."""
        am = AugmentManager()
        event_count = sum(1 for _, data in am.augment_data.items()
                          if am._is_event_augment(data))
        assert event_count >= 5, f"Expected 5+ event augments, got {event_count}"

    def test_item_conditional_augments(self):
        """Test identification of item-conditional augments."""
        am = AugmentManager()
        item_count = sum(1 for _, data in am.augment_data.items()
                         if am._is_item_conditional_augment(data))
        assert item_count >= 10, f"Expected 10+ item-conditional augments, got {item_count}"


class TestAugmentApplication:
    """Tests for augment application to units."""

    @pytest.fixture
    def engine(self):
        """Create a combat engine for testing."""
        return CombatEngine()

    def test_damage_amp_augment(self, engine):
        """Test damage amplification augment application."""
        # Find Darkwill's Invasion augment
        darkwill = None
        for api_name, data in engine.augment_manager.augment_data.items():
            if "Darkwill" in data.get('name', ''):
                darkwill = api_name
                break

        assert darkwill is not None, "Darkwill's Invasion should exist"

        # Create unit and verify base stats
        unit = engine.create_unit('TFT16_Draven', 2, (0, 3), 0)
        base_damage_amp = unit.stats.damage_amp

        # Apply augment
        engine.augment_manager.set_augments([darkwill])
        engine.augment_manager.apply_augments([unit], {'Noxus': 0})

        # Verify damage amp increased
        assert unit.stats.damage_amp > base_damage_amp, "Damage amp should increase"
        assert abs(unit.stats.damage_amp - 0.10) < 0.01, "Should have ~10% damage amp"

    def test_durability_augment(self, engine):
        """Test durability/damage reduction augment application."""
        # Find Defense of the Placidium
        defense = None
        for api_name, data in engine.augment_manager.augment_data.items():
            if "Placidium" in data.get('name', ''):
                defense = api_name
                break

        assert defense is not None, "Defense of the Placidium should exist"

        # Create unit
        unit = engine.create_unit('TFT16_Leona', 2, (0, 3), 0)
        base_dr = unit.stats.damage_reduction

        # Apply augment
        engine.augment_manager.set_augments([defense])
        engine.augment_manager.apply_augments([unit], {'Ionia': 0})

        # Verify damage reduction increased
        assert unit.stats.damage_reduction > base_dr, "Damage reduction should increase"

    def test_augment_by_display_name(self, engine):
        """Test setting augments by display name (not just apiName)."""
        engine.augment_manager.set_augments(["Darkwill's Invasion"])
        assert len(engine.augment_manager.active_augments) == 1, "Should find augment by display name"


class TestAugmentCombatEffects:
    """Tests for augment effects in combat simulation."""

    @pytest.fixture
    def engine(self):
        """Create a combat engine for testing."""
        return CombatEngine()

    def test_augment_increases_damage(self, engine):
        """Test that damage augments increase combat damage output."""
        # Find a damage-increasing augment
        darkwill = None
        for api_name, data in engine.augment_manager.augment_data.items():
            if "Darkwill" in data.get('name', ''):
                darkwill = api_name
                break

        # Baseline simulation
        result_base = engine.simulate_1v1('TFT16_Draven', 'TFT16_Leona',
                                          star1=2, star2=2, num_simulations=50)

        # With damage augment
        result_aug = engine.simulate_1v1('TFT16_Draven', 'TFT16_Leona',
                                         star1=2, star2=2,
                                         augments1=[darkwill], num_simulations=50)

        # Verify damage increased
        assert result_aug['avg_damage']['TFT16_Draven'] >= result_base['avg_damage']['TFT16_Draven'], \
            "Damage augment should increase damage output"

    def test_run_combat_with_augments(self, engine):
        """Test run_combat accepts augment parameters."""
        team0 = [engine.create_unit('TFT16_Draven', 2, (0, 3), 0)]
        team1 = [engine.create_unit('TFT16_Leona', 2, (3, 3), 1)]

        # This should not raise an error
        result = engine.run_combat(team0, team1,
                                   team0_augments=["Darkwill's Invasion"])

        assert 'winner' in result, "Combat should complete with augments"
        assert 'combat_time' in result, "Should have combat time"

    def test_augment_reset_between_combats(self, engine):
        """Test that augment state resets between combats."""
        # Run first combat with augments
        result1 = engine.run_combat(
            [engine.create_unit('TFT16_Draven', 2, (0, 3), 0)],
            [engine.create_unit('TFT16_Leona', 2, (3, 3), 1)],
            team0_augments=["Darkwill's Invasion"]
        )

        # Run second combat without augments
        unit_clean = engine.create_unit('TFT16_Draven', 2, (0, 3), 0)
        initial_damage_amp = unit_clean.stats.damage_amp

        result2 = engine.run_combat(
            [unit_clean],
            [engine.create_unit('TFT16_Leona', 2, (3, 3), 1)]
        )

        # Unit should not have augment effects from previous combat
        assert initial_damage_amp == 0.0, "Clean unit should have 0 base damage amp"


class TestSpecificAugments:
    """Tests for specific augment implementations."""

    @pytest.fixture
    def engine(self):
        """Create a combat engine for testing."""
        return CombatEngine()

    def test_urf_augment_with_spatula(self, engine):
        """Test U.R.F augment works with Spatula item."""
        # Find U.R.F augment
        urf = None
        for api_name, data in engine.augment_manager.augment_data.items():
            if data.get('name') == 'U.R.F':
                urf = api_name
                break

        assert urf is not None, "U.R.F augment should exist"

        # Without Spatula - augment should not apply
        unit_no_spat = engine.create_unit('TFT16_Draven', 2, (0, 3), 0)
        base_as = unit_no_spat.stats.attack_speed

        engine.augment_manager.set_augments([urf])
        engine.augment_manager.apply_augments([unit_no_spat], {})

        # With Spatula - augment should apply
        unit_with_spat = engine.create_unit('TFT16_Draven', 2, (0, 3), 0, items=['Spatula'])
        spat_base_as = unit_with_spat.stats.attack_speed

        engine.augment_manager.reset()
        engine.augment_manager.set_augments([urf])
        engine.augment_manager.apply_augments([unit_with_spat], {})

        # Unit with Spatula should have higher attack speed
        assert unit_with_spat.stats.attack_speed > spat_base_as, \
            "U.R.F should increase attack speed for Spatula holder"


def test_augment_info_retrieval():
    """Test getting augment information by apiName."""
    am = AugmentManager()

    # Get a known augment
    for api_name in list(am.augment_data.keys())[:1]:
        info = am.get_augment_info(api_name)
        assert info is not None, f"Should get info for {api_name}"
        assert 'name' in info, "Should have name field"
        assert 'effects' in info, "Should have effects field"


def test_all_augment_names():
    """Test getting list of all augment names."""
    am = AugmentManager()
    names = am.get_all_augment_names()
    assert len(names) > 0, "Should have augment names"
    assert all(isinstance(n, str) for n in names), "All names should be strings"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
