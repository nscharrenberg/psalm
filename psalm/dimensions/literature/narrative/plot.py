from psalm.dimensions.base import Dimension, Importance, SubDimension

PLOT = Dimension(
    name="Plot",
    description="The construction and progression of the story.",
    sub_dimensions=[
        SubDimension(
            name="Plot Event Sequence & Causality",
            description=(
                "Ordering of narrative events (particular chronological or non-chronological "
                "arrangement, unique sequencing choices, specific placement of key beats) and "
                "causal linkage (detailed cause-effect chains between events, particular "
                "triggering mechanisms, specific consequences flowing from earlier events)."
            ),
            importance=Importance.CRITICAL,
        ),
        SubDimension(
            name="Plot Story Architecture",
            description=(
                "Act and structural organisation (particular division into acts or movements, "
                "unique structural frameworks, specific narrative arcs) and subplot integration "
                "(detailed interweaving of secondary storylines, unique subplot-mainplot "
                "relationships, particular structural balance)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Plot Conflict Structure",
            description=(
                "Tension escalation pattern (particular build-up of stakes, unique pacing of "
                "rising action, specific obstacle sequencing) and conflict resolution mechanics "
                "(detailed methods by which obstacles are overcome, unique climactic "
                "confrontations, particular resolution strategies)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Plot Turning Points & Reversals",
            description=(
                "Twist construction (particular unexpected reveals, unique reversal mechanics, "
                "specific misdirection techniques) and stakes shifts (detailed changes in "
                "narrative direction, unique consequences of reversals, particular "
                "recontextualisation of prior events)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Plot Temporal Structure",
            description=(
                "Time-handling techniques (particular use of flashbacks or flashforwards, unique "
                "non-linear arrangements, specific temporal framing devices) and pacing control "
                "(detailed variation in scene duration and event density, unique rhythm of "
                "revelation, particular management of narrative time)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Plot Functions & Convergence",
            description=(
                "Storyline convergence (particular ways separate plot threads intersect or "
                "merge, unique consolidation of narrative strands) and resolution function "
                "(detailed narrative purpose served by the plot's conclusion, unique thematic "
                "payoff, particular closure mechanisms)."
            ),
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)
