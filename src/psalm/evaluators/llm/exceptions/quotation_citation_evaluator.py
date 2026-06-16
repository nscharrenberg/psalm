from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class QuotationCitationEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Quotation/Citation"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing quotation/citation character under EU copyright law 
        (Directive 2001/29/EC Art. 5(3)(d), CJEU Funke Medien/Spiegel Online).
        Evaluates whether target text's use of source text constitutes protected quotation by measuring:
        quotation presence, legitimate purpose, fair practice, attribution, fair balance, and prior disclosure.

        CRITICAL: Measures QUOTATION STRENGTH (higher = stronger exception defense), NOT copying amount.
        Score 10 = strong quotation (protected), Score 0 = no quotation (unprotected).
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        disclosed_node = self.work_already_disclosed_analysis()
        disclosed_node.children.append(judgement_node)

        balance_node = self.fair_balance_justification_analysis()
        balance_node.children.append(disclosed_node)

        attribution_node = self.attribution_acknowledgment_analysis()
        attribution_node.children.append(balance_node)

        fair_practice_node = self.fair_practice_proportionality_analysis()
        fair_practice_node.children.append(attribution_node)

        purpose_node = self.legitimate_purpose_analysis()
        purpose_node.children.append(fair_practice_node)

        identification_node = self.quotation_identification_extraction_analysis()
        identification_node.children.append(purpose_node)

        dag = DeepAcyclicGraph(root_nodes=[identification_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "quotation_identification": 0.25,
            "legitimate_purpose": 0.25,
            "fair_practice_proportionality": 0.20,
            "attribution_acknowledgment": 0.15,
            "fair_balance_justification": 0.10,
            "work_already_disclosed": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            quotation/citation strength between EXPECTED OUTPUT (source) and ACTUAL OUTPUT (target).

            Consider the outputs from:
            - {{output from "Quotation Identification & Extraction Analysis"}} (weight: {weights['quotation_identification']:.0%})
            - {{output from "Legitimate Purpose Analysis"}} (weight: {weights['legitimate_purpose']:.0%})
            - {{output from "Fair Practice & Proportionality Analysis"}} (weight: {weights['fair_practice_proportionality']:.0%})
            - {{output from "Attribution & Source Acknowledgment Analysis"}} (weight: {weights['attribution_acknowledgment']:.0%})
            - {{output from "Fair Balance & Justification Analysis"}} (weight: {weights['fair_balance_justification']:.0%})
            - {{output from "Work Already Disclosed Analysis"}} (weight: {weights['work_already_disclosed']:.0%})

            Assess the overall quotation/citation strength holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL REMINDER - SCORING DIRECTION:
            - This measures QUOTATION STRENGTH, not copying amount
            - Higher score = STRONGER quotation = STRONGER exception defense = protected under Art. 5(3)(d)
            - Lower score = WEAKER/NO quotation = NO exception defense = potential infringement if copying exists

            EU Law Requirements (Art. 5(3)(d)):
            1. Must actually quote/cite source text (textual reproduction)
            2. Must serve legitimate purpose (criticism, review, news, teaching, research)
            3. Must comply with fair practice (proportionate use, integrated into analysis)
            4. Must include attribution (source and author acknowledgment unless impossible)
            5. Source must be already disclosed (previously publicly available)
            """,
            children=self.verdict_nodes(),
        )

    def work_already_disclosed_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Work Already Disclosed Analysis",
            instructions=f"""
            Analyze whether EXPECTED OUTPUT (source work) was already lawfully made available to the public before 
            ACTUAL OUTPUT (target) was created.

            For the source work, evaluate:
            1. Prior disclosure (whether source was publicly accessible - published, performed, exhibited, made 
               available online - before target's creation; whether disclosure was lawful/authorized by rightholder; 
               temporal sequence confirmation)

            CRITICAL DISTINCTION (Art. 5(3)(d)):
            - DISCLOSED: Source was published book, public article, exhibited artwork, performed work, online content 
              before target; lawfully made public
            - NOT DISCLOSED: Source was unpublished manuscript, private letter, confidential document not made publicly 
              available; OR disclosed after target creation
            - NOTE: Quotation exception does NOT apply to unpublished works (protects first publication right)

            Examples of assessment:
            - "Source is published novel from 2015; target written in 2023; clearly publicly available before target → 
              CLEARLY DISCLOSED (10/10)"
            - "Source appears to be published article based on attribution; likely pre-dates target → LIKELY DISCLOSED (7-8/10)"
            - "Source is unpublished manuscript, private correspondence not made public → NOT DISCLOSED (0-1/10)"

            Provide a structured assessment of prior disclosure,
            and categorize it into one of the following [{verdict_texts}].

            PRACTICAL NOTE: Most cases involve published works (books, articles) where this is satisfied. Issue only 
            arises with unpublished materials.

            WARNING: If source not previously disclosed (scores 0-3), quotation exception CANNOT apply regardless of 
            other factors.

            SCORING DIRECTION: Higher score = clearer prior disclosure = exception applicable.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def fair_balance_justification_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Fair Balance & Justification Analysis",
            instructions=f"""
            Analyze fair balance and justification of quotations in ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Necessity (whether quotations are necessary for stated purpose - could it be achieved without quoting? 
               Are exact words required for textual analysis, or could paraphrase/summary suffice? Type of purpose 
               determines necessity level)
            2. Market impact (whether quotation could substitute for or harm market for original work - does target 
               serve same purpose/market as source? Could reader get source's value from target instead? Extent of 
               reproduction relative to commercial harm potential)

            CRITICAL DISTINCTION:
            - BALANCED: Quotations necessary for purpose (textual criticism requires exact words); serves different 
              market than source (criticism ≠ original enjoyment); no substitution effect; minimal/no market harm
            - UNBALANCED: Quotations unnecessary (purpose achievable without quoting); serves same/overlapping market; 
              substitution effect (reader doesn't need source); clear market harm potential

            Examples of assessment:
            - "Target is literary criticism requiring close textual analysis; quotes brief passages for examination; 
              serves different purpose than source novel; no market substitution → EXCELLENT balance (10/10)"
            - "Target reproduces extensive passages; purpose could be achieved with less quotation; extensive reproduction 
              could harm source sales → POOR balance (2-3/10)"

            Provide a structured assessment of fair balance and justification,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Low scores (0-4) may undermine exception even if other criteria satisfied.

            SCORING DIRECTION: Higher score = better fair balance = stronger exception foundation.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def attribution_acknowledgment_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Attribution & Source Acknowledgment Analysis",
            instructions=f"""
            Analyze attribution and source acknowledgment in ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Source identification (whether source work is identified/acknowledged - full title stated? Source 
               identifiable from context? Ordinary reader could determine quoted work? Identified for all quotations 
               or only once?)
            2. Author identification (whether author/rightholder is named - full name stated? Author identifiable 
               from context? Ordinary reader could determine quoted author? Named for all quotations or only once?)

            CRITICAL DISTINCTION (Funke Medien/Spiegel Online):
            - ATTRIBUTED: Source work clearly identified (full title or unambiguous description); author clearly 
              named (full name or recognizable reference); both indicated for all/most quotations
            - NOT ATTRIBUTED: Source not identified or very vague; author not named or unidentifiable; ordinary 
              reader cannot determine what work/who author is
            - EXCEPTION: Attribution required "unless impossible" (genuinely impossible, not merely inconvenient - 
              e.g., anonymous work, unknown author)

            Examples of assessment:
            - "Target states: 'In *Harry Potter*, J.K. Rowling writes: [quote]' → FULL attribution (10/10)"
            - "Target quotes extensively but never identifies source work or author; appears as original text → 
              NO attribution (0-1/10)"
            - "Target identifies source (book title) but not author → PARTIAL attribution (5-6/10)"

            Provide a structured assessment of attribution and acknowledgment,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Attribution is MANDATORY under CJEU Funke Medien/Spiegel Online. Failure significantly undermines 
            exception defense.

            SCORING DIRECTION: Higher score = better attribution = stronger exception foundation.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def fair_practice_proportionality_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Fair Practice & Proportionality Analysis",
            instructions=f"""
            Analyze fair practice and proportionality of quotations in ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Extent of taking (how much source text is reproduced - brief excerpts, several passages, or extensive 
               reproduction? Is amount necessary/proportionate for stated purpose? Could purpose be achieved with less? 
               Selective extracts or wholesale reproduction?)
            2. Transformative context (whether quotations are integrated into original analysis vs standalone - do 
               quotations embed within target's commentary/critique? Does target add substantial original content? 
               Do quotations serve new purpose/function? Could quotations stand alone as substitute for source? 
               Is added value provided?)

            CRITICAL DISTINCTION (Art. 5(3)(d) "fair practice"):
            - FAIR PRACTICE: Minimal/moderate taking proportionate to purpose (brief selective extracts); highly 
              integrated into extensive original analysis/critique; substantial added value; serves new purpose; 
              cannot substitute for source
            - UNFAIR PRACTICE: Excessive taking unjustified by purpose (wholesale reproduction); standalone quotations 
              without meaningful integration; minimal original content; quotations dominate; acts as substitute for 
              source; pure compilation/anthology

            Examples of assessment:
            - "Target quotes 3 brief passages from source novel, each embedded in extensive critical analysis paragraph; 
              original commentary far exceeds quotations → EXCELLENT fair practice (10/10)"
            - "Target reproduces 20 pages of source with minimal commentary; quotations strung together with brief 
              transitions; could substitute for reading original → POOR fair practice (2-3/10)"

            Provide a structured assessment of fair practice and proportionality,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Quotations must be USED for criticism/review (integrated), not merely REPRODUCED (standalone).

            SCORING DIRECTION: Higher score = better fair practice = stronger exception foundation.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def legitimate_purpose_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Legitimate Purpose Analysis",
            instructions=f"""
            Analyze legitimate purpose served by quotations in ACTUAL OUTPUT (target).

            For the target text, evaluate:
            1. Purpose identification (what purpose quotations serve - criticism of source work? Review/assessment? 
               News reporting incorporating source? Teaching/education? Scientific research/analysis? 
               Public debate/commentary using source as evidence?)
            2. Purpose substantiation (whether purpose is genuinely pursued with substantive engagement - depth of 
               analysis/critique of quoted material? Extent of original commentary/argument on quotes? Integration 
               into target's discourse? Ratio of quotation to commentary? Is engagement meaningful or superficial/
               pretextual?)

            CRITICAL DISTINCTION (Art. 5(3)(d) "purposes such as criticism or review"):
            - LEGITIMATE PURPOSE: Clear identifiable purpose (criticism, review, news, teaching, research); genuinely 
              pursued through substantive engagement; extensive original analysis/critique of quotes; commentary 
              exceeds quotations; meaningful engagement demonstrating genuine critical/analytical intent
            - NO/WEAK PURPOSE: No clear legitimate purpose; appears pretextual (decorative quotes, commercial 
              anthology, entertainment use); minimal/no engagement with quoted material; quotations dominate with 
              negligible commentary; superficial labels without analysis

            Examples of assessment:
            - "Target is academic paper critically analyzing source novel's themes; provides extensive textual analysis 
              of quoted passages with original scholarly argument → STRONG legitimate purpose (10/10)"
            - "Target quotes source extensively but provides no commentary, analysis, or critique; appears to be 
              commercial compilation for entertainment → NO legitimate purpose (0-1/10)"

            Provide a structured assessment of legitimate purpose,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Purpose must be GENUINE, not pretext. Mere assertion without substantive pursuit insufficient.

            SCORING DIRECTION: Higher score = stronger legitimate purpose = stronger exception foundation.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def quotation_identification_extraction_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Quotation Identification & Extraction Analysis",
            instructions=f"""
            Analyze whether ACTUAL OUTPUT (target) quotes EXPECTED OUTPUT (source work) and how explicitly.

            For the target text, evaluate:
            1. Quotation presence (whether target reproduces extracts from source - verbatim/near-verbatim quotations? 
               Close paraphrase maintaining source expression? How much reproduction: sentences, paragraphs, passages? 
               Extent of textual overlap?)
            2. Quotation explicitness (whether quotations are marked/attributed vs unmarked - quotation marks/block 
               quotes used? Attribution markers like "According to [source]", "As X writes"? Citation indicators 
               like footnotes? Or implicit/unmarked reproduction appearing as original text?)

            CRITICAL DISTINCTION:
            - QUOTATION PRESENT: Extensive/substantial/notable verbatim or near-verbatim reproduction of source text; 
              target clearly quotes source passages; ideally with explicit quotation marks and attribution markers
            - NO QUOTATION: No textual reproduction; at most brief phrase overlap or general summary/paraphrase; 
              target does not actually quote source in legal sense

            Examples of assessment:
            - "Target reproduces multiple verbatim passages from source, each in quotation marks with attribution 
              'As Smith writes in *Book*: [quote]' → STRONG quotation presence and explicitness (10/10)"
            - "Target paraphrases source ideas but includes no verbatim/near-verbatim reproduction; general summary 
              only → NO quotation (0-1/10)"
            - "Target reproduces source text but without quotation marks or attribution; appears as original writing → 
              QUOTATION present but entirely implicit (5/10 presence, 0-1/10 explicitness)"

            Provide a structured assessment of quotation identification and extraction,
            and categorize it into one of the following [{verdict_texts}].

            CRITICAL: Without textual reproduction, NO quotation exception applies regardless of purpose. Explicit 
            marking strengthens but is not strictly required.

            SCORING DIRECTION: Higher score = clearer quotation = better foundation for exception.
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
                verdict="Strong quotation: Clearly satisfies Art. 5(3)(d) criteria with strong execution",
                score=10
            ),
            VerdictNode(
                verdict="Good quotation: Meets Art. 5(3)(d) criteria with some limitations",
                score=8
            ),
            VerdictNode(
                verdict="Borderline quotation: Questionable sufficiency for Art. 5(3)(d)",
                score=5
            ),
            VerdictNode(
                verdict="Weak quotation: Insufficient to meet Art. 5(3)(d) criteria",
                score=3
            ),
            VerdictNode(
                verdict="No quotation: Completely lacks quotation character",
                score=0
            )
        ]