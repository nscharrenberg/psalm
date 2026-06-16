from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class SceneSequenceSimilarityEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Scene Sequence Similarity"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing scene sequence similarity for EU copyright analysis.
        Evaluates protectable scene expression (specific scene content, internal structures, 
        sequencing patterns, transitions, pacing) vs unprotectable generic scene types. 
        Focuses on creative scene construction and arrangement beyond stock scene categories.
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        functions_node = self.scene_functions_types_analysis()
        functions_node.children.append(judgement_node)

        pacing_node = self.scene_pacing_rhythm_analysis()
        pacing_node.children.append(functions_node)

        transitions_node = self.scene_transitions_connections_analysis()
        transitions_node.children.append(pacing_node)

        architecture_node = self.scene_sequence_architecture_analysis()
        architecture_node.children.append(transitions_node)

        structure_node = self.scene_internal_structure_analysis()
        structure_node.children.append(architecture_node)

        identity_node = self.scene_identity_content_analysis()
        identity_node.children.append(structure_node)

        dag = DeepAcyclicGraph(root_nodes=[identity_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "scene_identity_content": 0.25,
            "scene_internal_structure": 0.25,
            "scene_sequence_architecture": 0.20,
            "scene_transitions_connections": 0.15,
            "scene_pacing_rhythm": 0.10,
            "scene_functions_types": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            scene sequence similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Scene Identity & Content Analysis"}} (weight: {weights['scene_identity_content']:.0%})
            - {{output from "Scene Internal Structure Analysis"}} (weight: {weights['scene_internal_structure']:.0%})
            - {{output from "Scene Sequence Architecture Analysis"}} (weight: {weights['scene_sequence_architecture']:.0%})
            - {{output from "Scene Transitions & Connections Analysis"}} (weight: {weights['scene_transitions_connections']:.0%})
            - {{output from "Scene Pacing & Rhythm Analysis"}} (weight: {weights['scene_pacing_rhythm']:.0%})
            - {{output from "Scene Functions & Types Analysis"}} (weight: {weights['scene_functions_types']:.0%})

            Assess the overall scene sequence similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL EU COPYRIGHT REMINDER:
            - Generic scene types (chase, love scene, confrontation) are NOT protected (idea)
            - Specific scene construction and arrangement IS protected (expression)
            - Focus on DISTINCTIVE, ORIGINAL creative choices in scene design, not stock categories
            """,
            children=self.verdict_nodes(),
        )

    def scene_functions_types_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Functions & Types Analysis",
            instructions=f"""
            Analyze scene functions and types in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Scene type distribution (patterns of scene categories, ratios, arrangements)
            2. Structural positioning (where scene types appear in narrative structure)
            3. Note: This dimension is often LEAST protectable as scene types are typically stock

            CRITICAL DISTINCTION:
            - GENERIC scene types (UNPROTECTED): "action scene," "dialogue scene," "love scene," 
              "exposition scene," "confrontation scene," "climax near end"
            - SPECIFIC patterns (WEAKLY PROTECTED): Particular combinations and distributions with 
              details, unique positioning of specific scene types

            Examples of SPECIFIC elements:
            - "Specific distribution: X action-heavy scenes, Y introspective scenes, Z ensemble 
              dialogue scenes arranged in unique pattern (alternating or clustering in specified way)"
            - "Major revelation scene positioned at unique point (X% through narrative, after 
              particular sequence); action sequences clustered in particular structural locations"

            Provide a structured comparison of scene functions and types between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            EXPECT LOW SCORES here as stock scene types/positioning are NOT protectable.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def scene_pacing_rhythm_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Pacing & Rhythm Analysis",
            instructions=f"""
            Analyze scene pacing and rhythm in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Scene duration pattern (specific patterns of scene lengths, unique duration variations, 
               temporal architectures across sequences)
            2. Pacing rhythm (particular acceleration/deceleration patterns, unique tempo variations 
               across specific scene sequences)

            CRITICAL DISTINCTION:
            - GENERIC pacing (UNPROTECTED): "has short and long scenes," "varies scene length," 
              "fast then slow," "builds momentum"
            - SPECIFIC patterns (PROTECTED): Particular duration rhythms with details, unique 
              acceleration/deceleration points, specific tempo architectures

            Examples of SPECIFIC elements:
            - "Opening uses 3 very brief scenes (each covering X time/pages with particular content), 
              followed by extended scene (Y time/pages with specific rhythm), then alternating pattern 
              (short-long-short-medium with specified scenes)"
            - "Deliberate pace in scenes 1-3 → accelerates at scene 4 (specific techniques: action 
              density, shorter cuts) → maintains through 4-7 → decelerates at scene 8 (extended single 
              location) creating specific rhythm"

            Provide a structured comparison of scene pacing and rhythm between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic terms ("fast," "slow"). FOCUS on SPECIFIC length patterns and DETAILED tempo rhythms.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def scene_transitions_connections_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Transitions & Connections Analysis",
            instructions=f"""
            Analyze scene transitions and connections in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Transition mechanisms (particular transition techniques, unique linking devices, 
               specific methods of scene connection)
            2. Continuity patterns (particular elements that carry between scenes, unique patterns 
               of what persists/resolves/transforms, specific continuity architectures)

            CRITICAL DISTINCTION:
            - GENERIC transitions/continuity (UNPROTECTED): "scene cuts to next," "time passes," 
              "meanwhile," "element continues," "thread carries over"
            - SPECIFIC mechanisms (PROTECTED): Particular linking devices with details, unique 
              transitional elements, specific continuity architectures

            Examples of SPECIFIC elements:
            - "Scene A ends with character gazing at specific object X → transition dissolves to scene B 
              opening with different character holding similar object in different context → object X 
              links scenes thematically through specified mechanism"
            - "Scene A introduces unresolved element X (character makes specific promise regarding Y) → 
              carries through B and C via visual motif → resurfaces in D through particular trigger → 
              resolves in E with specific outcome"

            Provide a structured comparison of scene transitions and connections between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic terms ("cut," "carries over"). FOCUS on SPECIFIC linking devices and DETAILED 
            continuity architectures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def scene_sequence_architecture_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Sequence Architecture Analysis",
            instructions=f"""
            Analyze scene sequence architecture in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Scene ordering pattern (particular sequences of specific scenes, unique ordering logic, 
               specific scene-to-scene progressions)
            2. Scene relationship network (particular inter-scene connections, unique causal/thematic 
               linkage patterns, specific networks of how scenes relate)

            CRITICAL DISTINCTION:
            - GENERIC ordering/relationships (UNPROTECTED): "action scenes followed by quiet scenes," 
              "alternates between storylines," "scenes connect causally," "scenes mirror each other"
            - SPECIFIC patterns (PROTECTED): Particular sequences of identified scenes, unique ordering 
              logic with details, specific inter-scene relationship networks

            Examples of SPECIFIC elements:
            - "Specific scene sequence: Scene A (intimate conversation in specified setting) → Scene B 
              (specific action with particular elements) → Scene C (unique reflective moment with 
              detailed character action) → Scene D (specific group confrontation). Pattern: 2 
              internal/quiet, 1 external/active, repeat with variations at specified points"
            - "Scene A establishes element X which directly causes B through unique mechanism (character 
              decision leads to specific situation); B introduces detail Y which thematically echoes C 
              (visual motif with specific parallels); C creates condition Z enabling D's events; A and D 
              bracket sequence with unique symmetry (specific parallels and inversions)"

            Provide a structured comparison of scene sequence architecture between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("alternates," "connects"). FOCUS on SPECIFIC scene-to-scene sequences 
            and DETAILED relationship architectures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def scene_internal_structure_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Internal Structure Analysis",
            instructions=f"""
            Analyze scene internal structure in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Dramatic beat sequence (particular emotional/dramatic progressions within scenes, unique 
               sequences of beats, specific micro-structures of moment-to-moment unfolding)
            2. Scene composition & staging (particular character positioning/staging, unique visual/narrative 
               focus arrangements, specific compositional choices in element presentation)

            CRITICAL DISTINCTION:
            - GENERIC beat patterns/composition (UNPROTECTED): "tension rises," "conflict escalates," 
              "revelation occurs," "characters talk," "action occurs"
            - SPECIFIC structures (PROTECTED): Particular emotional progressions with stages, unique 
              staging choices with details, specific compositional arrangements

            Examples of SPECIFIC elements:
            - "Scene follows beat sequence: (1) initial false calm with particular character actions 
              (A arranges objects in specific pattern) → (2) subtle tension via unique mechanism (B mentions 
              specific detail triggering A's reaction) → (3) escalation through particular exchange 
              (specified dialogue structure) → (4) peak at specific moment (object falls, revealing hidden 
              item) → (5) resolution through unique mechanism"
            - "Scene staged with composition: A positioned at particular location (standing by window, back 
              turned, specific posture), B at unique position (seated at specified object, particular state), 
              with specific focus pattern (attention shifts between A's reflection showing expression, B's 
              hands performing action, environmental detail revealing information)"

            Provide a structured comparison of scene internal structure between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("tension rises," "characters talk"). FOCUS on SPECIFIC moment-to-moment 
            progressions and DETAILED compositional choices.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def scene_identity_content_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Scene Identity & Content Analysis",
            instructions=f"""
            Analyze scene identity and content in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Scene-specific elements (particular settings with details, unique character configurations, 
               specific actions/events, detailed circumstances, creative elaborations beyond stock scene types)
            2. Scene purpose elaboration (particular mechanisms of how scenes accomplish purposes, unique 
               combinations of purposes, detailed methods through which scenes function narratively)

            CRITICAL DISTINCTION:
            - GENERIC scene elements/purposes (UNPROTECTED): "two characters fight," "characters kiss," 
              "character discovers secret," "reveals information," "builds tension," "develops relationship"
            - SPECIFIC elements/purposes (PROTECTED): Particular settings, unique circumstances, specific 
              actions with details, detailed purpose mechanisms

            Examples of SPECIFIC elements:
            - "Confrontation in specific unusual location (cramped elevator with particular features) between 
              A and B using unique tactics (A uses confined space strategically, B attempts specific maneuver), 
              involving particular objects, with specific environmental constraints (elevator jerking, lights 
              flickering at key moments)"
            - "Scene reveals specific information X through unique mechanism: A discovers particular detail 
              via specific action sequence (searching specified object, finding encoded message, decoding 
              through particular method learned in prior scene), which simultaneously establishes B's deception 
              regarding particular matter, while positioning A in specific strategic position for later scene"

            Provide a structured comparison of scene identity and content between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic scene labels ("fight," "love scene," "reveals"). FOCUS ONLY on SPECIFIC creative 
            scene details and DETAILED purpose mechanisms.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def verdict_texts(self) -> str:
        verdicts = self.verdict_nodes()
        return ', '.join([str(verdict.verdict) for verdict in verdicts])

    def verdict_nodes(self):
        return [
            VerdictNode(
                verdict="Identical or near-identical scene sequences across all dimensions",
                score=10
            ),
            VerdictNode(
                verdict="Very similar scene sequences with only minor differences",
                score=8
            ),
            VerdictNode(
                verdict="Moderately similar scene sequences with some notable differences",
                score=5
            ),
            VerdictNode(
                verdict="Somewhat different scene sequences with limited similarities",
                score=3
            ),
            VerdictNode(
                verdict="Clearly different or opposite scene sequences",
                score=0
            )
        ]