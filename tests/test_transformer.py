"""Tests for TFTTransformerV2."""

from __future__ import annotations

import pytest
pytest.importorskip("torch")

import torch

from models.transformer import TFTTransformerV2


def _fake_batch(batch_size: int = 3) -> dict[str, torch.Tensor]:
    max_units = 14
    batch: dict[str, torch.Tensor] = {}
    for side in ("player", "opponent"):
        champions = torch.zeros((batch_size, max_units), dtype=torch.long)
        champions[:, :6] = torch.tensor([2, 3, 4, 5, 6, 7])
        batch[f"{side}_champion_ids"] = champions
        batch[f"{side}_star_levels"] = torch.ones((batch_size, max_units), dtype=torch.long)
        batch[f"{side}_items"] = torch.zeros((batch_size, max_units, 3), dtype=torch.long)
        batch[f"{side}_positions"] = torch.zeros((batch_size, max_units), dtype=torch.long)
        batch[f"{side}_costs"] = torch.ones((batch_size, max_units), dtype=torch.long)
        batch[f"{side}_mask"] = champions != 0
        batch[f"{side}_traits"] = torch.zeros((batch_size, 53), dtype=torch.float32)
        batch[f"{side}_augments"] = torch.zeros((batch_size, 3), dtype=torch.long)
        batch[f"{side}_game_state"] = torch.zeros((batch_size, 6), dtype=torch.float32)

    batch["fight_result"] = torch.ones((batch_size, 1), dtype=torch.float32)
    batch["damage_dealt"] = torch.ones((batch_size, 1), dtype=torch.float32)
    batch["survivors"] = torch.zeros((batch_size, 1), dtype=torch.float32)
    batch["combat_time"] = torch.zeros((batch_size, 1), dtype=torch.float32)
    batch["placement"] = torch.zeros((batch_size, 1), dtype=torch.long)
    return batch


def test_forward_shapes() -> None:
    model = TFTTransformerV2()
    outputs = model(_fake_batch())
    assert outputs["fight_win_logits"].shape == (3,)
    assert outputs["fight_win_prob"].shape == (3,)
    assert outputs["damage_dealt"].shape == (3,)
    assert outputs["survivors"].shape == (3,)
    assert outputs["combat_time"].shape == (3,)
    assert outputs["placement_logits"].shape == (3, 8)
    assert outputs["placement_distribution"].shape == (3, 8)
    assert outputs["board_strength"].shape == (3,)


def test_multitask_loss_computes() -> None:
    model = TFTTransformerV2()
    batch = _fake_batch()
    outputs = model(batch)
    losses = model.compute_loss(outputs, batch)
    assert losses["total"].item() >= 0
    assert set(losses.keys()) == {"total", "fight", "damage", "survivors", "time", "placement", "strength"}
