"""Monte-Carlo Dropout uncertainty utilities."""

from __future__ import annotations

from typing import Dict, List

import torch
import torch.nn.functional as F


class BayesianPredictor:
    """Estimate predictive uncertainty via MC Dropout."""

    def __init__(self, model: torch.nn.Module, n_samples: int = 30) -> None:
        self.model = model
        self.n_samples = n_samples

    def _confidence_bucket(self, uncertainty: torch.Tensor, probability: torch.Tensor) -> List[str]:
        labels: List[str] = []
        for unc, prob in zip(uncertainty.detach().cpu().tolist(), probability.detach().cpu().tolist()):
            if 0.45 <= prob <= 0.55 and unc > 0.1:
                labels.append("coin_flip")
            elif unc < 0.05:
                labels.append("high_confidence")
            elif unc < 0.15:
                labels.append("medium_confidence")
            else:
                labels.append("low_confidence")
        return labels

    def predict_with_uncertainty(self, batch: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor | List[str]]:
        """Run stochastic forward passes and return uncertainty signals."""
        was_training = self.model.training
        self.model.train()

        outputs: Dict[str, List[torch.Tensor]] = {
            "fight_win_logits": [],
            "damage_dealt": [],
            "placement_logits": [],
            "board_strength": [],
        }
        with torch.no_grad():
            for _ in range(self.n_samples):
                prediction = self.model(batch)
                for key in outputs:
                    outputs[key].append(prediction[key])

        if not was_training:
            self.model.eval()

        stacked = {key: torch.stack(values, dim=0) for key, values in outputs.items()}
        p_samples = torch.sigmoid(stacked["fight_win_logits"])
        aleatoric = (p_samples * (1.0 - p_samples)).mean(dim=0)
        epistemic = p_samples.var(dim=0)
        total_uncertainty = aleatoric + epistemic

        placement_mean_logits = stacked["placement_logits"].mean(dim=0)
        placement_distribution = F.softmax(placement_mean_logits, dim=-1)
        placement_uncertainty = stacked["placement_logits"].var(dim=0).sum(dim=-1)

        fight_win_prob = p_samples.mean(dim=0)
        confidence = (1.0 - total_uncertainty).clamp(0.0, 1.0)

        return {
            "fight_win_prob": fight_win_prob,
            "fight_win_aleatoric": aleatoric,
            "fight_win_epistemic": epistemic,
            "fight_win_total_uncertainty": total_uncertainty,
            "confidence": confidence,
            "confidence_bucket": self._confidence_bucket(total_uncertainty, fight_win_prob),
            "placement_distribution": placement_distribution,
            "placement_uncertainty": placement_uncertainty,
            "damage_dealt_mean": stacked["damage_dealt"].mean(dim=0),
            "board_strength_mean": stacked["board_strength"].mean(dim=0),
        }
