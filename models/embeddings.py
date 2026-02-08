"""Embedding layers for TFT structured board data."""

from __future__ import annotations

from typing import Optional, Tuple

import torch
import torch.nn as nn


class UnitEmbedding(nn.Module):
    """Embeds unit-level categorical and positional signals."""

    def __init__(
        self,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        position_vocab_size: int = 29,
    ) -> None:
        super().__init__()
        self.champion_embedding = nn.Embedding(champion_vocab_size, 64, padding_idx=0)
        self.item_embedding = nn.Embedding(item_vocab_size, 32, padding_idx=0)
        self.item_projection = nn.Linear(32, 64)

        self.position_embedding = nn.Embedding(position_vocab_size, 64)
        self.position_aux_projection = nn.Linear(7, 64)

        self.star_embedding = nn.Embedding(4, 16, padding_idx=0)
        self.star_projection = nn.Linear(16, 64)

        self.cost_embedding = nn.Embedding(8, 16, padding_idx=0)
        self.cost_projection = nn.Linear(16, 64)

        self.encoder = nn.Sequential(
            nn.Linear(320, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, 64),
        )

    def _build_position_features(self, positions: torch.Tensor) -> torch.Tensor:
        row = (positions // 7).float()
        col = (positions % 7).float()
        normalized_row = row / 3.0
        normalized_col = col / 6.0
        is_frontline = (row <= 1).float()
        is_backline = (row >= 2).float()
        center_row, center_col = 1.5, 3.0
        hex_ring = torch.sqrt((row - center_row) ** 2 + (col - center_col) ** 2) / 4.0
        return torch.stack(
            [
                row / 3.0,
                col / 6.0,
                normalized_row,
                normalized_col,
                is_frontline,
                is_backline,
                hex_ring,
            ],
            dim=-1,
        )

    def forward(
        self,
        champion_ids: torch.Tensor,
        star_levels: torch.Tensor,
        items: torch.Tensor,
        positions: torch.Tensor,
        costs: torch.Tensor,
    ) -> torch.Tensor:
        """Encode unit tensors into ``(batch, units, 64)`` embeddings."""
        champion_embed = self.champion_embedding(champion_ids)

        item_embed = self.item_embedding(items)  # (B, U, 3, 32)
        item_mask = (items != 0).unsqueeze(-1).float()
        item_sum = (item_embed * item_mask).sum(dim=2)
        item_count = item_mask.sum(dim=2).clamp_min(1.0)
        item_agg = item_sum / item_count
        item_embed_64 = self.item_projection(item_agg)

        positions = positions.clamp_min(0)
        pos_embed = self.position_embedding(positions.clamp_max(self.position_embedding.num_embeddings - 1))
        pos_aux = self.position_aux_projection(self._build_position_features(positions))
        position_embed = pos_embed + pos_aux

        star_embed = self.star_projection(self.star_embedding(star_levels.clamp(0, 3)))
        cost_embed = self.cost_projection(self.cost_embedding(costs.clamp(0, 7)))

        combined = torch.cat(
            [champion_embed, item_embed_64, position_embed, star_embed, cost_embed],
            dim=-1,
        )
        return self.encoder(combined)


class BoardEncoder(nn.Module):
    """Encodes one board side into unit-sequence and global embeddings."""

    def __init__(
        self,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        augment_vocab_size: int = 375,
        trait_dim: int = 53,
    ) -> None:
        super().__init__()
        self.unit_embedding = UnitEmbedding(
            champion_vocab_size=champion_vocab_size,
            item_vocab_size=item_vocab_size,
            position_vocab_size=29,
        )
        self.trait_encoder = nn.Sequential(
            nn.Linear(trait_dim, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
        )
        self.augment_embedding = nn.Embedding(augment_vocab_size, 32, padding_idx=0)
        self.augment_projection = nn.Linear(32, 64)
        self.game_state_encoder = nn.Sequential(
            nn.Linear(6, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
        )
        self.global_fusion = nn.Sequential(
            nn.Linear(64 * 3, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
        )

    def forward(
        self,
        champion_ids: torch.Tensor,
        star_levels: torch.Tensor,
        items: torch.Tensor,
        positions: torch.Tensor,
        costs: torch.Tensor,
        traits: torch.Tensor,
        augments: torch.Tensor,
        game_state: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return ``(unit_embeddings, global_context, valid_mask)``."""
        if mask is None:
            mask = champion_ids != 0

        unit_embeddings = self.unit_embedding(
            champion_ids=champion_ids,
            star_levels=star_levels,
            items=items,
            positions=positions,
            costs=costs,
        )

        trait_context = self.trait_encoder(traits.float())
        augment_embed = self.augment_embedding(augments.clamp_min(0))
        augment_mask = (augments != 0).unsqueeze(-1).float()
        augment_sum = (augment_embed * augment_mask).sum(dim=1)
        augment_count = augment_mask.sum(dim=1).clamp_min(1.0)
        augment_context = self.augment_projection(augment_sum / augment_count)
        game_context = self.game_state_encoder(game_state.float())
        global_context = self.global_fusion(torch.cat([trait_context, augment_context, game_context], dim=-1))

        return unit_embeddings, global_context, mask.bool()
