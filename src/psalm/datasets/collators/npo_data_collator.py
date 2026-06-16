from typing import Dict, List, Any, Optional

import torch
from transformers import PreTrainedTokenizerBase

EOT_TOKEN = "<|eot_id|>"


def _find_subsequence_positions(sequence: List[int], pattern: List[int]) -> int:
    """Return start index of first occurrence of pattern in sequence, or -1."""
    n, m = len(sequence), len(pattern)
    if m == 0 or m > n:
        return -1
    for i in range(n - m + 1):
        if sequence[i : i + m] == pattern:
            return i
    return -1


class NPODataCollator:
    """
    - Tokenizes the 'text' field (already rendered with the chat template).
    - Builds a boolean response_mask indicating assistant answer tokens.
    - Carries 'is_forget' as tensor.
    - Uses dynamic padding via tokenizer.
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizerBase,
        response_part_text: str,
        pad_to_multiple_of: Optional[int] = None,
    ):
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of

        # Token pattern for the assistant response header.
        self.response_part_ids: List[int] = self.tokenizer.encode(
            response_part_text, add_special_tokens=False
        )

        eot_id = self.tokenizer.convert_tokens_to_ids(EOT_TOKEN)
        if eot_id is None:
            eot_id = int(self.tokenizer.eos_token_id)
        self.eot_id: int = eot_id

    def __call__(self, examples: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        texts = [ex["text"] for ex in examples]
        is_forget = [int(ex["is_forget"]) for ex in examples]

        batch = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )

        input_ids = batch["input_ids"]
        attention_mask = batch["attention_mask"]

        resp_masks = []
        with torch.no_grad():
            for i in range(input_ids.size(0)):
                ids = input_ids[i].tolist()

                start = _find_subsequence_positions(ids, self.response_part_ids)
                if start == -1:
                    # No header found; no response region.
                    resp_masks.append(torch.zeros_like(input_ids[i], dtype=torch.bool))
                    continue

                resp_start = start + len(self.response_part_ids)
                try:
                    resp_end = ids.index(self.eot_id, resp_start)
                except ValueError:
                    resp_end = len(ids)

                mask = torch.zeros_like(input_ids[i], dtype=torch.bool)
                mask[resp_start:resp_end] = True
                resp_masks.append(mask)

        response_mask = torch.stack(resp_masks, dim=0)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "response_mask": response_mask,
            "is_forget": torch.tensor(is_forget, dtype=torch.long),
        }