from psalm.dimensions.base import Dimension, Importance, SubDimension

WRITING_STYLE = Dimension(
    name="Writing Style",
    description="How the text is stylistically composed.",
    sub_dimensions=[
        SubDimension(
            name="Figurative Language",
            description="Distinctive metaphors (unique comparative frameworks, specific symbolic mappings), unique similes (particular analogical constructions, specific comparative structures), specific allegories (detailed extended metaphors, unique narrative symbolism), and particular symbolic expressions (specific recurrent motifs, unique emblematic imagery).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Complexity & Depth",
            description="Specific layers of complexity (unique structural density, particular thematic depth, detailed intellectual engagement) and stylistic sophistication (unique literary techniques, specific intertextual references, detailed allusive patterns).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Narrative Techniques",
            description="Distinctive storytelling methods (unique narrative devices, specific structural innovations, particular storytelling strategies) and creative presentation (unique framing choices, specific pacing techniques, detailed narrative experiments).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Descriptive Techniques",
            description="Specific descriptive methods (unique sensory engagements, particular imagery patterns, detailed observational approaches) and creative depiction (unique visualizations, specific auditory evocations, particular tactile descriptions).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Syntax & Grammar",
            description="Particular syntactic structures (unique sentence constructions, specific grammatical choices, detailed clause arrangements) and structural creativity (unique paragraphing, specific punctuation use, particular syntactic experiments).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Sentence Structure",
            description="Particular sentence patterns (unique structural choices, specific length variations, detailed syntactic arrangements) and rhythmic construction (unique clause combinations, specific phrase orderings, particular sentence architectures).",
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)