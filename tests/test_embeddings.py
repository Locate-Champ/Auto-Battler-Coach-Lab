"""Tests for embedding modules."""

from __future__ import annotations

import pytest
pytest.importorskip("torch")

import torch

from models.embeddings import BoardEncoder, UnitEmbedding


def _make_unit_inputs(batch: int = 2, units: int = 14) -> dict[str, torch.Tensor]:
    champion_ids = torch.zeros((batch, units), dtype=torch.long)
    champion_ids[:, :5] = torch.tensor([[2, 3, 4, 5, 6], [6, 5, 4, 3, 2]])
    star_levels = torch.zeros((batch, units), dtype=torch.long)
    star_levels[:, :5] = 2
    items = torch.zeros((batch, units, 3), dtype=torch.long)
    items[:, :5, 0] = 10
    positions = torch.zeros((batch, units), dtype=torch.long)
    positions[:, :5] = torch.tensor([1, 2, 3, 4, 5])
    costs = torch.zeros((batch, units), dtype=torch.long)
    costs[:, :5] = torch.tensor([2, 3, 4, 5, 1])
    return {
        "champion_ids": champion_ids,
        "star_levels": star_levels,
        "items": items,
        "positions": positions,
        "costs": costs,
    }


def test_unit_embedding_shapes() -> None:
    module = UnitEmbedding()
    inputs = _make_unit_inputs()
    output = module(**inputs)
    assert output.shape == (2, 14, 64)


def test_board_encoder_outputs_masked_shapes() -> None:
    encoder = BoardEncoder()
    unit_inputs = _make_unit_inputs()
    traits = torch.zeros((2, 53), dtype=torch.float32)
    augments = torch.zeros((2, 3), dtype=torch.long)
    game_state = torch.zeros((2, 6), dtype=torch.float32)
    unit_embeddings, global_context, mask = encoder(
        champion_ids=unit_inputs["champion_ids"],
        star_levels=unit_inputs["star_levels"],
        items=unit_inputs["items"],
        positions=unit_inputs["positions"],
        costs=unit_inputs["costs"],
        traits=traits,
        augments=augments,
        game_state=game_state,
    )
    assert unit_embeddings.shape == (2, 14, 64)
    assert global_context.shape == (2, 64)
    assert mask.shape == (2, 14)
    assert mask[:, :5].all()
    assert (~mask[:, 5:]).all()
