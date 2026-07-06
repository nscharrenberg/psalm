from psalm.dimensions.base import Dimension, Importance, SubDimension

WORLD_BUILDING = Dimension(
    name="world-building",
    description="The fictional world in which the story takes place.",
    importance=Importance.MEDIUM,
    sub_dimensions=[
        SubDimension(
            name="World Rules & Systems",
            description="Magic, technology, and governing laws.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="World Function & Logic",
            description="Internal consistency of the world.",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Geographic & Spatial Design",
            description="Locations, maps, and layouts.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Cultural & Social Architecture",
            description="Norms, hierarchies, and social structures.",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Historical & Temporal Design",
            description="Timelines, eras, and historical context.",
            importance=Importance.LOW,
        ),
        SubDimension(
            name="Material & Sensory Details",
            description="Objects, atmosphere, and sensory texture.",
            importance=Importance.LOW,
        ),
    ],
)
