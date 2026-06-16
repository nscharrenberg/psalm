from dataclasses import dataclass, field
from enum import StrEnum

from psalm.ui.demo.state import TargetText, CopyrightText


class Severity(StrEnum):
    NEAR_IDENTICAL = "Identical or near-identical writing style across all dimensions"
    VERY_SIMILAR = "Very similar writing style with only minor differences"
    BORDERLINE = "Moderately similar writing style with some notable differences"
    DIFFERENT = "Somewhat different writing style with limited similarities"
    EXTREMELY_DIFFERENT = "Clearly different or opposite writing styles"

@dataclass
class ExampleTextVariant:
    severity: Severity
    text: TargetText = field(default_factory=lambda: TargetText())

@dataclass
class ExampleText:
    key: str
    name: str
    copyright_text: CopyrightText = field(default_factory=lambda: CopyrightText())
    variants: list[ExampleTextVariant] = field(default_factory=list)

import json
from pathlib import Path


def get_examples() -> list[ExampleText]:
    """Load example texts from the examples.json file.
    
    Returns:
        A list of ExampleText objects, each containing a copyright text and its variants
        with different severity levels of similarity.
    """
    examples_file = Path(__file__).parent / "examples.json"
    
    with open(examples_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    example_texts = []
    
    for example_data in data.get("examples", []):
        # Create the copyright text from the source
        source = example_data.get("source", {})
        copyright_text = CopyrightText(
            title=source.get("title", ""),
            author=source.get("author", ""),
            text=source.get("text", "")
        )
        
        # Create variants from the variants list
        variants = []
        for variant_data in example_data.get("variants", []):
            variant_text_data = variant_data.get("text", {})
            target_text = TargetText(
                title=source.get("title", ""),
                author=source.get("author", ""),
                text=variant_text_data.get("text", "") if type(variant_text_data) is dict else variant_text_data
            )
            
            # Map expected_score to severity
            text_similarity = variant_data.get("text_similarity", "")
            severity = _score_to_severity(variant_data.get("expected_score", 0.5))
            
            variants.append(ExampleTextVariant(
                severity=severity,
                text=target_text
            ))
        
        example_texts.append(ExampleText(
            key=example_data.get("control_case", ""),
            name=example_data.get("control_case", ""),
            copyright_text=copyright_text,
            variants=variants
        ))
    
    return example_texts


def _score_to_severity(score: float) -> Severity:
    """Map a similarity score to a Severity level.
    
    Args:
        score: The similarity score (0.0 to 1.0)
        
    Returns:
        The corresponding Severity level
    """
    if score >= 0.9:
        return Severity.NEAR_IDENTICAL
    elif score >= 0.7:
        return Severity.VERY_SIMILAR
    elif score >= 0.4:
        return Severity.BORDERLINE
    elif score >= 0.2:
        return Severity.DIFFERENT
    else:
        return Severity.EXTREMELY_DIFFERENT