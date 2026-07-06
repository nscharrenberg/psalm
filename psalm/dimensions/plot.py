from psalm.dimensions.base import Dimension, Importance, SubDimension

PLOT = Dimension(
    name="plot",
    description="The construction and progression of the story.",
    importance=Importance.HIGH,
    sub_dimensions=[
        SubDimension(
            name="Event Sequence & Causality",
            description="Order and causal links between events.",
            importance=Importance.CRITICAL,
        ),
        SubDimension(
            name="Story Architecture",
            description="Acts, subplots, and structural organisation.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Conflict Structure",
            description="Tension build-up and obstacles.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Turning Points & Reversals",
            description="Plot twists and reversals.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Temporal Structure",
            description="Flashbacks, pacing, and time handling.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Plot Functions & Convergence",
            description="How plot lines meet and resolve.",
            importance=Importance.LOW,
        ),
    ],
)
