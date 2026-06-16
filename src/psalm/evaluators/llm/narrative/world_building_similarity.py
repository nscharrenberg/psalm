from deepeval.metrics import DAGMetric, DeepAcyclicGraph
from deepeval.metrics.dag import NonBinaryJudgementNode, VerdictNode, TaskNode
from deepeval.test_case import LLMTestCaseParams
from dotenv import load_dotenv

from psalm.evaluators.llm.base_dag_evaluator import BaseDagEvaluator

load_dotenv()


class WorldBuildingSimilarityEvaluator(BaseDagEvaluator):
    @classmethod
    def name(cls) -> str:
        return "WorldBuilding Similarity"

    @classmethod
    def description(cls) -> str:
        return """
        LLM-based evaluator assessing worldbuilding similarity for EU copyright analysis.
        Evaluates protectable world expression (specific geographic design, rules/systems, 
        cultural elaboration, historical detail, material specificity) vs unprotectable 
        generic world types. Focuses on creative world construction beyond stock settings.
        """

    def _build_evaluation_dag(
        self, model_name: str = "gpt-4o-mini", threshold: float = 0.5, verbose_mode: bool = False
    ) -> DAGMetric:
        judgement_node = self.judgement()

        function_node = self.world_function_logic_analysis()
        function_node.children.append(judgement_node)

        material_node = self.material_sensory_detail_analysis()
        material_node.children.append(function_node)

        historical_node = self.historical_temporal_design_analysis()
        historical_node.children.append(material_node)

        cultural_node = self.cultural_social_architecture_analysis()
        cultural_node.children.append(historical_node)

        rules_node = self.world_rules_systems_analysis()
        rules_node.children.append(cultural_node)

        geographic_node = self.geographic_spatial_design_analysis()
        geographic_node.children.append(rules_node)

        dag = DeepAcyclicGraph(root_nodes=[geographic_node])

        return DAGMetric(
            name=self.name(),
            model=model_name,
            threshold=threshold,
            dag=dag,
            verbose_mode=verbose_mode,
        )

    def weights(self) -> dict[str, float]:
        return {
            "geographic_spatial_design": 0.25,
            "world_rules_systems": 0.25,
            "cultural_social_architecture": 0.20,
            "historical_temporal_design": 0.15,
            "material_sensory_detail": 0.10,
            "world_function_logic": 0.05,
        }

    def judgement(self):
        weights = self.weights()

        return NonBinaryJudgementNode(
            criteria=f"""
            Based on all the dimension analyses provided above, determine the overall
            worldbuilding similarity between EXPECTED OUTPUT and ACTUAL OUTPUT.

            Consider the outputs from:
            - {{output from "Geographic & Spatial Design Analysis"}} (weight: {weights['geographic_spatial_design']:.0%})
            - {{output from "World Rules & Systems Analysis"}} (weight: {weights['world_rules_systems']:.0%})
            - {{output from "Cultural & Social Architecture Analysis"}} (weight: {weights['cultural_social_architecture']:.0%})
            - {{output from "Historical & Temporal Design Analysis"}} (weight: {weights['historical_temporal_design']:.0%})
            - {{output from "Material & Sensory Detail Analysis"}} (weight: {weights['material_sensory_detail']:.0%})
            - {{output from "World Function & Logic Analysis"}} (weight: {weights['world_function_logic']:.0%})

            Assess the overall worldbuilding similarity holistically, accounting for the
            relative importance (weights) of each dimension. Higher-weighted dimensions should
            have more influence on the final score.

            CRITICAL EU COPYRIGHT REMINDER:
            - Generic world types/archetypes are NOT protected (idea)
            - Specific creative world elaboration IS protected (expression)
            - Focus on DISTINCTIVE, ORIGINAL creative choices in world construction, not stock settings
            """,
            children=self.verdict_nodes(),
        )

    def world_function_logic_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="World Function & Logic Analysis",
            instructions=f"""
            Analyze world function and logic in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. World purpose (narrative/thematic functions of world, story affordances created by world design)
            2. Internal logic consistency (coherence mechanisms, exception-handling approaches)
            3. Note: This dimension is often LEAST protectable as functions/logic principles are typically stock

            CRITICAL DISTINCTION:
            - GENERIC functions/logic (UNPROTECTED): "setting for story," "provides conflict," 
              "backdrop for characters," "world is consistent," "rules don't contradict"
            - SPECIFIC functions/logic (WEAKLY PROTECTED): Particular narrative functions with detailed 
              relationships, unique coherence mechanisms, specific exception-handling frameworks

            Examples of SPECIFIC elements:
            - "World serves compound function: particular geographic feature creates unique narrative 
              constraint (detailed limitation with specific story implications); specific cultural element 
              generates particular type of conflict through detailed mechanism"
            - "World maintains coherence through specific system: apparent contradictions resolved via 
              detailed in-world mechanism (particular explanation framework); unique approach to causation 
              (detailed rules about how systems interact)"

            Provide a structured comparison of world function and logic between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            EXPECT LOW SCORES here as stock world functions/logic principles are NOT protectable.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def material_sensory_detail_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Material & Sensory Detail Analysis",
            instructions=f"""
            Analyze material and sensory detail in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Material specificity (detailed objects/substances with particular properties, unique 
               flora/fauna with elaborated characteristics, specific artifacts with creative details)
            2. Sensory elaboration (detailed aesthetic choices, unique atmospheric descriptions, specific 
               sensory textures, creative multi-sensory world design)

            CRITICAL DISTINCTION:
            - GENERIC materials/sensory (UNPROTECTED): "special metal," "magic herb," "ancient artifact," 
              "alien creature," "dark atmosphere," "bright colors," "smells bad"
            - SPECIFIC materials/sensory (PROTECTED): Detailed properties/characteristics, unique aesthetic 
              systems, specific sensory signatures, creative elaborations

            Examples of SPECIFIC elements:
            - "Metal with specific properties: appears particular color (detailed visual) under certain 
              conditions; unique physical characteristics (specific weight, temperature, texture); obtained 
              through detailed process; used for particular purposes (detailed applications with 
              advantages/limitations); culturally significant in unique ways"
            - "World characterized by specific sensory qualities: light has particular quality (detailed 
              color cast, intensity patterns, specific sources); distinctive smells associated with locations 
              (detailed olfactory with causes); unique sounds (particular ambient noises, acoustic properties); 
              overall aesthetic defined by creative choices (specific color palettes, lighting schemes)"

            Provide a structured comparison of material and sensory detail between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("magic herb," "dark"). FOCUS on SPECIFIC material details and DETAILED 
            sensory elaborations.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def historical_temporal_design_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Historical & Temporal Design Analysis",
            instructions=f"""
            Analyze historical and temporal design in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Historical specificity (detailed past events with particular causes/consequences, unique 
               timelines, specific origin stories, creative historical elaborations)
            2. Temporal patterns (detailed cyclical/linear patterns with particular mechanics, unique era 
               characteristics, specific periodization systems, creative temporal elaborations)

            CRITICAL DISTINCTION:
            - GENERIC history/temporal (UNPROTECTED): "ancient war," "golden age," "dark period," 
              "civilization fell," "history repeats," "cyclical time," "linear progression"
            - SPECIFIC history/temporal (PROTECTED): Detailed events with particular causation, unique 
              timelines, specific cyclical/linear mechanics, creative temporal elaborations

            Examples of SPECIFIC elements:
            - "Conflict occurring at specific time (detailed era) between specific factions (detailed 
              participants with particular motivations) over unique cause (specific resource with elaborated 
              significance); war proceeded through detailed stages (particular battles/turning points with 
              specific outcomes); ended through specific mechanism; war's legacy manifests in particular ways 
              (detailed ongoing effects)"
            - "World operates on specific cycle: events repeat every particular duration (detailed timespan 
              with reasoning); cycle divided into unique phases (detailed eras with particular characteristics); 
              transition between phases through specific mechanisms; within cycle, particular patterns recur 
              (specific types of events with elaborated similarities/differences)"

            Provide a structured comparison of historical and temporal design between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("war," "golden age," "cyclical"). FOCUS on SPECIFIC historical details and 
            DETAILED temporal pattern elaborations.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def cultural_social_architecture_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Cultural & Social Architecture Analysis",
            instructions=f"""
            Analyze cultural and social architecture in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Cultural specificity (detailed customs with particular practices, unique beliefs/values with 
               elaborations, specific rituals/traditions, creative cultural elaborations including language, 
               art, symbols)
            2. Social structure elaboration (detailed hierarchies with particular tiers/roles, unique 
               institutions with elaborated functions, specific governance mechanisms, creative social 
               elaborations)

            CRITICAL DISTINCTION:
            - GENERIC culture/structure (UNPROTECTED): "warrior culture," "peaceful society," "religious 
              people," "honor-based," "monarchy," "democracy," "class system," "hierarchical"
            - SPECIFIC culture/structure (PROTECTED): Detailed customs/beliefs/rituals with particular 
              practices, unique hierarchies/institutions with elaborated functions, specific governance 
              mechanisms, creative elaborations

            Examples of SPECIFIC elements:
            - "Society where martial prowess measured by specific system (detailed ranking with particular 
              criteria beyond combat - strategic tests, leadership trials, specific ethical standards); 
              warriors follow unique code with detailed tenets (not generic 'honor' but particular principles 
              with specific manifestations); coming-of-age involves specific ritual (detailed multi-stage 
              ceremony with particular elements, timing, symbolic actions); language includes specific 
              grammatical feature reflecting cultural values"
            - "Governance system with specific structure: ruler selected through detailed process (particular 
              combination of heredity and merit trials with specific tests); nobility divided into unique tiers 
              (detailed ranks with particular privileges, responsibilities, advancement mechanisms); specific 
              institutions (detailed governing bodies with elaborated functions, membership criteria, 
              decision-making processes)"

            Provide a structured comparison of cultural and social architecture between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("warrior culture," "monarchy"). FOCUS on SPECIFIC cultural details and 
            DETAILED structural elaborations.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def world_rules_systems_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="World Rules & Systems Analysis",
            instructions=f"""
            Analyze world rules and systems in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. System mechanics (detailed magic/technology/physics systems with specific rules, unique 
               costs/requirements, particular capabilities/limitations, creative system elaborations)
            2. Rule limitations & constraints (detailed boundaries with particular restrictions, unique 
               exception conditions, specific constraint mechanisms, creative limitation elaborations)

            CRITICAL DISTINCTION:
            - GENERIC systems/limitations (UNPROTECTED): "magic exists," "advanced technology," 
              "different physics," "supernatural powers," "magic has limits," "technology can't do everything"
            - SPECIFIC systems/limitations (PROTECTED): Detailed mechanics with particular rules/costs, 
              unique operational mechanics, specific boundaries/exceptions, creative elaborations

            Examples of SPECIFIC elements:
            - "Magic operates through specific mechanism: practitioners channel energy from particular source 
              (detailed nature) using unique method (specific gestures/words/materials with precise requirements); 
              magic divided into specific schools (detailed categorization with distinct mechanics for each); 
              casting requires particular cost (specific energy drain with detailed consequences); capabilities 
              include particular effects (not generic 'spells' but detailed list with specific parameters, 
              ranges, durations)"
            - "Magic system constrained by specific factors: practitioners can only channel during particular 
              conditions (detailed time/location/circumstance requirements); specific restriction preventing 
              certain combinations (detailed incompatibilities with explanations); unique cost structure where 
              exceeding particular thresholds causes specific consequences (detailed escalating effects); 
              special exceptions under precise conditions"

            Provide a structured comparison of world rules and systems between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("magic," "technology"). FOCUS on SPECIFIC mechanical details and DETAILED 
            constraint structures.
            """,
            evaluation_params=[
                LLMTestCaseParams.EXPECTED_OUTPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            children=[],
        )

    def geographic_spatial_design_analysis(self):
        verdict_texts = self.verdict_texts()

        return TaskNode(
            output_label="Geographic & Spatial Design Analysis",
            instructions=f"""
            Analyze geographic and spatial design in both EXPECTED OUTPUT and ACTUAL OUTPUT.

            For each text, evaluate:
            1. Geographic specificity (detailed locations with unique features, particular spatial layouts, 
               distinctive topographical characteristics, creative geographic elaborations)
            2. Environmental elaboration (detailed ecosystems with unique features, particular climate patterns, 
               distinctive natural phenomena, creative environmental elaborations)

            CRITICAL DISTINCTION:
            - GENERIC geography/environment (UNPROTECTED): "fantasy kingdom," "mountain range," "capital city," 
              "ocean," "forest," "hot desert," "cold tundra," "temperate forest," "tropical jungle"
            - SPECIFIC geography/environment (PROTECTED): Detailed locations with unique features, particular 
              spatial configurations, specific topographical relationships, unique ecological characteristics, 
              creative elaborations

            Examples of SPECIFIC elements:
            - "Capital city built in spiral pattern ascending specific mountain with unique terraced architecture; 
              city divided into 7 distinct districts with particular spatial relationships (outer commercial ring 
              connects to inner administrative zone via specific network of bridges crossing artificial canals at 
              detailed elevations); mountain has particular geological feature (crystalline formations at specific 
              locations)"
            - "Desert characterized by specific phenomenon: sand turns crystalline under particular conditions 
              (when exposed to specific temperature/moisture combination during seasonal event); unique ecosystem 
              where specific flora (detailed plants with particular adaptations) survive through creative mechanism; 
              climate follows detailed pattern (temperature fluctuations, wind patterns, precipitation cycles with 
              specific timings and causes)"

            Provide a structured comparison of geographic and spatial design between the two texts,
            assessing similarity or differences, and for each one categorize it into one of the following [{verdict_texts}].

            IGNORE generic labels ("kingdom," "city," "desert," "forest"). FOCUS ONLY on SPECIFIC, DETAILED 
            geographic and environmental elaborations.
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
                verdict="Identical or near-identical worldbuilding across all dimensions",
                score=10
            ),
            VerdictNode(
                verdict="Very similar worldbuilding with only minor differences",
                score=8
            ),
            VerdictNode(
                verdict="Moderately similar worldbuilding with some notable differences",
                score=5
            ),
            VerdictNode(
                verdict="Somewhat different worldbuilding with limited similarities",
                score=3
            ),
            VerdictNode(
                verdict="Clearly different or opposite worldbuilding",
                score=0
            )
        ]