from psalm.dimensions.base import Dimension, Importance, SubDimension

WORLD_BUILDING = Dimension(
    name="World Building",
    description="How the fictional world is created and defined.",
    sub_dimensions=[
        SubDimension(
            name="Cultural & Social Architecture",
            description=(
                "Cultural specificity (particular customs, unique traditions, specific social "
                "norms, detailed cultural practices) and social structure elaboration (particular "
                "hierarchies, unique power dynamics, specific relationship networks, detailed "
                "social institutions)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="World Rules & Systems",
            description=(
                "System mechanics (particular rules governing the world, unique operational "
                "principles, specific constraints and possibilities) and rule limitations & "
                "constraints (detailed boundaries of what is possible, unique exceptions, specific "
                "consequences of rule-breaking)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Geographic & Spatial Design",
            description=(
                "Geographic specificity (particular locations, unique landscapes, specific spatial "
                "relationships) and environmental specificity (detailed climates, unique "
                "ecosystems, specific atmospheric conditions, particular sensory details of "
                "settings)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Material & Sensory Detail",
            description=(
                "Material specificity (particular objects, unique substances, specific textures, "
                "detailed material properties) and sensory elaboration (unique sounds, specific "
                "smells, particular tactile experiences, detailed visual descriptions)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Historical & Temporal Design",
            description=(
                "Historical specificity (particular historical events, unique timelines, specific "
                "era details) and temporal patterns (detailed time flows, unique temporal "
                "anomalies, specific cause-effect relationships across time)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="World Function & Logic",
            description=(
                "World purpose (particular narrative or thematic role of the world, unique "
                "functional contributions) and internal logic consistency (specific consistency of "
                "rules, unique coherence of systems, detailed logical frameworks)."
            ),
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)
