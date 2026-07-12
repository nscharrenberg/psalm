from psalm.dimensions.base import Dimension, Importance, SubDimension

PARODY_SATIRE = Dimension(
    name="Parody/Satire",
    description="How original works are transformed for comedic or critical effect.",
    sub_dimensions=[
        SubDimension(
            name="Transformative Nature",
            description="Particular transformations (unique reinterpretations, specific creative modifications, detailed subversive adaptations) and new expression (unique comedic twists, specific satirical recontextualizations, particular parody frameworks).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Social Commentary",
            description="Specific critical engagement (unique societal observations, particular institutional critiques, detailed cultural commentary) and thematic depth (unique satirical targets, specific moral or ethical points, particular social insights).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Humorous Intent",
            description="Clear comedic purpose (unique humorous elements, specific parody markers, detailed satirical tone) and comedic technique (particular comedic devices, unique timing, specific delivery styles).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Imitation & Exaggeration",
            description="Particular mimicked elements (unique stylistic reproductions, specific structural parallels, detailed formal imitations) and unique exaggerated features (specific hyperbolic distortions, particular caricatured representations, detailed satirical amplifications).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Recognition & Differentiation",
            description="Specific recognizable references (unique allusions, particular intertextual links, detailed source acknowledgments) and unique differentiation from original (specific parody signals, particular satirical distance, detailed transformative indicators).",
            importance=Importance.MEDIUM,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="exception",
)