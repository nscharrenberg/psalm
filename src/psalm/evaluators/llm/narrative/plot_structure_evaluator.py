from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()

class PlotStructureSimilarityEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Plot Structure Similarity"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing plot structure similarity for EU copyright analysis.
        Evaluates protectable narrative expression (specific event sequences, causal chains, 
        structural architecture, conflict construction, turning points, temporal organization) 
        vs unprotectable generic plot types. Focuses on creative narrative construction beyond 
        stock story patterns.
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        functions_node = self.plot_functions_convergence_analysis()
        functions_node.children.append(judgement_node)

        temporal_node = self.temporal_structure_analysis()
        temporal_node.children.append(functions_node)

        turning_points_node = self.plot_turning_points_analysis()
        turning_points_node.children.append(temporal_node)

        conflict_node = self.conflict_construction_analysis()
        conflict_node.children.append(turning_points_node)

        architecture_node = self.story_architecture_structure_analysis()
        architecture_node.children.append(conflict_node)

        event_node = self.event_sequence_causality_analysis()
        event_node.children.append(architecture_node)

        dag = DeepAcyclicGraph(root_nodes=[event_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "event_sequence_causality": 0.25,
            "story_architecture_structure": 0.25,
            "conflict_construction": 0.20,
            "plot_turning_points": 0.15,
            "temporal_structure": 0.10,
            "plot_functions_convergence": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            plot structure similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Event Sequence & Causality Analysis"}} (weight: {weights['event_sequence_causality']:.0%})
            - {{output from "Story Architecture & Structure Analysis"}} (weight: {weights['story_architecture_structure']:.0%})
            - {{output from "Conflict Construction Analysis"}} (weight: {weights['conflict_construction']:.0%})
            - {{output from "Plot Turning Points & Reversals Analysis"}} (weight: {weights['plot_turning_points']:.0%})
            - {{output from "Temporal Structure Analysis"}} (weight: {weights['temporal_structure']:.0%})
            - {{output from "Plot Functions & Convergence Analysis"}} (weight: {weights['plot_functions_convergence']:.0%})

            Assess the overall plot structure similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL EU COPYRIGHT REMINDER:
            - Generic plot types/archetypes are NOT protected (idea)
            - Specific narrative construction IS protected (expression)
            - Focus on DISTINCTIVE, ORIGINAL creative choices in plot architecture, not stock patterns
            """,
            children=self.verdict_nodes(),
        )

    def plot_functions_convergence_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Plot Functions & Convergence Analysis",
            instructions=f"""
            Analyze plot functions and convergence in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Plot thread functions (narrative purposes of plot elements, functional relationships)
            2. Resolution architecture (specific mechanisms of conflict resolution, ordering, interdependencies)
            3. Note: This dimension is often LEAST protectable as functions are typically stock

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "main plot," "subplot," "conflicts resolve," "happy ending," "tragic ending"
            - SPECIFIC (WEAKLY PROTECTED): Particular narrative purposes with details, unique resolution mechanisms, 
              specific ordering and interdependencies

            Examples of SPECIFIC elements:
            - "Secondary thread serves compound function: provides particular information X through unique mechanism, 
              while creating specific emotional resonance and thematic parallel"
            - "Conflict A resolves through particular mechanism which enables resolution of B; C remains partially 
              unresolved in detailed way"

            Provide a structured comparison of plot functions and convergence between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            EXPECT LOW SCORES here as stock plot functions are NOT protectable.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def temporal_structure_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Temporal Structure Analysis",
            instructions=f"""
            Analyze temporal structure in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Chronological organization (particular timeline arrangements, unique flashback patterns, 
               specific time jump structures, detailed temporal layering)
            2. Pacing architecture (particular pacing patterns, unique acceleration/deceleration points, 
               specific rhythmic structures, detailed pacing choices)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "has flashbacks," "non-linear," "starts in medias res," "fast," "slow"
            - SPECIFIC (PROTECTED): Particular timeline arrangements, unique temporal patterns, specific 
              pacing rhythms with creative reasoning

            Examples of SPECIFIC elements:
            - "Narrative alternates between specific timelines (present + flashbacks to years X, Y, Z) using 
              particular pattern; flashbacks triggered by specific mechanisms; converge at detailed moment"
            - "Slow contemplative pace for first 3 chapters → acceleration at specific trigger → rapid pacing 
              through middle → deceleration at detailed moment → final acceleration with unique rhythm"

            Provide a structured comparison of temporal structure between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels. FOCUS on SPECIFIC timeline patterns and DETAILED pacing architectures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def plot_turning_points_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Plot Turning Points & Reversals Analysis",
            instructions=f"""
            Analyze plot turning points and reversals in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Turning point specificity (particular nature of plot shifts with details, unique content 
               of revelations/changes, specific timing and positioning, detailed mechanisms)
            2. Reversal mechanisms (particular mechanisms of how reversals occur, unique triggers and causes, 
               specific patterns of expectation-then-subversion, detailed direction changes)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "character makes discovery," "revelation occurs," "unexpected twist," 
              "fortune changes"
            - SPECIFIC (PROTECTED): Particular content of shifts, unique reversal mechanisms, specific 
              trigger structures, detailed consequences

            Examples of SPECIFIC elements:
            - "At specific moment during particular event, character finds specific evidence revealing 
              precise truth, discovered through unique mechanism, shifting plot from X to Y through 
              detailed pathway"
            - "Plot establishes specific expectation via particular setup → reversal through unique mechanism 
              (specific event reveals particular information) → redirects to specific new direction"

            Provide a structured comparison of plot turning points and reversals between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels. FOCUS on SPECIFIC turning point content and DETAILED reversal structures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def conflict_construction_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Conflict Construction Analysis",
            instructions=f"""
            Analyze conflict construction in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Conflict escalation pattern (particular escalation stages, unique mechanisms of intensification, 
               specific trigger points, detailed escalation sequences)
            2. Obstacle configuration (particular obstacle types with details, unique obstacle networks/relationships, 
               specific mechanisms of impediment, detailed sequencing)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "conflict increases," "stakes rise," "character faces challenges," 
              "encounters opposition"
            - SPECIFIC (PROTECTED): Particular escalation stages, unique obstacle networks, specific 
              trigger mechanisms, detailed configurations

            Examples of SPECIFIC elements:
            - "Conflict escalates through 4 specific stages: initial misunderstanding over particular issue → 
              specific action triggers defensive response using unique method → escalation to third party 
              through detailed mechanism → final stage via particular pathway"
            - "Character encounters network of 3 interconnected obstacles with specific details; obstacles 
              relate through particular mechanism where overcoming one intensifies another"

            Provide a structured comparison of conflict construction between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic descriptions. FOCUS on SPECIFIC escalation stages and DETAILED obstacle architectures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def story_architecture_structure_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Story Architecture & Structure Analysis",
            instructions=f"""
            Analyze story architecture and structure in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Structural organization (particular structural choices, unique act divisions, distinctive 
               framing devices, specific nested narrative patterns, creative architectural decisions)
            2. Plot layering patterns (particular relationships between plot threads, unique convergence/divergence 
               patterns, specific interweaving mechanisms, detailed thread hierarchies)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "three-act structure," "beginning-middle-end," "has main plot and subplot," 
              "multiple storylines"
            - SPECIFIC (PROTECTED): Particular structural choices, unique nested patterns, specific thread 
              relationships, detailed interweaving mechanisms

            Examples of SPECIFIC elements:
            - "Narrative divided into 5 specific sections with particular thematic focuses; includes framing 
              device where specific narrator reflects between sections using unique mechanism; act 2 subdivided 
              into parallel timelines converging at specific point"
            - "Three specific plot threads interweave using particular pattern: A and B converge at specific 
              points through unique mechanism; C runs parallel until specific trigger causes intersection"

            Provide a structured comparison of story architecture and structure between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic structure labels. FOCUS on SPECIFIC architectural choices and DETAILED thread relationships.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def event_sequence_causality_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Event Sequence & Causality Analysis",
            instructions=f"""
            Analyze event sequence and causality in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Event specificity (particular plot event details beyond generic story beats, unique circumstances, 
               distinctive actions, creative elaborations)
            2. Causal chain architecture (particular cause-effect relationships, unique causal mechanisms, 
               detailed chains where specific events connect through particular mechanisms)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "character faces challenge," "hero fights villain," "one thing leads to another," 
              "actions have consequences"
            - SPECIFIC (PROTECTED): Particular event details, unique circumstances, specific cause-effect relationships, 
              detailed causal mechanisms

            Examples of SPECIFIC elements:
            - "Character accidentally intercepts encrypted message while repairing specific device, realizes it's 
              from believed-dead relative, must decode using particular method learned in childhood"
            - "Character's specific decision to hide particular information from X (due to specific reason) → 
              X makes uninformed choice about Z → triggers event W through mechanism V → cascade continues through 
              detailed chain"

            Provide a structured comparison of event sequence and causality between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic story beats. FOCUS ONLY on SPECIFIC creative event details and DETAILED causal mechanisms.
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
                verdict="Identical or near-identical plot structures across all dimensions",
                score=10
            ),
            VerdictNode(
                verdict="Very similar plot structures with only minor differences",
                score=8
            ),
            VerdictNode(
                verdict="Moderately similar plot structures with some notable differences",
                score=5
            ),
            VerdictNode(
                verdict="Somewhat different plot structures with limited similarities",
                score=3
            ),
            VerdictNode(
                verdict="Clearly different or opposite plot structures",
                score=0
            )
        ]