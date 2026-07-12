from psalm.dimensions.base import Dimension, Importance, SubDimension

PASTICHE = Dimension(
    name="Pastiche",
    description="How multiple styles and elements are blended as artistic homage.",
    sub_dimensions=[
        SubDimension(
            name="Stylistic Blending",
            description=(
                "Particular style combinations (unique fusion patterns, specific eclectic "
                "elements, detailed hybrid techniques) and creative synthesis (unique stylistic "
                "harmonies, specific integrated influences, particular cohesive mixtures)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Artistic Homage",
            description=(
                "Distinctive tribute elements (unique respectful references, specific homage "
                "indicators, detailed appreciative allusions) and creative reverence (unique "
                "artistic acknowledgments, specific inspirational debts, particular stylistic "
                "nods)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Style Imitation",
            description=(
                "Specific imitated styles (unique period-appropriate elements, particular "
                "historical reproductions, detailed stylistic echoes) and authentic recreation "
                "(unique genre faithfulness, specific technical accuracy, particular stylistic "
                "precision)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Period Elements",
            description=(
                "Particular historical references (unique era-specific details, specific temporal "
                "markers, detailed period authenticity) and contextual accuracy (unique cultural "
                "verisimilitude, specific historical fidelity, particular epochal details)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Creative Transformation",
            description=(
                "Specific creative adaptations (unique reinterpretations, particular artistic "
                "modifications, detailed innovative reworkings) and original integration (unique "
                "synthesis of influences, specific transformative contributions, particular "
                "creative reimaginings)."
            ),
            importance=Importance.MEDIUM,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="exception",
)