"""TFT cross-attention transformer model."""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from .embeddings import BoardEncoder


class AttentionPooling(nn.Module):
    """Learned attention pooling over a sequence."""

    def __init__(self, embed_dim: int) -> None:
        super().__init__()
        self.query = nn.Parameter(torch.randn(embed_dim))

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        scores = torch.matmul(x, self.query) / math.sqrt(x.size(-1))
        if mask is not None:
            scores = scores.masked_fill(~mask, float("-inf"))
            empty_rows = ~mask.any(dim=1)
            if empty_rows.any():
                scores[empty_rows] = 0.0
        weights = F.softmax(scores, dim=1)
        return torch.sum(x * weights.unsqueeze(-1), dim=1)


class TFTTransformerV2(nn.Module):
    """Cross-attention transformer for TFT combat and placement prediction."""

    def __init__(
        self,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        augment_vocab_size: int = 375,
        trait_dim: int = 53,
    ) -> None:
        super().__init__()
        self.board_encoder = BoardEncoder(
            champion_vocab_size=champion_vocab_size,
            item_vocab_size=item_vocab_size,
            augment_vocab_size=augment_vocab_size,
            trait_dim=trait_dim,
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=64,
            nhead=4,
            dim_feedforward=256,
            dropout=0.1,
            batch_first=True,
        )
        self.self_attention = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=64, num_heads=4, dropout=0.1, batch_first=True
        )

        self.player_pool = AttentionPooling(embed_dim=64)
        self.opponent_pool = AttentionPooling(embed_dim=64)

        self.mlp = nn.Sequential(
            nn.Linear(384, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.15),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.15),
            nn.Linear(128, 64),
            nn.GELU(),
        )

        self.fight_head = nn.Linear(64, 1)
        self.damage_head = nn.Linear(64, 1)
        self.survivors_head = nn.Linear(64, 1)
        self.combat_time_head = nn.Linear(64, 1)
        self.placement_head = nn.Linear(64, 8)
        self.board_strength_head = nn.Linear(64, 1)

    def _encode_side(
        self, batch: Dict[str, torch.Tensor], prefix: str
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.board_encoder(
            champion_ids=batch[f"{prefix}_champion_ids"],
            star_levels=batch[f"{prefix}_star_levels"],
            items=batch[f"{prefix}_items"],
            positions=batch[f"{prefix}_positions"],
            costs=batch[f"{prefix}_costs"],
            traits=batch[f"{prefix}_traits"],
            augments=batch[f"{prefix}_augments"],
            game_state=batch[f"{prefix}_game_state"],
            mask=batch.get(f"{prefix}_mask"),
        )

    def forward(self, batch: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """Run forward pass over a structured batch."""
        player_units, player_global, player_mask = self._encode_side(batch, "player")
        opponent_units, opponent_global, opponent_mask = self._encode_side(batch, "opponent")

        player_encoded = self.self_attention(player_units, src_key_padding_mask=~player_mask)
        opponent_encoded = self.self_attention(opponent_units, src_key_padding_mask=~opponent_mask)

        cross_output, _ = self.cross_attention(
            query=player_encoded,
            key=opponent_encoded,
            value=opponent_encoded,
            key_padding_mask=~opponent_mask,
        )
        player_cross = player_encoded + cross_output

        player_pooled = self.player_pool(player_cross, player_mask)
        opponent_pooled = self.opponent_pool(opponent_encoded, opponent_mask)

        combined = torch.cat(
            [
                player_pooled,
                opponent_pooled,
                player_global,
                opponent_global,
                player_pooled - opponent_pooled,
                player_pooled * opponent_pooled,
            ],
            dim=-1,
        )
        hidden = self.mlp(combined)

        fight_logits = self.fight_head(hidden).squeeze(-1)
        damage_dealt = F.relu(self.damage_head(hidden).squeeze(-1))
        survivors = F.relu(self.survivors_head(hidden).squeeze(-1))
        combat_time = F.relu(self.combat_time_head(hidden).squeeze(-1))
        placement_logits = self.placement_head(hidden)
        board_strength = self.board_strength_head(hidden).squeeze(-1)

        return {
            "fight_win_logits": fight_logits,
            "fight_win_prob": torch.sigmoid(fight_logits),
            "damage_dealt": damage_dealt,
            "survivors": survivors,
            "combat_time": combat_time,
            "placement_logits": placement_logits,
            "placement_distribution": F.softmax(placement_logits, dim=-1),
            "board_strength": board_strength,
        }

    def compute_loss(
        self,
        outputs: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor],
        board_strength_m: float = 38.097,
        board_strength_c: float = 25.491,
    ) -> Dict[str, torch.Tensor]:
        """Compute weighted multi-task training loss."""
        target_win = targets["fight_result"].float().view(-1)
        target_damage = targets["damage_dealt"].float().view(-1)
        target_survivors = targets["survivors"].float().view(-1)
        target_time = targets["combat_time"].float().view(-1)
        target_placement = targets["placement"].long().view(-1)
        target_strength = board_strength_m * target_win + board_strength_c

        loss_fight = F.binary_cross_entropy_with_logits(outputs["fight_win_logits"], target_win)
        loss_damage = F.mse_loss(outputs["damage_dealt"], target_damage)
        loss_survivors = F.smooth_l1_loss(outputs["survivors"], target_survivors)
        loss_time = F.smooth_l1_loss(outputs["combat_time"], target_time)
        loss_place = F.cross_entropy(outputs["placement_logits"], target_placement)
        loss_strength = F.mse_loss(outputs["board_strength"], target_strength)

        total = (
            (1.0 * loss_fight)
            + (0.3 * loss_damage)
            + (0.1 * loss_survivors)
            + (0.05 * loss_time)
            + (0.5 * loss_place)
            + (0.2 * loss_strength)
        )
        return {
            "total": total,
            "fight": loss_fight,
            "damage": loss_damage,
            "survivors": loss_survivors,
            "time": loss_time,
            "placement": loss_place,
            "strength": loss_strength,
        }

    def parameter_count(self) -> int:
        """Return trainable parameter count."""
        return sum(param.numel() for param in self.parameters() if param.requires_grad)
