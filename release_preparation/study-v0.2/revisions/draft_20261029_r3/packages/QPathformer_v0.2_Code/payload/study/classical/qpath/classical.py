"""Connected local text reference for QPATH-ARCH-002 v0.3.1.

Inference takes tokens, masks and (only for stable random routing) original input
text. Labels, ratings, split IDs and provenance IDs are never forward inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .policies import canonical_route_text, stable_text_route


@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 8192
    max_length: int = 256
    width: int = 256
    layers: int = 6
    heads: int = 4
    feedforward: int = 1024
    adapters: int = 18
    bottleneck: int = 16
    labels: int = 4
    dropout: float = 0.1
    norm_eps: float = 1e-5
    route_eps: float = 1e-8
    pad_id: int = 0

    def __post_init__(self) -> None:
        if self.width % self.heads or min(self.width, self.layers, self.heads, self.adapters, self.labels) < 1:
            raise ValueError("Positive dimensions and width divisible by heads are required")

    @classmethod
    def smoke(cls) -> ModelConfig:
        """Explicit engineering fixture deviations; these are not paper settings."""
        return cls(vocab_size=128, max_length=32, width=32, layers=2, heads=4,
                   feedforward=64, adapters=18, bottleneck=16, labels=4)


class TextTokenizer:
    """Train-only BPE with explicit vocabulary/truncation and saved provenance."""
    def __init__(self, tokenizer, training_ids: Sequence[str], requested_vocab: int, max_length: int):
        self.tokenizer = tokenizer
        self.training_ids = tuple(training_ids)
        self.requested_vocab = requested_vocab
        self.max_length = max_length

    @classmethod
    def fit(cls, records: Sequence[dict], vocab_size: int = 8192, max_length: int = 256) -> TextTokenizer:
        from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, trainers, processors
        if not records or any(record.get("split") != "train" for record in records):
            raise ValueError("Tokenizer fitting accepts only an explicit nonempty training partition")
        if len({record["id"] for record in records}) != len(records):
            raise ValueError("Training IDs must be unique")
        texts = [record["text"] for record in records]
        if any(not canonical_route_text(text) for text in texts):
            raise ValueError("Empty post-validation input")
        tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
        tokenizer.normalizer = normalizers.NFKC()
        tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
        trainer = trainers.BpeTrainer(vocab_size=vocab_size, min_frequency=1,
                                      special_tokens=["[PAD]", "[UNK]", "[BOS]", "[EOS]"], show_progress=False)
        tokenizer.train_from_iterator(texts, trainer=trainer)
        tokenizer.post_processor = processors.TemplateProcessing(
            single="[BOS] $A [EOS]", special_tokens=[("[BOS]", 2), ("[EOS]", 3)])
        # tokenizers subtracts the post-processor's two special tokens from this
        # total length, leaving at most 254 content tokens for a 256-token model.
        tokenizer.enable_truncation(max_length=max_length)
        tokenizer.enable_padding(length=max_length, pad_id=0, pad_token="[PAD]")
        return cls(tokenizer, [record["id"] for record in records], vocab_size, max_length)

    @property
    def vocab_size(self) -> int:
        return self.tokenizer.get_vocab_size()

    def encode(self, texts: Sequence[str]) -> tuple[torch.Tensor, torch.Tensor]:
        if not texts or any(not canonical_route_text(text) for text in texts):
            raise ValueError("Empty post-validation input or batch")
        encoded = self.tokenizer.encode_batch(list(texts))
        return (torch.tensor([value.ids for value in encoded], dtype=torch.long),
                torch.tensor([value.attention_mask for value in encoded], dtype=torch.bool))

    def save(self, path: Path) -> None:
        self.tokenizer.save(str(path))

    @classmethod
    def load(cls, path: Path, provenance_path: Path | None = None) -> TextTokenizer:
        """Restore a saved tokenizer only after checking its persisted provenance/hash."""
        from tokenizers import Tokenizer
        path = Path(path)
        provenance_path = Path(provenance_path) if provenance_path else path.with_name("tokenizer_provenance.json")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        encoded = path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != provenance.get("tokenizer_sha256"):
            raise ValueError("Saved tokenizer hash does not match provenance")
        ids = provenance.get("training_ids")
        if (not isinstance(ids, list) or not ids or any(not isinstance(value, str) or not value for value in ids)
                or len(set(ids)) != len(ids) or provenance.get("fit_splits") != ["train"]):
            raise ValueError("Saved tokenizer requires unique nonempty training-only provenance")
        maximum_length = provenance.get("maximum_length")
        requested_vocab = provenance.get("requested_vocab")
        if not isinstance(maximum_length, int) or maximum_length < 1 or not isinstance(requested_vocab, int) or requested_vocab < 2:
            raise ValueError("Invalid tokenizer vocabulary or truncation metadata")
        tokenizer = Tokenizer.from_str(encoded.decode("utf-8"))
        if (tokenizer.get_vocab_size() != provenance.get("actual_vocab")
                or not tokenizer.truncation or tokenizer.truncation.get("max_length") != maximum_length
                or not tokenizer.padding or tokenizer.padding.get("length") != maximum_length
                or tokenizer.padding.get("pad_id") != 0 or tokenizer.token_to_id("[PAD]") != 0):
            raise ValueError("Saved tokenizer configuration does not match provenance")
        return cls(tokenizer, ids, requested_vocab, maximum_length)


class EncoderBlock(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.norm1 = nn.LayerNorm(config.width, eps=config.norm_eps)
        self.attention = nn.MultiheadAttention(config.width, config.heads, dropout=config.dropout, batch_first=True)
        self.norm2 = nn.LayerNorm(config.width, eps=config.norm_eps)
        self.linear1 = nn.Linear(config.width, config.feedforward)
        self.linear2 = nn.Linear(config.feedforward, config.width)
        self.dropout1 = nn.Dropout(config.dropout)
        self.dropout2 = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
        y = self.norm1(x)
        attended = self.attention(y, y, y, key_padding_mask=~valid_mask, need_weights=False)[0]
        x = x + self.dropout1(attended)
        return x + self.dropout2(self.linear2(F.gelu(self.linear1(self.norm2(x)))))


class ResidualAdapter(nn.Module):
    def __init__(self, width: int, bottleneck: int):
        super().__init__()
        self.down = nn.Linear(width, bottleneck)
        self.up = nn.Linear(bottleneck, width)

    def forward(self, raw_pooled: torch.Tensor) -> torch.Tensor:
        return raw_pooled + self.up(F.relu(self.down(raw_pooled)))


class FrozenRoutingEncoder(nn.Module):
    """Immutable, eval-only post-warmup input representation for routing."""
    def __init__(self, source):
        super().__init__()
        self.config = source.config
        self.token_embedding = deepcopy(source.token_embedding)
        self.position_embedding = deepcopy(source.position_embedding)
        self.blocks = deepcopy(source.blocks)
        self.register_buffer("centroids", source.centroids.detach().clone())
        self.requires_grad_(False)
        self.eval()

    def train(self, mode=True):
        return super().train(False)

    @torch.no_grad()
    def forward(self, tokens, mask):
        raw = QPathTextModel.pooled(self, tokens, mask)
        norms = raw.norm(dim=1, keepdim=True)
        routes = (raw / norms.clamp_min(self.config.route_eps) @ self.centroids.T).argmax(1)
        return torch.where(norms[:, 0] < self.config.route_eps, 0, routes)


class QPathTextModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.width, padding_idx=config.pad_id)
        self.position_embedding = nn.Embedding(config.max_length, config.width)
        self.blocks = nn.ModuleList(EncoderBlock(config) for _ in range(config.layers))
        self.adapters = nn.ModuleList(ResidualAdapter(config.width, config.bottleneck) for _ in range(config.adapters))
        self.classifier = nn.Linear(config.width, config.labels)
        self.register_buffer("centroids", torch.zeros(config.adapters, config.width))
        self.register_buffer("random_route_probabilities", torch.full((config.adapters,), 1 / config.adapters, dtype=torch.float64))
        self.centroids_fitted = False
        self.centroid_training_ids: tuple[str, ...] = ()
        self.route_mode = "content"
        self.route_seed = 101
        self.frozen_router = None
        self.dispatch_mode = "grouped"
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for module in self.modules():
            if isinstance(module, (nn.Linear, nn.Embedding)):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if getattr(module, "bias", None) is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.MultiheadAttention):
                nn.init.normal_(module.in_proj_weight, mean=0.0, std=0.02)
                nn.init.zeros_(module.in_proj_bias)
        with torch.no_grad():
            self.token_embedding.weight[self.config.pad_id].zero_()
            for adapter in self.adapters:
                adapter.up.weight.zero_()
                adapter.down.bias.zero_()
                adapter.up.bias.zero_()

    def pooled(self, tokens: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
        if tokens.ndim != 2 or valid_mask.shape != tokens.shape or tokens.shape[1] > self.config.max_length:
            raise ValueError("tokens and mask must have the same [batch, time] shape within max_length")
        if tokens.shape[0] == 0 or tokens.shape[1] == 0 or not torch.all(valid_mask.any(dim=1)):
            raise ValueError("Empty post-validation input or batch")
        valid_mask = valid_mask.to(dtype=torch.bool)
        positions = torch.arange(tokens.shape[1], device=tokens.device)
        x = self.token_embedding(tokens) + self.position_embedding(positions)[None, :, :]
        for block in self.blocks:
            x = block(x, valid_mask)
        # UNK represents unknown content; structural PAD/BOS/EOS are not pooled.
        content_mask = valid_mask & (tokens != 0) & (tokens != 2) & (tokens != 3)
        if not torch.all(content_mask.any(dim=1)):
            raise ValueError("No non-special content tokens remain for pooling")
        weights = content_mask.unsqueeze(-1).to(x.dtype)
        return (x * weights).sum(dim=1) / weights.sum(dim=1)

    def select_routes(self, raw_pooled: torch.Tensor, texts: Sequence[str] | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        norm = torch.linalg.vector_norm(raw_pooled, dim=-1, keepdim=True)
        zero_flag = norm[:, 0] < self.config.route_eps
        if self.route_mode == "shared":
            routes = torch.zeros(raw_pooled.shape[0], device=raw_pooled.device, dtype=torch.long)
        elif self.route_mode == "random":
            if texts is None or len(texts) != raw_pooled.shape[0]:
                raise ValueError("Stable random routing requires the full original text per example")
            probabilities = self.random_route_probabilities.tolist()
            routes = torch.tensor([stable_text_route(text, self.route_seed, probabilities) for text in texts],
                                  device=raw_pooled.device, dtype=torch.long)
        elif self.route_mode == "content":
            if not self.centroids_fitted:
                raise RuntimeError("Content centroids must be fitted on training-only warm-up embeddings")
            unit = raw_pooled / norm.clamp_min(self.config.route_eps)
            routes = (unit @ self.centroids.T).argmax(dim=1)  # First index breaks ties.
        else:
            raise ValueError(f"Unknown route mode: {self.route_mode}")
        # Applies to every routing mode as a separately logged degenerate-input rule.
        routes = torch.where(zero_flag, torch.zeros_like(routes), routes)
        return routes, zero_flag

    def apply_adapters(self, raw_pooled: torch.Tensor, routes: torch.Tensor) -> torch.Tensor:
        if routes.shape != (raw_pooled.shape[0],) or torch.any(routes < 0) or torch.any(routes >= len(self.adapters)):
            raise ValueError("One valid adapter index per example is required")
        # Call only active modules. Separate Parameter objects plus grad=None
        # leave inactive AdamW weights AND moments unchanged, including decay.
        if self.dispatch_mode == "grouped":
            # Stack only active Parameter objects: an absent adapter keeps
            # grad=None, preserving its AdamW moments and weight decay state.
            active, inverse = torch.unique(routes, sorted=True, return_inverse=True)
            modules = [self.adapters[index] for index in active.tolist()]
            down_w = torch.stack([m.down.weight for m in modules])[inverse]
            down_b = torch.stack([m.down.bias for m in modules])[inverse]
            up_w = torch.stack([m.up.weight for m in modules])[inverse]
            up_b = torch.stack([m.up.bias for m in modules])[inverse]
            hidden = F.relu(torch.bmm(down_w, raw_pooled.unsqueeze(-1)).squeeze(-1) + down_b)
            return raw_pooled + torch.bmm(up_w, hidden.unsqueeze(-1)).squeeze(-1) + up_b
        if self.dispatch_mode != "loop":
            raise ValueError("Unknown adapter dispatch mode")
        result = torch.empty_like(raw_pooled)
        for index in torch.unique(routes, sorted=True).tolist():
            selected = routes == index
            result[selected] = self.adapters[index](raw_pooled[selected])
        return result

    def forward(self, tokens: torch.Tensor, valid_mask: torch.Tensor, texts: Sequence[str] | None = None,
                use_adapters: bool = True, routing_features: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        raw = self.pooled(tokens, valid_mask)
        if use_adapters:
            zero_flag = torch.linalg.vector_norm(raw, dim=-1) < self.config.route_eps
            if routing_features is not None:
                if self.route_mode not in ("frozen_content", "hash18"):
                    raise ValueError("Cached input-derived routes only apply to immutable routing modes")
                routes = routing_features
            elif self.route_mode == "frozen_content":
                if self.frozen_router is None:
                    raise ValueError("Frozen router is missing")
                routes = self.frozen_router(tokens, valid_mask)
            elif self.route_mode == "hash18":
                if texts is None:
                    raise ValueError("Hash routing requires original input text")
                routes = torch.tensor([stable_text_route(t, self.route_seed, [1 / self.config.adapters] * self.config.adapters)
                                       for t in texts], device=raw.device)
            else:
                routes, zero_flag = self.select_routes(raw, texts)
            representation = self.apply_adapters(raw, routes)
        else:
            routes = torch.full((raw.shape[0],), -1, dtype=torch.long, device=raw.device)
            zero_flag = torch.linalg.vector_norm(raw, dim=-1) < self.config.route_eps
            representation = raw
        return {"logits": self.classifier(representation), "routes": routes,
                "zero_norm": zero_flag, "raw_pooled": raw, "adapted": representation}

    def set_centroids(self, values: torch.Tensor, training_ids: Sequence[str]) -> None:
        if values.shape != self.centroids.shape or not torch.isfinite(values).all():
            raise ValueError("Centroid dimensions/values do not match the model")
        norms = torch.linalg.vector_norm(values, dim=1)
        if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5):
            raise ValueError("Every stored centroid must have unit norm")
        self.centroids.copy_(values.to(self.centroids))
        self.centroids_fitted = True
        self.centroid_training_ids = tuple(training_ids)


def adamw_optimizer(model: QPathTextModel, lr: float = 3e-4) -> torch.optim.AdamW:
    decay, no_decay = [], []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        # LayerNorm weights and all biases are one-dimensional in this model.
        (no_decay if parameter.ndim == 1 or name.endswith("bias") else decay).append(parameter)
    return torch.optim.AdamW([{"params": decay, "weight_decay": 0.01},
                             {"params": no_decay, "weight_decay": 0.0}],
                            lr=lr, betas=(0.9, 0.999), eps=1e-8)


def train_update(model: QPathTextModel, optimizer: torch.optim.Optimizer,
                 tokens: torch.Tensor, mask: torch.Tensor, labels: torch.Tensor,
                 texts: Sequence[str] | None = None, use_adapters: bool = True,
                 routing_features: torch.Tensor | None = None) -> tuple[float, torch.Tensor]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    output = model(tokens, mask, texts, use_adapters=use_adapters, routing_features=routing_features)
    loss = F.cross_entropy(output["logits"], labels)
    if not torch.isfinite(loss):
        raise FloatingPointError("Nonfinite training loss")
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    optimizer.step()
    return float(loss.detach()), output["routes"].detach()


def spherical_kmeans(embeddings: torch.Tensor, record_ids: Sequence[str], count: int,
                     seed: int, max_iterations: int = 100, tolerance: float = 1e-6) -> tuple[torch.Tensor, dict]:
    """Seeded spherical k-means++; ties/refill are stable by training record ID.

    k-means++ uses squared Euclidean distance between unit vectors, 2-2*cos.
    Clustering uses float64 locally, then stores float32 model centroids.
    """
    if embeddings.ndim != 2 or len(embeddings) != len(record_ids) or len(set(record_ids)) != len(record_ids):
        raise ValueError("Expected one unique training ID per embedding")
    norms = embeddings.norm(dim=1)
    keep = norms >= 1e-8
    if int(keep.sum()) < count or count < 1:
        raise ValueError("Insufficient nonzero training embeddings for requested centroid count")
    pairs = sorted((record_ids[i], i) for i in range(len(record_ids)) if bool(keep[i]))
    ids = [pair[0] for pair in pairs]
    array = embeddings[[pair[1] for pair in pairs]].detach().cpu().double().numpy()
    array /= np.linalg.norm(array, axis=1, keepdims=True)
    rng = np.random.Generator(np.random.PCG64(seed))
    chosen = [int(rng.integers(len(array)))]
    centers = [array[chosen[0]].copy()]
    while len(centers) < count:
        distance = np.clip(2 - 2 * array @ np.array(centers).T, 0, None).min(axis=1)
        distance[chosen] = 0
        if distance.sum() <= 1e-15:
            index = next(i for i in range(len(array)) if i not in chosen)
        else:
            index = int(rng.choice(len(array), p=distance / distance.sum()))
        chosen.append(index)
        centers.append(array[index].copy())
    centers = np.array(centers)
    empty_refills = 0
    displacement = float("inf")
    for iteration in range(1, max_iterations + 1):
        similarities = array @ centers.T
        assignments = similarities.argmax(axis=1)
        next_centers = centers.copy()
        refill_order = np.argsort(-np.clip(2 - 2 * similarities.max(axis=1), 0, None), kind="stable")
        refill_used: set[int] = set()
        for index in range(count):
            points = array[assignments == index]
            mean = points.mean(axis=0) if len(points) else np.zeros(array.shape[1])
            norm = np.linalg.norm(mean)
            if norm < 1e-12:
                candidate = next(int(i) for i in refill_order if int(i) not in refill_used)
                refill_used.add(candidate)
                next_centers[index] = array[candidate]
                empty_refills += 1
            else:
                next_centers[index] = mean / norm
        displacement = float(np.linalg.norm(next_centers - centers, axis=1).max())
        centers = next_centers
        if displacement < tolerance:
            break
    return torch.from_numpy(centers).to(dtype=embeddings.dtype, device=embeddings.device), {
        "algorithm": "spherical-kmeans++", "initial_distance": "squared Euclidean on unit sphere",
        "seed": seed, "iterations": iteration, "max_iterations": max_iterations,
        "final_displacement": displacement, "tolerance": tolerance, "empty_refills": empty_refills,
        "excluded_zero_norm_ids": [record_ids[i] for i in range(len(record_ids)) if not bool(keep[i])],
        "training_ids": ids,
    }


@torch.no_grad()
def fit_training_centroids(model: QPathTextModel, tokenizer: TextTokenizer, records: Sequence[dict],
                           seed: int, batch_size: int = 64) -> dict:
    if not records or any(record.get("split") != "train" for record in records):
        raise ValueError("Centroid fitting accepts only explicit training records")
    model.eval()
    vectors = []
    for start in range(0, len(records), batch_size):
        tokens, mask = tokenizer.encode([record["text"] for record in records[start:start + batch_size]])
        vectors.append(model.pooled(tokens, mask))
    embeddings = torch.cat(vectors)
    ids = [record["id"] for record in records]
    centroids, manifest = spherical_kmeans(embeddings, ids, model.config.adapters, seed)
    model.set_centroids(centroids, ids)
    routes, _ = model.select_routes(embeddings)
    counts = torch.bincount(routes, minlength=model.config.adapters).double()
    model.random_route_probabilities.copy_(counts / counts.sum())
    manifest["route_counts"] = counts.long().tolist()
    manifest["random_route_probabilities"] = model.random_route_probabilities.tolist()
    return manifest


def parameter_counts(model: QPathTextModel, active_routes: Sequence[int]) -> dict[str, int]:
    active = set(active_routes)
    total = sum(p.numel() for p in model.parameters())
    adapter_total = sum(p.numel() for module in model.adapters for p in module.parameters())
    active_adapter = sum(p.numel() for i in active for p in model.adapters[i].parameters())
    return {"total": total, "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad),
            "active_for_observed_batch": total - adapter_total + active_adapter,
            "parameter_bytes": sum(p.numel() * p.element_size() for p in model.parameters())}
