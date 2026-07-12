from psalm.dimensions.base import Dimension, Importance, SubDimension

SCENE_SEQUENCE = Dimension(
    name="Scene Sequence",
    description="How scenes are arranged and function within the narrative.",
    sub_dimensions=[
        SubDimension(
            name="Scene Internal Structure",
            description="Dramatic beat sequence (particular arrangement of dramatic moments, unique pacing of beats, specific emotional arcs within scenes) and scene composition & staging (detailed blocking, unique visual or spatial arrangements, specific character positioning).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Scene Sequence Architecture",
            description="Scene ordering pattern (particular sequence of scenes, unique structural choices, specific narrative flow) and scene relationship network (detailed connections between scenes, unique cause-effect relationships, specific thematic linkages).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Scene Transitions & Connections",
            description="Transition mechanisms (particular methods of moving between scenes, unique bridging techniques, specific continuity devices) and continuity patterns (detailed consistency in tone, unique thematic echoes, specific character arcs across scenes).",
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Scene Pacing & Rhythm",
            description="Scene duration pattern (particular lengths of scenes, unique temporal choices, specific rhythm of scene changes) and pacing rhythm (detailed speed variations, unique acceleration/deceleration, specific momentum shifts).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Scene Identity & Content",
            description="Scene-specific elements (particular details unique to each scene, unique atmospheric choices, specific symbolic motifs) and scene purpose elaboration (detailed narrative function of each scene, unique thematic contributions, specific character development moments).",
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Scene Functions & Types",
            description="Scene type distribution (particular variety of scene types, unique balance of action/dialogue/exposition) and structural positioning (specific placement of scenes within overall structure, unique narrative weight of each scene type).",
            importance=Importance.LOW,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="infringement",
)
