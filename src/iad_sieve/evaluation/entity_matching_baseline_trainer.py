"""实体匹配 cross-encoder checkpoint 训练模块。"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from iad_sieve.evaluation.entity_matching_baseline_runner import _document_text
from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntityMatchingTrainingExample:
    """实体匹配训练样本。"""

    left_text: str
    right_text: str
    label: int


def _pair_label(value: object) -> int | None:
    """解析 pair 标签。

    参数:
        value: 原始标签值。

    返回:
        0/1 标签；无法解析时返回 None。
    """
    if isinstance(value, bool):
        return int(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "same", "same_work", "match", "duplicate"}:
        return 1
    if normalized in {"0", "false", "no", "n", "different", "non_match", "unrelated"}:
        return 0
    return None


def build_entity_matching_training_examples(
    documents: list[dict],
    pairs: list[dict],
    *,
    train_split: str = "train",
    split_field: str = "split",
    label_field: str = "same_work",
) -> tuple[list[EntityMatchingTrainingExample], dict]:
    """构造实体匹配 cross-encoder 训练样本。

    参数:
        documents: 文献记录。
        pairs: pair 记录。
        train_split: 训练 split；为空字符串时使用全部 pair。
        split_field: split 字段名。
        label_field: 标签字段名。

    返回:
        训练样本列表和样本构造摘要。
    """
    document_lookup = {str(record.get("document_id", "")): record for record in documents}
    examples: list[EntityMatchingTrainingExample] = []
    skipped_split_count = 0
    missing_document_count = 0
    missing_label_count = 0
    for pair in pairs:
        if train_split and str(pair.get(split_field, "")) != train_split:
            skipped_split_count += 1
            continue
        source_document_id = str(pair.get("source_document_id", ""))
        target_document_id = str(pair.get("target_document_id", ""))
        left_document = document_lookup.get(source_document_id)
        right_document = document_lookup.get(target_document_id)
        if left_document is None or right_document is None:
            missing_document_count += 1
            continue
        label = _pair_label(pair.get(label_field))
        if label is None:
            missing_label_count += 1
            continue
        examples.append(
            EntityMatchingTrainingExample(
                left_text=_document_text(left_document),
                right_text=_document_text(right_document),
                label=label,
            )
        )
    summary = {
        "document_count": len(documents),
        "pair_count": len(pairs),
        "training_pair_count": len(examples),
        "skipped_split_count": skipped_split_count,
        "missing_document_count": missing_document_count,
        "missing_label_count": missing_label_count,
        "train_split": train_split,
        "split_field": split_field,
        "label_field": label_field,
    }
    return examples, summary


def _collate_entity_matching_batch(tokenizer: Any, examples: list[EntityMatchingTrainingExample], max_length: int) -> dict:
    """构造 PyTorch batch。

    参数:
        tokenizer: transformers tokenizer。
        examples: 训练样本。
        max_length: 最大 token 长度。

    返回:
        模型输入 batch。
    """
    import torch

    encoded = tokenizer(
        [example.left_text for example in examples],
        [example.right_text for example in examples],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    encoded["labels"] = torch.tensor([example.label for example in examples], dtype=torch.long)
    return encoded


def train_entity_matching_baseline(
    documents: list[dict],
    pairs: list[dict],
    *,
    output_dir: str | Path,
    system_name: str,
    base_model_name: str = "textattack/roberta-base-MRPC",
    train_split: str = "train",
    split_field: str = "split",
    label_field: str = "same_work",
    batch_size: int = 8,
    epochs: int = 1,
    learning_rate: float = 2e-5,
    max_length: int = 512,
    seed: int = 42,
) -> dict:
    """训练实体匹配 cross-encoder checkpoint。

    参数:
        documents: 文献记录。
        pairs: pair 记录。
        output_dir: checkpoint 输出目录。
        system_name: 训练系统名称。
        base_model_name: Hugging Face 序列分类 base model。
        train_split: 训练 split；为空字符串时使用全部 pair。
        split_field: split 字段名。
        label_field: 标签字段名。
        batch_size: 训练批大小。
        epochs: 训练 epoch 数。
        learning_rate: 学习率。
        max_length: 最大 token 长度。
        seed: 随机种子。

    返回:
        训练摘要。
    """
    examples, summary = build_entity_matching_training_examples(
        documents,
        pairs,
        train_split=train_split,
        split_field=split_field,
        label_field=label_field,
    )
    if not examples:
        raise ValueError("实体匹配训练样本为空，无法训练 checkpoint")

    try:
        import torch
        from torch.utils.data import DataLoader
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except Exception as exc:  # pragma: no cover - 依赖缺失由远程预检覆盖
        LOGGER.exception("实体匹配训练依赖不可用")
        raise RuntimeError(f"实体匹配训练依赖不可用: {exc}") from exc

    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    model = AutoModelForSequenceClassification.from_pretrained(base_model_name, num_labels=2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    data_loader = DataLoader(
        examples,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=lambda batch: _collate_entity_matching_batch(tokenizer, list(batch), max_length=max_length),
    )
    loss_total = 0.0
    step_count = 0
    for _ in range(epochs):
        for batch in data_loader:
            batch = {name: value.to(device) for name, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            loss_total += float(loss.detach().cpu())
            step_count += 1

    checkpoint_dir = ensure_directory(output_dir)
    model.save_pretrained(checkpoint_dir)
    tokenizer.save_pretrained(checkpoint_dir)
    training_summary = {
        **summary,
        "system": system_name,
        "base_model_name": base_model_name,
        "output_dir": str(output_dir),
        "execution_mode": "actual_model",
        "model_backend": "transformers",
        "device": str(device),
        "batch_size": batch_size,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "seed": seed,
        "step_count": step_count,
        "mean_training_loss": round(loss_total / step_count, 6) if step_count else 0.0,
    }
    LOGGER.info(
        "实体匹配 checkpoint 训练完成: system=%s output_dir=%s examples=%s steps=%s",
        system_name,
        output_dir,
        len(examples),
        step_count,
    )
    return training_summary


def write_entity_matching_training_summary(summary: dict, summary_path: str | Path) -> None:
    """写出实体匹配训练摘要。

    参数:
        summary: 训练摘要。
        summary_path: JSONL 输出路径。

    返回:
        无。
    """
    write_records([summary], summary_path)
