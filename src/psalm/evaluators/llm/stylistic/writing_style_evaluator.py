from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class WritingStyleEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Writing Style"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing writing style similarity across lexical, 
        syntactic, rhetorical, and tonal dimensions to determine authorship 
        consistency.
        """

    def _build_evaluation_dag(
            self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        tone_node = self.tone_voice_analysis()
        tone_node.children.append(judgement_node)

        discourse_node = self.discourse_organization_analysis()
        discourse_node.children.append(tone_node)

        rhetorical_node = self.rhetorical_patterns_analysis()
        rhetorical_node.children.append(discourse_node)

        rhythm_node = self.rhythm_flow_analysis()
        rhythm_node.children.append(rhetorical_node)

        sentence_node = self.sentence_structure_analysis()
        sentence_node.children.append(rhythm_node)

        lexical_node = self.lexical_complexity_analysis()
        lexical_node.children.append(sentence_node)

        dag = DeepAcyclicGraph(root_nodes=[lexical_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "lexical_complexity": 0.20,
            "sentence_structure": 0.25,
            "rhythm_flow": 0.15,
            "rhetorical_patterns": 0.20,
            "discourse_organization": 0.15,
            "tone_voice": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            writing style similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Lexical Complexity Analysis"}} (weight: {weights['lexical_complexity']:.0%})
            - {{output from "Sentence Structure Analysis"}} (weight: {weights['sentence_structure']:.0%})
            - {{output from "Rhythm & Flow Analysis"}} (weight: {weights['rhythm_flow']:.0%})
            - {{output from "Rhetorical Patterns Analysis"}} (weight: {weights['rhetorical_patterns']:.0%})
            - {{output from "Discourse Organization Analysis"}} (weight: {weights['discourse_organization']:.0%})
            - {{output from "Tone & Voice Analysis"}} (weight: {weights['tone_voice']:.0%})

            Assess the overall writing style similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.
            """,
            children=self.verdict_nodes(),
        )

    def tone_voice_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Tone & Voice Analysis",
            instructions=f"""
            Analyze tone and voice in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Authorial presence (personal voice with I/we vs impersonal voice with passive constructions)
            2. Assertiveness level (definitive statements vs hedging with maybe/might/possibly)
            3. Overall voice characteristics and consistency

            Provide a structured comparison of tone and voice between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content and meaning. Focus ONLY on voice and stance.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def discourse_organization_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Discourse Organization Analysis",
            instructions=f"""
            Analyze discourse organization in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Paragraph structure (short vs long, single-sentence vs multi-sentence)
            2. Transition and connective usage (however, therefore, moreover, etc.)
            3. Overall organizational patterns and coherence devices

            Provide a structured comparison of discourse organization between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content. Focus on organizational patterns.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def rhetorical_patterns_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Rhetorical Patterns Analysis",
            instructions=f"""
            Analyze rhetorical patterns in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Question/statement/imperative usage (distribution and frequency)
            2. Repetition patterns (repeated phrases, parallel structures, anaphora)
            3. Overall rhetorical device usage and patterns

            Provide a structured comparison of rhetorical patterns between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content. Focus on rhetorical devices and patterns.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def rhythm_flow_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Rhythm & Flow Analysis",
            instructions=f"""
            Analyze rhythm and flow in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Punctuation patterns (frequency and variety of commas, periods, semicolons, etc.)
            2. Sentence rhythm (staccato/choppy vs flowing/smooth)
            3. Overall pacing and rhythmic characteristics

            Provide a structured comparison of rhythm and flow between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content. Focus on pacing and rhythm.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def sentence_structure_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Sentence Structure Analysis",
            instructions=f"""
            Analyze sentence structure in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Sentence length patterns (short/medium/long distribution)
            2. Sentence complexity (simple vs complex structures with clauses and subordination)
            3. Overall structural consistency and patterns

            Provide a structured comparison of sentence structure between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content and meaning. Focus ONLY on structural patterns.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def lexical_complexity_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Lexical Complexity Analysis",
            instructions=f"""
            Analyze lexical complexity in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Vocabulary richness (pattern of word repetition vs variety)
            2. Word length patterns (preference for short/medium/long words)
            3. Formality level (contractions, colloquialisms, slang vs formal vocabulary, technical jargon)

            Provide a structured comparison of lexical complexity between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            CRITICAL: Ignore content, topic, and meaning entirely. Focus ONLY on HOW the text is written, not WHAT it says.
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
                verdict="Identical or near-identical writing style across all dimensions",
                score=10
            ),
            VerdictNode(
                verdict="Very similar writing style with only minor differences",
                score=8
            ),
            VerdictNode(
                verdict="Moderately similar writing style with some notable differences",
                score=5
            ),
            VerdictNode(
                verdict="Somewhat different writing style with limited similarities",
                score=3
            ),
            VerdictNode(
                verdict="Clearly different or opposite writing styles",
                score=0
            )
        ]