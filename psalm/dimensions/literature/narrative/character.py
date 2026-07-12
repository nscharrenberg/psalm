from psalm.dimensions.base import Dimension, Importance, SubDimension

CHARACTER = Dimension(
    name="Character",
    description="How characters are developed and expressed.",
    sub_dimensions=[
        SubDimension(
            name="Character Identity & Traits",
            description=(
                "Distinctive personality traits (unique quirks, contradictions, creative "
                "elaborations beyond archetypes), physical & behavioral specificity (unique "
                "features, mannerisms, gestures, idiosyncratic behaviors), and psychological "
                "complexity (multi-layered internal conflicts, contradictory emotions, nuanced "
                "psychological states, specific defense mechanisms)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Character Arc & Development",
            description=(
                "Transformation pattern (specific catalysts, unique stages, internal shifts, "
                "detailed trajectory of change) and internal conflict structure (particular "
                "manifestations, unique opposing forces, detailed psychological stakes, specific "
                "triggers and resolutions)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Character Relationships & Dynamics",
            description=(
                "Relationship constellation (network structure, particular dynamics, unique power "
                "balances, detailed emotional textures) and interaction patterns (specific "
                "communication styles, unique behavioral patterns in social contexts, detailed "
                "conflict/cooperation methods)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Character Background & Motivation",
            description=(
                "Backstory specificity (detailed personal history, particular events, unique "
                "formative experiences, specific causal connections to present) and motivational "
                "structure (detailed goal hierarchies, particular value systems, unique desire "
                "configurations, specific origins and manifestations)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Character Expression & Behavior",
            description=(
                "Behavioral signatures (specific action patterns, decision-making processes, "
                "unique habits, distinctive rituals) and emotional response patterns (particular "
                "triggers, unique coping mechanisms, specific emotional sequences, detailed "
                "manifestations)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Character Function & Role",
            description=(
                "Narrative function (specific plot roles, unique responsibilities, particular "
                "narrative mechanisms) and agency & autonomy level (patterns of character agency, "
                "constraints, evolution)."
            ),
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)
