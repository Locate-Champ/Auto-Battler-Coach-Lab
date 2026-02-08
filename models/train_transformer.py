"""Training script for TFTTransformerV2."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
import torch
from torch.nn.utils import clip_grad_norm_
from torch.utils.data import DataLoader, Subset
from torch.utils.tensorboard import SummaryWriter

from .dataset import TFTDataset
from .transformer import TFTTransformerV2


@dataclass
class TrainConfig:
    """Transformer training hyperparameters."""

    data: str
    output: str
    epochs: int = 50
    batch_size: int = 512
    lr: float = 3e-4
    weight_decay: float = 0.01
    betas: Tuple[float, float] = (0.9, 0.98)
    early_stopping_patience: int = 10
    max_grad_norm: float = 1.0
    num_workers: int = 4
    seed: int = 42


def _select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _move_batch(batch: Dict[str, torch.Tensor], device: torch.device) -> Dict[str, torch.Tensor]:
    return {key: value.to(device) for key, value in batch.items()}


def _split_by_game(dataset: TFTDataset, seed: int) -> Tuple[Subset, Subset, Subset]:
    game_ids = np.asarray(dataset.game_ids)
    unique_games = np.unique(game_ids)
    if unique_games.size < 3:
        indices = np.arange(len(dataset))
        return Subset(dataset, indices.tolist()), Subset(dataset, []), Subset(dataset, [])

    train_games, temp_games = train_test_split(unique_games, test_size=0.2, random_state=seed)
    val_games, test_games = train_test_split(temp_games, test_size=0.5, random_state=seed)

    train_set = set(train_games.tolist())
    val_set = set(val_games.tolist())
    test_set = set(test_games.tolist())

    train_idx = [idx for idx, game_id in enumerate(game_ids.tolist()) if game_id in train_set]
    val_idx = [idx for idx, game_id in enumerate(game_ids.tolist()) if game_id in val_set]
    test_idx = [idx for idx, game_id in enumerate(game_ids.tolist()) if game_id in test_set]
    return Subset(dataset, train_idx), Subset(dataset, val_idx), Subset(dataset, test_idx)


def _evaluate(model: TFTTransformerV2, loader: DataLoader, device: torch.device) -> Dict[str, float]:
    model.eval()
    losses = []
    probs = []
    labels = []
    with torch.no_grad():
        for batch in loader:
            batch = _move_batch(batch, device)
            outputs = model(batch)
            loss_dict = model.compute_loss(outputs, batch)
            losses.append(float(loss_dict["total"].detach().cpu()))
            probs.extend(outputs["fight_win_prob"].detach().cpu().tolist())
            labels.extend(batch["fight_result"].view(-1).detach().cpu().tolist())

    avg_loss = float(np.mean(losses)) if losses else 0.0
    auc = roc_auc_score(labels, probs) if len(set(labels)) > 1 else 0.5
    return {"loss": avg_loss, "auc": float(auc)}


def parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser(description="Train TFTTransformerV2.")
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--output", type=str, default="models/checkpoints/transformer_v1")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    return TrainConfig(
        data=args.data,
        output=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
    )


def main() -> None:
    config = parse_args()
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)

    output_dir = Path(config.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = TFTDataset(config.data)
    train_dataset, val_dataset, test_dataset = _split_by_game(dataset, seed=config.seed)

    workers = min(config.num_workers, max(0, (os.cpu_count() or 1) - 1))
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=True,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=True,
    )

    device = _select_device()
    model = TFTTransformerV2().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.lr,
        weight_decay=config.weight_decay,
        betas=config.betas,
    )
    steps_per_epoch = max(1, len(train_loader))
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=config.lr,
        epochs=config.epochs,
        steps_per_epoch=steps_per_epoch,
        pct_start=0.1,
        anneal_strategy="cos",
    )

    amp_enabled = device.type == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)
    writer = SummaryWriter(log_dir=str(output_dir / "tb"))

    best_auc = -1.0
    epochs_without_improvement = 0
    global_step = 0

    for epoch in range(1, config.epochs + 1):
        model.train()
        epoch_losses = []
        for batch_idx, batch in enumerate(train_loader, start=1):
            batch = _move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)

            with torch.cuda.amp.autocast(enabled=amp_enabled):
                outputs = model(batch)
                loss_dict = model.compute_loss(outputs, batch)
                loss = loss_dict["total"]

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            clip_grad_norm_(model.parameters(), max_norm=config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            loss_value = float(loss.detach().cpu())
            epoch_losses.append(loss_value)
            global_step += 1

            if batch_idx % 100 == 0:
                print(f"epoch={epoch} batch={batch_idx}/{len(train_loader)} loss={loss_value:.4f}")

            writer.add_scalar("train/loss", loss_value, global_step)
            writer.add_scalar("train/lr", scheduler.get_last_lr()[0], global_step)

        train_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
        val_metrics = _evaluate(model, val_loader, device) if len(val_dataset) else {"loss": 0.0, "auc": 0.5}
        writer.add_scalar("val/loss", val_metrics["loss"], epoch)
        writer.add_scalar("val/auc", val_metrics["auc"], epoch)
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={val_metrics['loss']:.4f} val_auc={val_metrics['auc']:.4f}")

        if val_metrics["auc"] > best_auc:
            best_auc = val_metrics["auc"]
            epochs_without_improvement = 0
            torch.save(model.state_dict(), output_dir / "best_model.pt")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= config.early_stopping_patience:
                print("Early stopping triggered.")
                break

    if (output_dir / "best_model.pt").exists():
        model.load_state_dict(torch.load(output_dir / "best_model.pt", map_location=device))

    test_metrics = _evaluate(model, test_loader, device) if len(test_dataset) else {"loss": 0.0, "auc": 0.5}
    writer.add_scalar("test/loss", test_metrics["loss"], 0)
    writer.add_scalar("test/auc", test_metrics["auc"], 0)
    writer.close()

    summary = {
        "config": asdict(config),
        "device": str(device),
        "parameter_count": model.parameter_count(),
        "best_val_auc": best_auc,
        "test_metrics": test_metrics,
        "dataset_sizes": {
            "train": len(train_dataset),
            "val": len(val_dataset),
            "test": len(test_dataset),
        },
    }
    with (output_dir / "training_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Saved training summary -> {output_dir / 'training_summary.json'}")


if __name__ == "__main__":
    main()
