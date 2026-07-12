from psalm.dimensions.base import Dimension, Importance, SubDimension

NARRATIVE_VOICE = Dimension(
    name="Narrative Voice",
    description="How the story is narrated.",
    sub_dimensions=[
        SubDimension(
            name="Stylistic Voice",
            description="Distinctive stylistic markers (unique syntactic patterns, specific linguistic idiosyncrasies, particular rhetorical devices) and creative language use (unique word combinations, specific phrasing choices, detailed figurative language).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Tone & Atmosphere",
            description="Specific tonal qualities (unique emotional colors, particular mood establishment, detailed atmospheric elements) and narrative mood (unique emotional textures, specific atmospheric shifts, detailed sensory evocations).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Narrative Perspective",
            description="Particular point-of-view choices (unique focalization patterns, specific narrative distances, detailed perspective shifts) and narrative focus (specific attentional patterns, unique observational angles, particular perceptual filters).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Narrative Personality",
            description="Distinctive narrative character (unique authorial presence, specific voice consistency, detailed personality traits of the narrator) and authorial attitude (particular judgments, unique biases, specific worldviews expressed through narration).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Diction & Word Choice",
            description="Particular vocabulary selections (unique lexical choices, specific word frequencies, detailed terminology) and phrasing patterns (unique sentence constructions, specific idiomatic expressions, particular collocations).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Rhythm & Flow",
            description="Specific sentence rhythms (unique cadence patterns, particular syntactic pacing, detailed prosodic elements) and narrative flow (unique progression patterns, specific momentum shifts, detailed temporal arrangements of clauses).",
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)