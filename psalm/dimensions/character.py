from psalm.dimensions.base import Dimension, Importance, SubDimension

CHARACTER = Dimension(
    name="character",
    description="How characters are developed and expressed.",
    importance=Importance.HIGH,
    sub_dimensions=[
        SubDimension(
            name="Identity & Properties",
            description="Distinctive personality traits (unique quirks, contradictions, creative elaborations), physical & behavioral specificity (unique features, mannerisms, gestures), and psychological complexity (multi-layered conflicts, defense mechanisms).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Character Arc & Development",
            description="Transformation pattern (specific catalysts, unique stages, internal shifts) and internal conflict structure (unique opposing forces, detailed stakes, specific triggers).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Relationships & Dynamics",
            description="Relationship constellation (unique power balances, detailed emotional textures) and interaction patterns (specific communication styles, unique behavioral patterns).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Background & Motivation",
            description="Backstory specificity (particular events, unique formative experiences) and motivational structure (detailed goal hierarchies, specific value systems).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Expression & Behaviour",
            description="Behavioral signatures (specific action patterns, unique habits, rituals) and emotional response patterns (particular triggers, coping mechanisms).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Function & Role",
            description="Narrative function (specific plot roles, unique responsibilities) and agency & autonomy level (particular patterns of agency, constraints).",
            importance=Importance.LOW,
        ),
    ],
)
