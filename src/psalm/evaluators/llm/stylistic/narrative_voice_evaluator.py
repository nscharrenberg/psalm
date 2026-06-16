from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()

class NarrativeVoiceEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Narrative Voice"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing narrative voice similarity across point of view,
        narrative distance, narrator type, temporal perspective, focalization, and reader
        relationship to determine storytelling perspective consistency.
        """

    def _build_evaluation_dag(self, model_name: str = "gpt-4o-mini", threshold: float = 0.5,
                              verbose_mode: bool = False) -> DAGMetric:
        judgement_node = self.judgement()

        reader_node = self.reader_engagement_analysis()
        reader_node.children.append(judgement_node)

        focalization_node = self.focalization_pattern_analysis()
        focalization_node.children.append(reader_node)

        temporal_node = self.temporal_perspective_analysis()
        temporal_node.children.append(focalization_node)

        narrator_node = self.narrator_presence_analysis()
        narrator_node.children.append(temporal_node)

        distance_node = self.narrative_distance_analysis()
        distance_node.children.append(narrator_node)

        pov_node = self.point_of_view_analysis()
        pov_node.children.append(distance_node)

        dag = DeepAcyclicGraph(root_nodes=[pov_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=0.5,
            dag=dag,
            verbose_mode=verbose_mode
        )

    def weights(self) -> dict[str, float]:
        return {
            "point_of_view_person": 0.25,
            "narrative_distance": 0.20,
            "narrator_presence_type": 0.20,
            "temporal_perspective": 0.15,
            "focalization_pattern": 0.15,
            "reader_engagement": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            narrative voice similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Point of View Analysis"}} (weight: {weights['point_of_view_person']:.0%})
            - {{output from "Narrative Distance Analysis"}} (weight: {weights['narrative_distance']:.0%})
            - {{output from "Narrator Presence Analysis"}} (weight: {weights['narrator_presence_type']:.0%})
            - {{output from "Temporal Perspective Analysis"}} (weight: {weights['temporal_perspective']:.0%})
            - {{output from "Focalization Pattern Analysis"}} (weight: {weights['focalization_pattern']:.0%})
            - {{output from "Reader Engagement Analysis"}} (weight: {weights['reader_engagement']:.0%})

            Assess the overall narrative voice similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.
            """,
            children=self.verdict_nodes(),
        )

    def reader_engagement_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Reader Engagement Analysis",
            instructions=f"""
            Analyze reader engagement in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Direct address patterns (how often narrator explicitly addresses reader)
            2. Assumed reader relationship (intimate/familiar, neutral, formal/distant)
            3. Examples of reader engagement or acknowledgment

            Provide a structured comparison of reader engagement between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def focalization_pattern_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Focalization Pattern Analysis",
            instructions=f"""
            Analyze focalization patterns in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Consciousness filtering (whose perspective filters events: fixed internal,
               variable internal, external, mixed)
            2. Perceptual limitations (what information boundaries exist: strictly limited,
               moderately limited, minimally limited, unlimited)
            3. Any shifts in focalization or boundary crossings

            Provide a structured comparison of focalization patterns between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def temporal_perspective_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Temporal Perspective Analysis",
            instructions=f"""
            Analyze temporal perspective in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Verb tense patterns (primary tense: past, present, future, mixed)
            2. Temporal relationship (narrator's position relative to events: retrospective,
               immediate, anticipatory, mixed)
            3. Consistency and any deliberate tense shifts

            Provide a structured comparison of temporal perspective between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def narrator_presence_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Narrator Presence Analysis",
            instructions=f"""
            Analyze narrator presence and type in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Narrator role (participant in story, witness/peripheral character, or external observer)
            2. Narrator intrusiveness (frequency of commentary, editorializing, direct intervention)
            3. Whether narrator exists inside or outside the story world

            Provide a structured comparison of narrator presence between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def narrative_distance_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Narrative Distance Analysis",
            instructions=f"""
            Analyze narrative distance in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Psychological proximity (how close narrator is to character consciousness:
               intimate/close, middle distance, distant/far)
            2. Emotional involvement (narrator's emotional stance: high, moderate, low/none)
            3. Degree of access to character interiority and any distance shifts

            Provide a structured comparison of narrative distance between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].
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

    def point_of_view_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Point of View Analysis",
            instructions=f"""
            Analyze point of view in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Grammatical person (first "I/we", second "you", third "he/she/they")
            2. Narrative knowledge scope (limited to one character, multiple characters,
               omniscient, or objective/external only)
            3. Consistency of person and knowledge boundaries throughout the text

            Provide a structured comparison of point of view between the two texts,
            assessing similarity or differences and for each one categorize it into one of the following [{verdict_texts}].
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[]
        )

    def verdict_nodes(self):
        return [
        VerdictNode(
            verdict="Identical or near-identical narrative voice across all dimensions",
            score=10
        ),
        VerdictNode(
            verdict="Very similar narrative voice with only minor differences",
            score=8
        ),
        VerdictNode(
            verdict="Moderately similar narrative voice with some notable differences",
            score=5
        ),
        VerdictNode(
            verdict="Somewhat different narrative voice with limited similarities",
            score=3
        ),
        VerdictNode(
            verdict="Clearly different or opposite narrative voices",
            score=0
        )
    ]


