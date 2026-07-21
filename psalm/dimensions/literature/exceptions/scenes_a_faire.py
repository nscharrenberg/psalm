from psalm.dimensions.base import Dimension, Importance, SubDimension

SCENES_A_FAIRE = Dimension(
    name="Scènes à Faire",
    description="Standard or necessary elements indispensable to the genre or type of work.",
    sub_dimensions=[
        SubDimension(
            name="Creative Elaboration",
            description=(
                "Distinctive voice/style (unique authorial tone, specific creative expression "
                "patterns), original descriptive detail (particular sensory richness, unique "
                "observational depth), psychological depth (complex character interiority, "
                "specific emotional nuance), unique dialogue (particular speech patterns, specific "
                "conversational styles), innovative structure (unique narrative architectures, "
                "specific formal experiments), creative worldbuilding (particular imaginative "
                "constructions, unique setting details)."
            ),
            importance=Importance.HIGH,
            # HIGH textual similarity here means the shared passage is highly original/creatively
            # elaborate -- the strongest possible infringement signal, not scenes-à-faire
            # material. _compute_weighted_score (psalm/phases/deliberation.py) flips this
            # sub-dimension's contribution accordingly. The juror is never told about this --
            # it scores this sub-dimension exactly like any other, using the same
            # pure-textual-similarity rubric (_VOTE_SYSTEM_PROMPT in psalm/agents/juror.py);
            # the inversion is applied only during aggregation, in code.
            inverse=True,
        ),
        SubDimension(
            name="Genre Conventions & Setting",
            description=(
                "Genre-specific plot elements (particular narrative tropes typical of the genre, "
                "unique structural expectations) and standard settings & worldbuilding (specific "
                "environmental clichés, particular background elements common to the genre)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Thematic Commonplaces",
            description=(
                "Standard themes (particular recurring ideas, unique universal concepts) and "
                "conventional conflicts (specific typical struggles, particular archetypal "
                "tensions)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Standard Plot Devices & Tropes",
            description=(
                "Common plot devices (particular narrative shortcuts, unique storytelling "
                "conventions) and narrative tropes (specific recurring motifs, particular genre "
                "staples)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Stock Characters & Archetypes",
            description=(
                "Character archetypes (particular standard character types, unique role templates) "
                "and standard relationships (specific typical character dynamics, particular "
                "conventional pairings)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Necessary Technical Elements",
            description=(
                "Genre-required elements (particular mandatory components, unique structural "
                "necessities) and functional elements (specific practical requirements, particular "
                "mechanical necessities)."
            ),
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="exception",
)
