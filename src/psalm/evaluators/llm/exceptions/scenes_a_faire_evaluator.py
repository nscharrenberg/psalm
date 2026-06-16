from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class ScenesAFaireEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "Scènes à Faire"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing scènes à faire presence (stock elements) under EU copyright law.
        Evaluates extent to which texts rely on unprotectable genre conventions, stock characters, 
        standard plot devices, common themes, and necessary technical elements vs original creative elaboration.

        CRITICAL: Measures STOCK-NESS/GENERICNESS (higher = more generic = less protectable = lower infringement risk).
        Score 10 = entirely stock/generic (unprotectable), Score 0 = entirely original (fully protectable).

        Use with other similarity evaluators to determine: similarity of unprotectable elements (low risk) 
        vs similarity of protectable expression (infringement risk).
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        elaboration_node = self.creative_elaboration_analysis()
        elaboration_node.children.append(judgement_node)

        technical_node = self.necessary_technical_elements_analysis()
        technical_node.children.append(elaboration_node)

        themes_node = self.thematic_commonplaces_analysis()
        themes_node.children.append(technical_node)

        plot_devices_node = self.standard_plot_devices_tropes_analysis()
        plot_devices_node.children.append(themes_node)

        characters_node = self.stock_characters_archetypes_analysis()
        characters_node.children.append(plot_devices_node)

        genre_node = self.genre_conventions_setting_analysis()
        genre_node.children.append(characters_node)

        dag = DeepAcyclicGraph(root_nodes=[genre_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "genre_conventions_setting": 0.25,
            "stock_characters_archetypes": 0.25,
            "standard_plot_devices_tropes": 0.20,
            "thematic_commonplaces": 0.15,
            "necessary_technical_elements": 0.10,
            "creative_elaboration": 0.05,  # Inverse: high originality = LOW scènes à faire
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            scènes à faire presence between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Genre Conventions & Setting Analysis"}} (weight: {weights['genre_conventions_setting']:.0%})
            - {{output from "Stock Characters & Archetypes Analysis"}} (weight: {weights['stock_characters_archetypes']:.0%})
            - {{output from "Standard Plot Devices & Tropes Analysis"}} (weight: {weights['standard_plot_devices_tropes']:.0%})
            - {{output from "Thematic Commonplaces Analysis"}} (weight: {weights['thematic_commonplaces']:.0%})
            - {{output from "Necessary Technical Elements Analysis"}} (weight: {weights['necessary_technical_elements']:.0%})
            - {{output from "Creative Elaboration Analysis (INVERSE)"}} (weight: {weights['creative_elaboration']:.0%})

            Assess the overall scènes à faire presence holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL REMINDER - SCORING DIRECTION:
            - This measures STOCK-NESS/GENERICNESS, not similarity or quality
            - Higher score = MORE stock elements = LESS protectable = LOWER infringement risk
            - Lower score = MORE original = MORE protectable = HIGHER infringement risk if similar

            EU Copyright Principles:
            1. Only ORIGINAL expression is protected (Berne Convention Art. 9(2))
            2. Originality = author's own intellectual creation (CJEU Infopaq)
            3. Standard elements dictated by genre/theme = unprotectable scènes à faire
            4. Stock characters, plot devices, settings, themes without original elaboration = unprotectable
            """,
            children=self.verdict_nodes(),
        )

    def creative_elaboration_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Creative Elaboration Analysis (INVERSE)",
            instructions=f"""
            Analyze extent of distinctive original creative expression in BOTH texts (EXPECTED OUTPUT and ACTUAL OUTPUT).

            **CRITICAL - INVERSE DIMENSION**: This measures ORIGINALITY to contextualize scènes à faire.
            This dimension is scored INVERSELY (high originality = low dimension score = reduces final scènes à faire score).

            For both texts, evaluate:
            1. Distinctive voice/style (unique narrative voice, original prose style, distinctive language use)
            2. Original descriptive detail (creative descriptions, unique sensory details, imaginative imagery)
            3. Psychological depth (complex character psychology beyond archetypes, nuanced emotional portrayal)
            4. Unique dialogue (distinctive dialogue styles, original character voices, creative linguistic choices)
            5. Innovative structure (original narrative structure, creative pacing, distinctive organization)
            6. Creative worldbuilding (imaginative world details beyond genre requirements, original concepts)
            7. Original insights (unique perspectives, fresh observations, distinctive thematic treatment)

            LEGAL PRINCIPLE (CJEU Infopaq C-5/08 ¶45, Painer C-145/10):
            - Copyright protects only "author's own intellectual creation"
            - Requires originality = reflecting author's creative choices
            - Generic expression (no creative choices) = unprotectable
            - Distinctive original expression = protectable

            Examples:
            - HIGH originality (scores 0-3): Highly distinctive voice, imaginative descriptions, complex psychology, 
              unique dialogue, innovative structure → LOW scènes à faire (more protectable)
            - LOW originality (scores 8-10): Generic voice, stock descriptions, flat characters, predictable dialogue, 
              standard structure → HIGH scènes à faire (less protectable)

            Provide a structured assessment of creative elaboration (measuring genericness inversely),
            and categorize it into one of the following [{verdict_texts}].

            INVERSE SCORING: Rate GENERICNESS (0 = entirely original/distinctive, 10 = entirely generic/stock).
            High originality naturally reduces final scènes à faire score, indicating more protectable content.

            CRITICAL: Assess BOTH texts together. If both highly original, score low. If both generic, score high.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def necessary_technical_elements_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Necessary Technical Elements Analysis",
            instructions=f"""
            Analyze extent to which BOTH texts rely on genre-required and purely functional elements.

            For both texts, evaluate:
            1. Genre-required elements (technical components necessary for genre coherence - fantasy magic system 
               rules, detective investigation procedures, sci-fi technology explanations, romance relationship 
               development beats, thriller suspense building, legal/medical professional procedures)
            2. Functional elements (purely mechanical/functional components without creative elaboration - generic 
               exposition, standard transitions, basic dialogue tags, functional descriptions, narrative mechanics)

            CRITICAL DISTINCTION (Scènes à Faire Doctrine):
            - Elements TECHNICALLY NECESSARY for genre = unprotectable (functional necessity, not creative choice)
            - Elements PURELY FUNCTIONAL (mechanical) = unprotectable (no creative expression)
            - GENERIC: Magic system rules, investigation procedures, tech explanations, exposition, transitions
            - ORIGINAL: Distinctive elaboration of required elements, creative functional approaches

            Examples:
            - HIGH scènes à faire (scores 8-10): Heavy reliance on necessary genre components; generic functional 
              elements; standard magic rules, investigation procedures, "Once upon a time" exposition, basic dialogue tags
            - LOW scènes à faire (scores 0-3): Minimal genre requirements or highly original handling; creative 
              functional elaboration; distinctive approaches to necessary elements

            Provide a structured assessment of necessary technical elements,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Genre requirements and functional elements are needed but unprotectable unless distinctively elaborated.

            SCORING DIRECTION: Higher score = more reliance on necessary/functional elements = less protectable.

            CRITICAL: Assess BOTH texts together. If both heavily rely on genre requirements, score high.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def thematic_commonplaces_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Thematic Commonplaces Analysis",
            instructions=f"""
            Analyze extent to which BOTH texts rely on standard themes and conventional conflicts.

            For both texts, evaluate:
            1. Standard themes (common themes without original treatment - universal: good vs evil, love conquers all, 
               coming of age, identity/belonging, power corrupts, redemption, sacrifice; genre: chosen one/destiny, 
               soulmates, conspiracy, humanity vs technology)
            2. Conventional conflicts (standard conflict types without original elaboration - classical: man vs man/
               self/society/nature/technology; relationship: parent-child, siblings, romantic; genre: hero vs villain, 
               good vs evil; internal: identity crisis, duty vs desire)

            CRITICAL DISTINCTION (Berne Art. 9(2)):
            - Themes are IDEAS, not expression → never protectable per se
            - Generic themes/conflicts = unprotectable scènes à faire
            - GENERIC: "Good vs evil" with standard treatment; typical "coming of age"; predictable "love conquers all"
            - ORIGINAL: Themes explored with unique perspective, moral complexity, distinctive treatment; conflicts with 
              original psychological depth

            Examples:
            - HIGH scènes à faire (scores 8-10): Entirely generic themes with standard treatment; conventional conflicts 
              with no original complexity; "good vs evil" battle with no nuance
            - LOW scènes à faire (scores 0-3): Themes explored with unique philosophical perspective; conflicts with 
              distinctive psychological complexity; original moral dimensions

            Provide a structured assessment of thematic commonplaces,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: All works explore themes/conflicts. What matters is whether treatment is generic (stock) or distinctive (original).

            SCORING DIRECTION: Higher score = more generic thematic treatment = less protectable.

            CRITICAL: Assess BOTH texts together. If both use generic themes/conflicts, score high.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def standard_plot_devices_tropes_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Standard Plot Devices & Tropes Analysis",
            instructions=f"""
            Analyze extent to which BOTH texts rely on common plot devices and narrative tropes.

            For both texts, evaluate:
            1. Common plot devices (stock mechanisms/twists - identity/deception: mistaken identity, secret identity; 
               timing: race against time, deadline; discovery: hidden truth revealed; relationship: love triangle, 
               forbidden romance; conflict: false accusation, betrayal; quest: chosen one prophecy, MacGuffin; 
               reversal: traitor revealed; resolution: deus ex machina, sacrifice)
            2. Narrative tropes (standard storytelling patterns - structure: hero's journey, three-act, fish out of 
               water; character: redemption arc, fall from grace, coming of age; dramatic: irony, Chekhov's gun, 
               red herring; scene: training montage, big reveal, sacrifice; resolution: happily ever after, twist ending)

            CRITICAL DISTINCTION:
            - Common plot devices/tropes = scènes à faire = unprotectable
            - STOCK: "Race against time" with bomb countdown; typical "betrayal by trusted ally"; generic "training 
              montage"; standard hero's journey with expected beats; predictable "love triangle"
            - ORIGINAL: Original plot mechanisms; unique twists on devices; subverted tropes; distinctive combinations

            Examples:
            - HIGH scènes à faire (scores 8-10): Entirely stock devices in standard form; typical tropes with no 
              subversions; generic "chosen one prophecy," standard hero's journey, predictable betrayal reveals
            - LOW scènes à faire (scores 0-3): Original plot mechanisms; subverted/deconstructed tropes; unique 
              combinations; distinctive storytelling approaches

            Provide a structured assessment of plot devices and tropes,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Using standard devices/tropes isn't inherently bad, but they're unprotectable. Original twists add protectability.

            SCORING DIRECTION: Higher score = more stock devices/tropes = less protectable.

            CRITICAL: Assess BOTH texts together. If both heavily use stock devices, score high.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def stock_characters_archetypes_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Stock Characters & Archetypes Analysis",
            instructions=f"""
            Analyze extent to which BOTH texts rely on stock character archetypes and standard relationship types.

            For both texts, evaluate:
            1. Character archetypes (generic character types without distinctive elaboration - stock heroes: chosen one, 
               reluctant hero, orphan protagonist; stock mentors: wise old mentor, magical guide; stock villains: evil 
               overlord, corrupt authority; stock supporting: loyal sidekick, comic relief, love interest, damsel, 
               tech genius, traitor)
            2. Standard relationships (generic relationship types without original dynamics - romantic: love triangle, 
               forbidden love, enemies-to-lovers, instalove; mentorship: wise mentor guides naive student; familial: 
               estranged siblings reconciling, parent-child conflict; friendship: loyal best friend, band of misfits; 
               rivalry: hero vs villain, competing love interests)

            CRITICAL DISTINCTION:
            - Stock characters/archetypes WITHOUT distinctive elaboration = unprotectable scènes à faire
            - STOCK: Pure archetypes with no distinctive personality/backstory/motivation - "wise old wizard mentor," 
              "evil dark lord," "spunky teenage chosen one"; generic "love triangle," standard "mentor-student"
            - ORIGINAL: Characters with complex unique personality, detailed backstory, distinctive psychological depth, 
              even if loosely archetypal; relationships with unique dynamics, complex psychological texture

            Examples:
            - HIGH scènes à faire (scores 8-10): Pure stock archetypes; no distinctive elaboration; completely generic 
              character types; generic relationships with standard dynamics
            - LOW scènes à faire (scores 0-3): Highly distinctive characters with complex psychology; minimal archetypal 
              elements; original characterization; unique relationship dynamics

            Provide a structured assessment of stock characters and archetypes,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Starting from archetype is OK if substantially elaborated with distinctive traits. Pure archetypes = high score.

            SCORING DIRECTION: Higher score = more stock characters/relationships = less protectable.

            CRITICAL: Assess ALL significant characters/relationships in BOTH texts together.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def genre_conventions_setting_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Genre Conventions & Setting Analysis",
            instructions=f"""
            Analyze extent to which BOTH texts (EXPECTED OUTPUT and ACTUAL OUTPUT) rely on genre conventions and standard settings.

            For both texts, evaluate:
            1. Genre-specific plot elements (standard plot structures/events dictated by genre - detective: crime → 
               investigation → revelation; romance: meet → obstacle → resolution; fantasy: quest → trials → climax; 
               thriller: hook → rising tension → twist → climax; hero's journey: call → refusal → mentor → trials)
            2. Standard settings & worldbuilding (common/expected settings for genre - sci-fi: spaceships, futuristic 
               cities, alien planets; fantasy: medieval castles, elves/dwarves/orcs, standard magic systems; contemporary: 
               high school, suburban homes; dystopian: oppressive government, divided society; legal/medical: courtrooms, 
               hospitals)

            CRITICAL DISTINCTION (Scènes à Faire Doctrine):
            - Elements DICTATED BY GENRE = unprotectable (not author's creative choice)
            - GENERIC: Detective story following exact "murder → investigation → revelation" with no twists; romance with 
              standard "meet-cute → misunderstanding → resolution"; fantasy with generic medieval European setting, 
              standard elves/dwarves, typical magic system
            - ORIGINAL: Plot subverts genre conventions with unique structure; highly original setting elaboration; 
              distinctive worldbuilding unlike standard tropes

            Examples:
            - HIGH scènes à faire (scores 8-10): Plot follows exact standard genre structure; completely stock genre beats; 
              entirely genre-standard settings; no distinctive elaboration
            - LOW scènes à faire (scores 0-3): Subverts genre conventions; unique narrative structure; highly original 
              settings/worldbuilding; distinctive elaboration beyond requirements

            Provide a structured assessment of genre conventions and settings,
            and categorize it into one of the following [{verdict_texts}].

            NOTE: Identify genre from texts, assess how much follows standard conventions vs distinctive elaboration.

            SCORING DIRECTION: Higher score = more genre-dictated stock elements = less protectable.

            CRITICAL: Assess BOTH texts together. If both heavily genre-standard, score high. If both original, score low.
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
                verdict="Entirely scènes à faire: heavily stock/generic elements (unprotectable)",
                score=10
            ),
            VerdictNode(
                verdict="Mostly scènes à faire: predominantly stock elements (limited protectability)",
                score=8
            ),
            VerdictNode(
                verdict="Balanced: equal stock and original elements (uncertain protectability)",
                score=5
            ),
            VerdictNode(
                verdict="Mostly original: predominantly distinctive creative expression (substantial protectability)",
                score=3
            ),
            VerdictNode(
                verdict="Entirely original: heavily distinctive creative elaboration (fully protectable)",
                score=0
            )
        ]