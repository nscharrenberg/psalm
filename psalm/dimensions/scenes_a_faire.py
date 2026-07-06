from psalm.dimensions.base import Dimension, Importance, SubDimension

SCENES_A_FAIRE = Dimension(
    name="scenes-a-faire",
    description="Stock elements that are not copyright-protected.",
    importance=Importance.MEDIUM,
    sub_dimensions=[
        SubDimension(
            name="Genre Conventions & Setting",
            description="Standard genre elements used.",
            importance=Importance.CRITICAL,
        ),
        SubDimension(
            name="Standard Characters & Archetypes",
            description="Whether characters are clichéd archetypes.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Standard Plot Devices & Tropes",
            description="Use of clichéd storylines.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Thematic Commonplaces",
            description="Whether themes are generic.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Necessary Technical Elements",
            description="Functionally necessary elements.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Creative Elaboration",
            description="How much original elaboration exists.",
            importance=Importance.LOW,
        ),
    ],
)
