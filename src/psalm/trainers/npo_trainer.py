import unsloth  # Ensure Unsloth patches are applied before transformers
from typing import Optional, Dict, Any

import torch
import torch.nn.functional as F
from transformers import Trainer, PreTrainedModel, PreTrainedTokenizerBase

from psalm.configs.training.npo_config import NPOConfig


def _masked_mean_logp(
    logits: torch.Tensor,
    input_ids: torch.Tensor,
    response_mask: torch.Tensor,
    length_normalize: bool = True,
) -> torch.Tensor:
    """
    Compute per-example mean log p for response tokens only (teacher forcing).
    - logits: [B, T, V]
    - input_ids: [B, T]
    - response_mask: [B, T] bool
    Returns: [B] tensor.
    """
    shift_logits = logits[:, :-1, :]
    shift_labels = input_ids[:, 1:]
    shift_mask = response_mask[:, 1:].to(shift_logits.dtype)

    log_probs = F.log_softmax(shift_logits, dim=-1)
    token_logp = log_probs.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
    token_logp = token_logp * shift_mask

    token_counts = shift_mask.sum(dim=1).clamp_min(1.0)
    sum_logp = token_logp.sum(dim=1)
    if length_normalize:
        return sum_logp / token_counts
    else:
        return sum_logp


class NPOTrainer(Trainer):
    """
    Trainer that applies NPO loss on forget examples and an optional retain
    objective (SFT CE or KL) on retain examples.
    """

    def __init__(
        self,
        reference_model: PreTrainedModel,
        tokenizer: PreTrainedTokenizerBase,
        npo_config: NPOConfig,
        retain_objective: Optional[str] = None,
        retain_weight: Optional[float] = None,
        **kwargs: Any,
    ):
        # Force remove_unused_columns off since we rely on a custom collator
        if "args" in kwargs and kwargs["args"] is not None:
            try:
                kwargs["args"].remove_unused_columns = False
            except Exception:
                pass

        super().__init__(**kwargs)

        # Double safety after init
        try:
            self.args.remove_unused_columns = False
        except Exception:
            pass

        self.ref_model = reference_model.eval()
        for p in self.ref_model.parameters():
            p.requires_grad_(False)

        self.tokenizer = tokenizer
        self.cfg = npo_config
        self.retain_objective = (
            retain_objective if retain_objective is not None else self.cfg.retain_objective
        )
        self.retain_weight = (
            float(retain_weight) if retain_weight is not None else float(self.cfg.retain_weight)
        )

    def compute_loss(
        self,
        model: PreTrainedModel,
        inputs: Dict[str, torch.Tensor],
        return_outputs: bool = False,
        num_items_in_batch: Optional[int] = None,
        **kwargs: Any,
    ):
        # Unsloth may pass num_items_in_batch; we ignore it.
        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]
        response_mask = inputs["response_mask"]
        is_forget = inputs["is_forget"]  # 1 forget, 0 retain

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            use_cache=False,
        )
        logits = outputs.logits

        with torch.no_grad():
            ref_out = self.ref_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=False,
            )
            ref_logits = ref_out.logits

        logp = _masked_mean_logp(
            logits,
            input_ids,
            response_mask=response_mask,
            length_normalize=self.cfg.length_normalize,
        )
        logp_ref = _masked_mean_logp(
            ref_logits,
            input_ids,
            response_mask=response_mask,
            length_normalize=self.cfg.length_normalize,
        )

        forget_mask = is_forget == 1
        retain_mask = is_forget == 0

        total_loss = torch.tensor(0.0, device=logits.device)

        # NPO: softplus(beta * (logp - logp_ref)) on forget examples
        if forget_mask.any():
            adv = (logp - logp_ref)[forget_mask]
            if self.cfg.clamp_adv_abs is not None:
                clamp = float(self.cfg.clamp_adv_abs)
                adv = adv.clamp(min=-clamp, max=clamp)
            npo_loss = F.softplus(self.cfg.beta * adv).mean()
            total_loss = total_loss + npo_loss

        # Retain objective
        if retain_mask.any() and self.retain_objective != "none":
            if self.retain_objective == "sft_ce":
                shift_logits = logits[:, :-1, :]
                shift_labels = input_ids[:, 1:]
                shift_mask = response_mask[:, 1:].to(shift_logits.dtype)

                ce_per_token = F.cross_entropy(
                    shift_logits.reshape(-1, shift_logits.size(-1)),
                    shift_labels.reshape(-1),
                    reduction="none",
                ).view(shift_labels.size())

                ce_per_token = ce_per_token * shift_mask

                token_counts = shift_mask.sum(dim=1).clamp_min(1.0)
                ce_per_example = ce_per_token.sum(dim=1) / token_counts

                retain_loss = ce_per_example[retain_mask].mean()

            elif self.retain_objective == "kl":
                pol = F.log_softmax(logits[:, :-1, :], dim=-1)
                ref = F.log_softmax(ref_logits[:, :-1, :], dim=-1)
                p = pol.exp()
                kl_per_token = (p * (pol - ref)).sum(-1)
                shift_mask = response_mask[:, 1:].to(kl_per_token.dtype)
                kl_per_token = kl_per_token * shift_mask
                token_counts = shift_mask.sum(dim=1).clamp_min(1.0)
                kl_per_example = kl_per_token.sum(dim=1) / token_counts
                retain_loss = kl_per_example[retain_mask].mean()

            else:
                raise ValueError(f"Unknown retain_objective: {self.retain_objective}")

            total_loss = total_loss + self.retain_weight * retain_loss

        if return_outputs:
            return total_loss, outputs
        return total_loss