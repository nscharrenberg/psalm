from psalm.dimensions.base import Dimension, Importance, SubDimension

CHARACTER = Dimension(
    name="character",
    description="How characters are developed and expressed.",
    importance=Importance.HIGH,
    sub_dimensions=[
        SubDimension(
            name="Identity & Properties",
            description="Unique traits and characteristics.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Character Development",
            description="Growth and change over the narrative.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Relationships & Dynamics",
            description="Interactions with other characters.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Background & Motivation",
            description="Backstory and driving forces.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Expression & Behaviour",
            description="Manner of acting and speaking.",
            importance=Importance.LOW,
        ),
        SubDimension(
            name="Function & Role",
            description="Narrative role (e.g. hero, antagonist).",
            importance=Importance.LOW,
        ),
    ],
)
