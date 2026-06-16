from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class ParodySatireEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Parody/Satire"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing parody/satire character under EU copyright law (CJEU Deckmyn test).
        Evaluates whether target text constitutes protected parody/satire of source text by measuring:
        source evocation, noticeable differences, humorous/mocking character, critical purpose, and fair balance.

        CRITICAL: Measures PARODY STRENGTH (higher = stronger exception defense), NOT similarity.
        Score 10 = strong parody (protected), Score 0 = no parody (unprotected).
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        balance_node = self.fair_balance_context_analysis()
        balance_node.children.append(judgement_node)

        mockery_node = self.mocking_critical_character_analysis()
        mockery_node.children.append(balance_node)

        humor_node = self.humorous_character_analysis()
        humor_node.children.append(mockery_node)

        differences_node = self.noticeable_differences_transformation_analysis()
        differences_node.children.append(humor_node)

        evocation_node = self.source_evocation_recognition_analysis()
        evocation_node.children.append(differences_node)

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
            "source_evocation_recognition": 0.30,
            "noticeable_differences_transformation": 0.25,
            "humorous_character": 0.20,
            "mocking_critical_character": 0.15,
            "fair_balance_context": 0.10,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            parody/satire strength between EXPECTED OUTPUT (source) and ACTUAL OUTPUT (target).

            Consider the outputs from:
            - {{output from "Source Work Evocation/Recognition Analysis"}} (weight: {weights['source_evocation_recognition']:.0%})
            - {{output from "Noticeable Differences/Transformation Analysis"}} (weight: {weights['noticeable_differences_transformation']:.0%})
            - {{output from "Humorous Character Analysis"}} (weight: {weights['humorous_character']:.0%})
            - {{output from "Mocking/Critical Character Analysis"}} (weight: {weights['mocking_critical_character']:.0%})
            - {{output from "Fair Balance & Context Analysis"}} (weight: {weights['fair_balance_context']:.0%})

            Assess the overall parody/satire strength holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL REMINDER - SCORING DIRECTION:
            - This measures PARODY STRENGTH, not similarity
            - Higher score = STRONGER parody = STRONGER exception defense = protected under Deckmyn
            - Lower score = WEAKER/NO parody = NO exception defense = potential infringement if copying exists

            CJEU Deckmyn Requirements:
            1. Must evoke existing work (recognizably reference source)
            2. Must be noticeably different from source (transformation)
            3. Must express humor OR mockery (comedic/critical character)
            4. Must respect fair balance (proportionate use, no discrimination)
            """,
            children=self.verdict_nodes(),
        )

    def fair_balance_context_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Fair Balance & Context Analysis",
            instructions=f"""
            Analyze fair balance and contextual factors of ACTUAL OUTPUT (target) in relation to EXPECTED OUTPUT (source).

            For the target text, evaluate:
            1. Proportionality of use (extent of source taking, necessity for parodic purpose, transformative ratio, 
               market impact - whether use could substitute for or harm source market)
            2. Non-discriminatory character (absence of discriminatory messaging harming dignity - race, ethnicity, 
               religion, sex, gender, sexual orientation, disability, age stereotyping/hate speech)

            CRITICAL DISTINCTION (Deckmyn ¶27-32):
            - PROPORTIONATE: Minimal/moderate taking necessary for parody; highly transformative; no market harm
            - DISPROPORTIONATE: Excessive taking unjustified by purpose; minimally transformative; substitutes original
            - NON-DISCRIMINATORY: Respects human dignity; no harmful stereotyping/hate speech
            - DISCRIMINATORY: Contains discriminatory messaging; harms dignity (DISQUALIFYING per Deckmyn ¶31-32)

            Examples of assessment:
            - "Uses only 3 key characters from source, transformed significantly; adds substantial original content; 
              unlikely to harm source market; no discriminatory content → EXCELLENT fair balance"
            - "Copies nearly entire plot with minimal changes; could substitute for original; adds little transformative 
              content → POOR proportionality"
            - "Contains offensive racial stereotypes that harm dignity → DISCRIMINATORY (may disqualify parody defense 
              regardless of other factors)"

            Provide a structured assessment of fair balance and context,
            and categorize it into one of the following [{verdict_texts}].

            WARNING: Low score on non-discrimination may DISQUALIFY parody defense regardless of other dimensions.

            SCORING DIRECTION: Higher score = better fair balance = stronger parody protection.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def mocking_critical_character_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Mocking/Critical Character Analysis",
            instructions=f"""
            Analyze mocking/critical character of ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Critical commentary (presence and strength of critique, satire, analytical perspective - direct/implicit 
               criticism of source work, author, genre, or broader societal issues)
            2. Target of mockery (what is being mocked and how clearly - source work itself, author's style, genre 
               conventions, broader subjects using source as vehicle, or mixed targets)

            CRITICAL DISTINCTION (Deckmyn ¶20):
            - MOCKING: Clear critical/satirical purpose; discernible target; sustained mockery/commentary
            - NON-MOCKING: No critical dimension; purely entertaining or straight copying; no identifiable target
            - NOTE: Mockery is ALTERNATIVE to humor (work can have mockery without humor and still be parody)

            Examples of MOCKING character:
            - "Target transforms heroic source protagonist into bumbling fool to critique toxic masculinity tropes in 
              fantasy genre; sustained satirical commentary throughout → STRONG mockery"
            - "Target uses source's dystopian setting as vehicle to critique current government surveillance policies; 
              clear political satire → CLEAR mockery of broader subject using source"
            - "Target simply retells source story with different names; no critical perspective or commentary → NO mockery"

            Provide a structured assessment of mocking/critical character,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Parody requires humor OR mockery (at least one). If BOTH humor and mockery are absent, NO parody.

            SCORING DIRECTION: Higher score = stronger mocking/critical character = stronger parody qualification.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def humorous_character_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Humorous Character Analysis",
            instructions=f"""
            Analyze humorous character of ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Humor presence & type (existence, nature, and strength of comedic elements - wit/wordplay, irony, satire, 
               absurdity, exaggeration, incongruity, parody-specific humor from transformation)
            2. Comedic intent clarity (how clearly work signals its humorous purpose through explicit cues, tonal markers, 
               structural choices like punchlines, genre signals, audience recognition)

            CRITICAL DISTINCTION (Deckmyn ¶20):
            - HUMOROUS: Clear, intentional humor throughout; comedic character evident; signals humorous purpose
            - NON-HUMOROUS: No humor or accidental humor only; serious/neutral tone; no comedic intent
            - NOTE: Humor is ALTERNATIVE to mockery (work can have humor without mockery and still be parody)

            Examples of HUMOROUS character:
            - "Target transforms source's grim battle scenes into absurdist slapstick with characters slipping on banana 
              peels; consistent comedic tone; impossible to read as serious → STRONG humor"
            - "Target adds witty dialogue and ironic commentary throughout source's plot; clear playful tone; obviously 
              comedic → CLEAR humor"
            - "Target retells source story seriously with no comedic elements; earnest tone; no humor signals → NO humor"

            Provide a structured assessment of humorous character,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Parody requires humor OR mockery (at least one). If BOTH humor and mockery are absent, NO parody.

            SCORING DIRECTION: Higher score = stronger humorous character = stronger parody qualification.
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
            1. Substantive changes (meaningful alterations to characters - traits/roles/motivations; plot - events/outcomes/
               conflicts; setting - time/place/context; tone - serious→comedic, dramatic→satirical; meaning - transformed 
               message/themes; perspective - different POV/voice)
            2. Creative transformation (degree of original creative input - new characters/plot elements/settings/themes; 
               new artistic/stylistic/structural decisions; fresh perspective/commentary; new meaning/message/function 
               created)

            CRITICAL DISTINCTION (Deckmyn ¶21):
            - NOTICEABLY DIFFERENT: Major substantive changes; significant creative transformation; new artistic vision
            - NOT NOTICEABLY DIFFERENT: Minimal changes; superficial alterations only (name changes without substance); 
              pure copying; nearly identical
            - NOTE: Without noticeable differences, work is mere copy, NOT parody (even if humorous)

            Examples of NOTICEABLE DIFFERENCES:
            - "Target transforms source's tragic romance into absurdist comedy; protagonist becomes bumbling antihero; 
              setting changes from medieval to modern corporate office; adds extensive original satirical content → 
              MAJOR transformation"
            - "Target changes character names and minor setting details but keeps plot, relationships, themes identical; 
              minimal creative input → NOT noticeably different (just superficial changes)"

            Provide a structured assessment of differences and transformation,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Differences must be SUBSTANTIVE, not superficial. Cosmetic changes alone insufficient.

            SCORING DIRECTION: Higher score = greater transformation = stronger parody qualification.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def source_evocation_recognition_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Source Work Evocation/Recognition Analysis",
            instructions=f"""
            Analyze how clearly and specifically ACTUAL OUTPUT (target) evokes EXPECTED OUTPUT (source work).

            For the target text, evaluate:
            1. Recognizability strength (how clearly target makes source recognizable through character references - 
               names/traits/roles; plot/scene references - specific events/sequences; style mimicry - deliberate 
               imitation of writing style/voice/tone; setting references - specific locations/world-building; 
               thematic references - core themes/motifs; direct quotations or paraphrases)
            2. Evocation specificity (whether references are SOURCE-SPECIFIC to this particular work vs. generic 
               genre tropes - unique elements distinctive to source; named references; signature/iconic elements; 
               ratio of source-specific vs genre-generic elements)

            CRITICAL DISTINCTION (Deckmyn ¶20):
            - EVOKES SOURCE: Multiple explicit, specific references to THIS source work; unmistakably recognizable; 
              source-specific elements (not just genre conventions)
            - DOES NOT EVOKE SOURCE: No clear references; generic similarities only; unrelated work; possible 
              accidental resemblance
            - NOTE: Generic genre similarities (e.g., both fantasy) do NOT constitute evocation of specific source

            Examples of SOURCE EVOCATION:
            - "Target uses exact character names from source (Harry, Hermione, Ron), references Hogwarts school, 
              mentions Voldemort, uses specific spell names → CLEAR evocation of Harry Potter specifically"
            - "Target features generic wizard school with generic evil villain and generic magic; no specific 
              Harry Potter elements → NOT evocation (just generic fantasy genre)"

            Provide a structured assessment of source evocation and recognition,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Evocation must be SPECIFIC to source work. Generic genre similarities don't count.

            SCORING DIRECTION: Higher score = stronger evocation = better parody foundation.
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
                verdict="Strong parody: Clearly satisfies Deckmyn criteria with strong execution",
                score=10
            ),
            VerdictNode(
                verdict="Good parody: Meets Deckmyn criteria with some limitations",
                score=8
            ),
            VerdictNode(
                verdict="Borderline parody: Questionable sufficiency for Deckmyn test",
                score=5
            ),
            VerdictNode(
                verdict="Weak parody: Insufficient to meet Deckmyn test",
                score=3
            ),
            VerdictNode(
                verdict="No parody: Completely lacks parodic character",
                score=0
            )
        ]