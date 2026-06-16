from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class CharacterSimilarityEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Character Similarity"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing character similarity for EU copyright analysis.
        Evaluates protectable character expression (distinctive traits, development, 
        relationships, motivations, behaviors) vs unprotectable generic character types.
        Focuses on creative elaboration beyond stock archetypes.
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        function_node = self.character_function_role_analysis()
        function_node.children.append(judgement_node)

        expression_node = self.character_expression_behavior_analysis()
        expression_node.children.append(function_node)

        background_node = self.character_background_motivation_analysis()
        background_node.children.append(expression_node)

        relationships_node = self.character_relationships_analysis()
        relationships_node.children.append(background_node)

        arc_node = self.character_arc_development_analysis()
        arc_node.children.append(relationships_node)

        identity_node = self.character_identity_traits_analysis()
        identity_node.children.append(arc_node)

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
            "character_identity_traits": 0.25,
            "character_arc_development": 0.20,
            "character_relationships": 0.20,
            "character_background_motivation": 0.15,
            "character_expression_behavior": 0.15,
            "character_function_role": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            character similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Character Identity & Traits Analysis"}} (weight: {weights['character_identity_traits']:.0%})
            - {{output from "Character Arc & Development Analysis"}} (weight: {weights['character_arc_development']:.0%})
            - {{output from "Character Relationships & Dynamics Analysis"}} (weight: {weights['character_relationships']:.0%})
            - {{output from "Character Background & Motivation Analysis"}} (weight: {weights['character_background_motivation']:.0%})
            - {{output from "Character Expression & Behavior Analysis"}} (weight: {weights['character_expression_behavior']:.0%})
            - {{output from "Character Function & Role Analysis"}} (weight: {weights['character_function_role']:.0%})

            Assess the overall character similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL EU COPYRIGHT REMINDER:
            - Generic character types/archetypes are NOT protected (idea)
            - Specific creative elaboration IS protected (expression)
            - Focus on DISTINCTIVE, ORIGINAL creative choices, not stock characteristics
            """,
            children=self.verdict_nodes(),
        )

    def character_function_role_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Function & Role Analysis",
            instructions=f"""
            Analyze character function and role in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Narrative function (plot roles, responsibilities, mechanisms, positioning)
            2. Agency & autonomy level (patterns of character agency, constraints, evolution)
            3. Note: This dimension is often LEAST protectable as functions are typically stock

            CRITICAL DISTINCTION:
            - GENERIC functions (UNPROTECTED): "protagonist," "antagonist," "mentor," "sidekick"
            - SPECIFIC functions (WEAKLY PROTECTED): Particular plot roles with unique responsibilities, 
              specific narrative mechanisms, detailed functional elaborations

            Provide a structured comparison of character function and role between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            EXPECT LOW SCORES here as stock narrative functions are NOT protectable.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def character_expression_behavior_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Expression & Behavior Analysis",
            instructions=f"""
            Analyze character expression and behavior in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Behavioral signatures (specific action patterns, decision-making, habits, rituals)
            2. Emotional response patterns (emotional sequences, triggers, coping mechanisms, manifestations)

            CRITICAL DISTINCTION:
            - GENERIC behaviors/emotions (UNPROTECTED): "brave," "impulsive," "gets angry" without specificity
            - SPECIFIC patterns (PROTECTED): Particular action sequences, unique emotional triggers, 
              distinctive behavioral habits, specific response mechanisms

            Examples of SPECIFIC patterns:
            - "When stressed, follows ritual: checks locks three times, makes tea in particular order"
            - "Emotional sequence: initial numbness (2 hours) → anger directed at self → delayed grief"

            Provide a structured comparison of character expression and behavior between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic descriptors. FOCUS on SPECIFIC, DETAILED patterns.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def character_background_motivation_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Background & Motivation Analysis",
            instructions=f"""
            Analyze character background and motivation in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Backstory specificity (detailed personal history, particular events, unique formative 
               experiences, specific causal connections to present)
            2. Motivational structure (detailed goal hierarchies, particular value systems, unique 
               desire configurations, specific origins and manifestations)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "tragic past," "orphaned as child," "wants revenge," "seeks power"
            - SPECIFIC (PROTECTED): Detailed personal histories with particular events, unique goal 
              hierarchies, specific value conflicts, detailed motivational origins

            Examples of SPECIFIC elements:
            - "Witnessed father's death at age 7 in specific circumstances; formed coping mechanisms 
              through particular friendship that ended in betrayal at 16"
            - "Primary motivation is proving competence (not power) to deceased parent; creates 
              particular internal tensions with secondary motivation of avoiding intimacy"

            Provide a structured comparison of character background and motivation between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels. FOCUS on SPECIFIC, DETAILED personal histories and motivational architectures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def character_relationships_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Relationships & Dynamics Analysis",
            instructions=f"""
            Analyze character relationships and dynamics in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Relationship constellation (network structure, particular dynamics, unique power balances, 
               detailed emotional textures)
            2. Interaction patterns (specific communication styles, unique behavioral patterns in social 
               contexts, detailed conflict/cooperation methods)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "has mentor," "loves someone," "has rival," "character is friendly"
            - SPECIFIC (PROTECTED): Particular relationship dynamics, unique interaction patterns, 
              specific emotional textures, detailed communication styles

            Examples of SPECIFIC elements:
            - "Asymmetric mentor relationship where mentor withholds information due to guilt; romantic 
              relationship characterized by intellectual sparring masking vulnerability"
            - "Uses self-deprecating humor to deflect serious conversations; becomes formal/distant when 
              vulnerable; specific escalation pattern in arguments"

            Provide a structured comparison of character relationships and dynamics between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE relationship labels. FOCUS on SPECIFIC dynamics and DETAILED interaction patterns.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def character_arc_development_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Arc & Development Analysis",
            instructions=f"""
            Analyze character arc and development in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Transformation pattern (detailed trajectory of change, particular triggers, unique stages, 
               specific internal shifts)
            2. Internal conflict structure (particular manifestations, unique opposing forces, detailed 
               psychological stakes, specific triggers and resolutions)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "character learns to be brave," "villain becomes good," "duty vs desire"
            - SPECIFIC (PROTECTED): Detailed trajectory of change with particular catalysts, unique internal 
              conflict manifestations, specific psychological structures

            Examples of SPECIFIC elements:
            - "Initially copes through isolation → triggered by specific event → gradually learns vulnerability 
              through series of small failures → ultimately accepts interdependence"
            - "Need for control (rooted in childhood abandonment) vs desire for connection (triggered by 
              specific relationship), manifesting as self-sabotage through particular behaviors"

            Provide a structured comparison of character arc and development between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic arc labels. FOCUS on DETAILED trajectory and SPECIFIC conflict structures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def character_identity_traits_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Character Identity & Traits Analysis",
            instructions=f"""
            Analyze character identity and traits in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Distinctive personality traits (specific creative elaborations, quirks, contradictions, 
               unique combinations beyond archetypes)
            2. Physical & behavioral specificity (unique physical details, distinctive mannerisms, 
               particular gestures, idiosyncratic behaviors)
            3. Psychological complexity (multi-layered internal conflicts, contradictory emotions, 
               nuanced psychological states, specific defense mechanisms)

            CRITICAL DISTINCTION:
            - GENERIC (UNPROTECTED): "brave," "kind," "evil," "tall," "dark hair," one-dimensional motivations
            - SPECIFIC (PROTECTED): Specific creative elaborations, unique contradictions, distinctive details, 
              complex psychological patterns

            Examples of SPECIFIC traits:
            - "Compulsively counts objects when anxious, but only in threes; speaks formally to strangers 
              but uses childish language with loved ones"
            - "Left eyebrow twitches when lying; scar shaped like crescent moon on right temple"
            - "Internal contradiction: loves independence but craves approval; uses humor to deflect intimacy"

            Provide a structured comparison of character identity and traits between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic archetypes. FOCUS ONLY on DISTINCTIVE, ORIGINAL creative elaborations.
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
                verdict="Identical or near-identical characters across all dimensions",
                score=10
            ),
            VerdictNode(
                verdict="Very similar characters with only minor differences",
                score=8
            ),
            VerdictNode(
                verdict="Moderately similar characters with some notable differences",
                score=5
            ),
            VerdictNode(
                verdict="Somewhat different characters with limited similarities",
                score=3
            ),
            VerdictNode(
                verdict="Clearly different or opposite characters",
                score=0
            )
        ]