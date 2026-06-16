from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class PasticheEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Pastiche"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing pastiche character under EU copyright law (AG Emiliou Opinion in Pelham II, 
        C-590/23). Evaluates whether target text constitutes protected pastiche of source text by measuring: 
        style evocation, artistic skill, homage/tribute character, noticeable differences, and fair balance.

        CRITICAL: Measures PASTICHE STRENGTH (higher = stronger exception defense), NOT similarity.
        Score 10 = strong pastiche (protected), Score 0 = no pastiche (unprotected).

        Pastiche is DISTINCT from parody: respectful artistic imitation WITHOUT humor/mockery.
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        balance_node = self.fair_balance_proportionality_analysis()
        balance_node.children.append(judgement_node)

        differences_node = self.noticeable_differences_transformation_analysis()
        differences_node.children.append(balance_node)

        homage_node = self.homage_tribute_character_analysis()
        homage_node.children.append(differences_node)

        skill_node = self.artistic_skill_execution_analysis()
        skill_node.children.append(homage_node)

        evocation_node = self.style_evocation_recognition_analysis()
        evocation_node.children.append(skill_node)

        dag = DeepAcyclicGraph(root_nodes=[evocation_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "style_evocation_recognition": 0.30,
            "artistic_skill_execution": 0.25,
            "homage_tribute_character": 0.20,
            "noticeable_differences_transformation": 0.15,
            "fair_balance_proportionality": 0.10,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            pastiche strength between EXPECTED OUTPUT (source) and ACTUAL OUTPUT (target).

            Consider the outputs from:
            - {{output from "Style Evocation & Recognition Analysis"}} (weight: {weights['style_evocation_recognition']:.0%})
            - {{output from "Artistic Skill & Execution Analysis"}} (weight: {weights['artistic_skill_execution']:.0%})
            - {{output from "Homage/Tribute Character Analysis"}} (weight: {weights['homage_tribute_character']:.0%})
            - {{output from "Noticeable Differences/Transformation Analysis"}} (weight: {weights['noticeable_differences_transformation']:.0%})
            - {{output from "Fair Balance & Proportionality Analysis"}} (weight: {weights['fair_balance_proportionality']:.0%})

            Assess the overall pastiche strength holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL REMINDER - SCORING DIRECTION:
            - This measures PASTICHE STRENGTH, not similarity
            - Higher score = STRONGER pastiche = STRONGER exception defense = protected under AG Emiliou
            - Lower score = WEAKER/NO pastiche = NO exception defense = potential infringement if copying exists

            AG Emiliou (Pelham II) Requirements:
            1. Must evoke source by adopting distinctive "aesthetic language" (style imitation)
            2. Must be noticeably different from source (content differs despite style imitation)
            3. Must be intended to be recognized as imitation (overt tribute/homage)
            4. NO humor/mockery required (distinguishes from parody - respectful not critical)
            5. Must be artistic creation (demonstrates creative mastery)

            CRITICAL: Pastiche is NOT catch-all for all derivative uses (AG Emiliou explicitly rejected this).
            """,
            children=self.verdict_nodes(),
        )

    def fair_balance_proportionality_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Fair Balance & Proportionality Analysis",
            instructions=f"""
            Analyze fair balance and proportionality of ACTUAL OUTPUT (target) as pastiche of EXPECTED OUTPUT (source).

            For the target text, evaluate:
            1. Proportionality of imitation (extent of style borrowing, necessity for tribute purpose, balance with 
               new content, artistic justification - whether extent of imitation is appropriate for homage purpose)
            2. Market non-substitution (whether target could substitute for/harm source market - different purpose/function, 
               audience distinction, no competition with source, compliance with three-step test)

            CRITICAL DISTINCTION (Art. 5(5) InfoSoc; three-step test):
            - PROPORTIONATE: Minimal/moderate style borrowing necessary for tribute; well-balanced; no market harm
            - DISPROPORTIONATE: Excessive borrowing unjustified by purpose; imbalanced; competes with/substitutes source
            - NOTE: Even if pastiche criteria met, disproportionate use or market substitution may fail three-step test

            Examples of assessment:
            - "Borrows only Hemingway's specific sparse prose style; applies to completely different story/characters; 
              serves literary tribute purpose; no market competition → EXCELLENT proportionality and no substitution"
            - "Copies nearly entire source style and substantial content; minimal transformation; could compete with 
              source market → POOR proportionality and market harm"

            Provide a structured assessment of fair balance and proportionality,
            and categorize it into one of the following [{verdict_texts}].

            WARNING: Low score on proportionality or market substitution may UNDERMINE pastiche defense.

            SCORING DIRECTION: Higher score = better fair balance = stronger pastiche protection.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def noticeable_differences_transformation_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Noticeable Differences/Transformation Analysis",
            instructions=f"""
            Analyze noticeable differences and transformation in ACTUAL OUTPUT (target) compared to EXPECTED OUTPUT (source).

            For the target text, evaluate:
            1. Substantive differences (meaningful content/substance differences DESPITE style imitation - different plot/
               characters/events/settings/themes/context/meanings despite similar style; style is imitated but substance 
               must differ)
            2. New creative content (original creative elements added beyond imitation - new characters/plot elements/ideas/
               themes; creative additions; functional independence; creative value added)

            CRITICAL DISTINCTION (AG Emiliou ¶186):
            - NOTICEABLY DIFFERENT: Major substantive differences in content/substance despite style imitation; 
              substantial new creative content; style borrowed but applied to different substance
            - NOT NOTICEABLY DIFFERENT: Minimal differences; similar content AND style; pure copying; no transformation
            - KEY: Target imitates source's AESTHETIC LANGUAGE but applies it to DIFFERENT content/substance

            Examples of NOTICEABLE DIFFERENCES:
            - "Target imitates Austen's specific ironic prose style (aesthetic language) but applies it to modern corporate 
              office romance with completely different characters, plot, themes → MAJOR differences (style imitated, 
              substance differs)"
            - "Target copies both Austen's style AND her specific Pride & Prejudice plot/characters with minor name changes 
              → NOT noticeably different (both style and substance copied)"

            Provide a structured assessment of differences and transformation,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Style imitation is EXPECTED in pastiche; content/substance must meaningfully differ.

            SCORING DIRECTION: Higher score = greater transformation = stronger pastiche qualification.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def homage_tribute_character_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Homage/Tribute Character Analysis",
            instructions=f"""
            Analyze homage/tribute character of ACTUAL OUTPUT (target) toward EXPECTED OUTPUT (source).

            For the target text, evaluate:
            1. Non-mocking character (ABSENCE of humor, mockery, or criticism - respectful tone conveying admiration/
               neutral artistic engagement, no jokes/irony/satire targeting source, no critical intent, 
               celebratory/neutral character)
            2. Tribute intent clarity (how clearly work signals respectful homage purpose - explicit tribute markers 
               like dedications/acknowledgments, celebratory tone, positioned as artistic tribute, audience recognition 
               of homage intent)

            CRITICAL DISTINCTION (AG Emiliou ¶174-181 - KEY DIFFERENCE FROM PARODY):
            - PASTICHE: Respectful/neutral artistic imitation WITHOUT humor/mockery/criticism (tribute/homage)
            - PARODY: Critical/mocking imitation WITH humor/mockery (critique)
            - This is THE distinguishing feature: pastiche = respectful, parody = mocking

            Examples of TRIBUTE character:
            - "Target imitates Tolkien's epic fantasy style with clear admiration; no mockery or criticism; framed as 
              homage to master; respectful tone throughout → STRONG tribute character (pastiche not parody)"
            - "Target imitates Tolkien's style but adds satirical commentary mocking fantasy genre tropes; critical 
              tone → MOCKING character (parody not pastiche)"

            Provide a structured assessment of homage/tribute character,
            and categorize it into one of the following [{verdict_texts}].

            WARNING: If mockery/criticism present (low score), work is PARODY not PASTICHE (different exception).

            SCORING DIRECTION: Higher score = stronger tribute character = stronger pastiche qualification.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def artistic_skill_execution_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Artistic Skill & Execution Analysis",
            instructions=f"""
            Analyze artistic skill and execution quality of ACTUAL OUTPUT's stylistic imitation of EXPECTED OUTPUT.

            For the target text, evaluate:
            1. Technical skill (quality/sophistication of stylistic imitation - accuracy of imitation, consistency 
               of style maintenance, sophistication of techniques, mastery demonstration; how precisely target captures 
               source style nuances)
            2. Creative integration (how skillfully style is adapted to new creative context - contextual adaptation, 
               organic incorporation, creative synthesis, functional use; how naturally style fits into new work vs 
               mechanical copying)

            CRITICAL DISTINCTION (AG Emiliou ¶190-192):
            - ARTISTIC CREATION: High skill; masterful imitation; skillful adaptation; demonstrates creative mastery
            - MERE COPYING: Poor skill; clumsy imitation; mechanical copying; no artistic mastery
            - NOTE: Pastiche must be "artistic creation" (AG Emiliou) - demonstrates creative skill through imitation

            Examples of ARTISTIC SKILL:
            - "Target masterfully captures Hemingway's specific spare prose style with precision; maintains consistency 
              throughout; adapts style seamlessly to new story context; demonstrates deep understanding of aesthetic 
              → HIGH artistic skill (artistic creation)"
            - "Target attempts Hemingway style but execution is clumsy; inconsistent; poorly adapted; mechanical rather 
              than artistic → LOW skill (not artistic creation, just poor copying)"

            Provide a structured assessment of artistic skill and execution,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Without demonstrable artistic skill, work is mere copying, not pastiche.

            SCORING DIRECTION: Higher score = greater artistic skill = stronger pastiche qualification.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def style_evocation_recognition_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Style Evocation & Recognition Analysis",
            instructions=f"""
            Analyze how clearly and specifically ACTUAL OUTPUT (target) imitates the distinctive style/aesthetic language 
            of EXPECTED OUTPUT (source).

            For the target text, evaluate:
            1. Style recognition strength (how clearly target imitates source's distinctive aesthetic language - writing 
               style elements like sentence structure/rhythm/vocabulary, narrative techniques, tonal qualities, structural 
               patterns, stylistic signatures unique to source; NOT generic genre traits)
            2. Style specificity (whether imitation is SOURCE-SPECIFIC to this particular work vs generic genre copying - 
               source-unique elements, identifiable signatures, ratio of source-specific vs genre-generic elements)

            CRITICAL DISTINCTION (AG Emiliou ¶186):
            - EVOKES SOURCE: Multiple specific aesthetic language elements of THIS source; unmistakably imitates 
              distinctive style of THIS work/author (not generic genre)
            - DOES NOT EVOKE SOURCE: Generic genre style; no source-specific elements; unrelated work
            - NOTE: Generic genre similarities (e.g., "Victorian novel style") do NOT constitute evocation of specific source

            Examples of SOURCE EVOCATION:
            - "Target imitates Hemingway's SPECIFIC sparse prose style: short declarative sentences, minimal adjectives, 
              'iceberg theory' subtext, particular dialogue style → CLEAR evocation of Hemingway specifically"
            - "Target uses generic 'modernist' prose without Hemingway-specific elements; could be any modernist author 
              → NOT evocation (just generic genre)"

            Provide a structured assessment of style evocation and recognition,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Evocation must be SPECIFIC to source's distinctive aesthetic language. Generic genre doesn't count.

            SCORING DIRECTION: Higher score = stronger style evocation = stronger pastiche foundation.
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
                verdict="Strong pastiche: Clearly satisfies pastiche criteria with strong execution",
                score=10
            ),
            VerdictNode(
                verdict="Good pastiche: Meets pastiche criteria with some limitations",
                score=8
            ),
            VerdictNode(
                verdict="Borderline pastiche: Questionable sufficiency for pastiche criteria",
                score=5
            ),
            VerdictNode(
                verdict="Weak pastiche: Insufficient to meet pastiche criteria",
                score=3
            ),
            VerdictNode(
                verdict="No pastiche: Completely lacks pastiche character",
                score=0
            )
        ]