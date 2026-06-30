# PSALM v2 Improvements Design Spec

**Date**: 2026-06-30  
**Author**: Noah Scharrenberg  
**Project**: psalm-eu v2  
**Scope**: Argumentation round structure, dimension architecture, deliberation flow, per-dimension verdicts, rubric scoring

---

## 1. Overview

This spec covers seven interrelated improvements observed through experimentation:

1. Symmetric argumentation rounds (both sides argue and counter)
2. Sub-dimension-keyed prompting to prevent lawyer silence on generic elements
3. Vote-first deliberation flow
4. Structured `Dimension` objects with sub-dimensions and importance weights
5. Per-dimension verdicts with configurable pipeline strategies
6. `SCENES_A_FAIRE` as an optional built-in dimension
7. Rubric-supplemented juror scoring

---

## 2. Dimension Architecture

### 2.1 New module: `psalm/dimensions/`

```
psalm/dimensions/
├── __init__.py          # re-exports Dimension, SubDimension, Importance + all built-ins
├── base.py              # Dimension, SubDimension, Importance, SimilarityScore
├── character.py         # CHARACTER constant
├── plot.py              # PLOT constant
├── world_building.py    # WORLD_BUILDING constant
└── scenes_a_faire.py    # SCENES_A_FAIRE constant (opt-in)
```

### 2.2 Models (`psalm/dimensions/base.py`)

```python
class Importance(str, Enum):
    LOW      = "low"       # multiplier: 0.5
    MEDIUM   = "medium"    # multiplier: 1.0  (default)
    HIGH     = "high"      # multiplier: 1.5
    CRITICAL = "critical"  # multiplier: 2.0

_IMPORTANCE_MULTIPLIERS: dict[Importance, float] = {
    Importance.LOW:      0.5,
    Importance.MEDIUM:   1.0,
    Importance.HIGH:     1.5,
    Importance.CRITICAL: 2.0,
}

class SimilarityScore(str, Enum):
    NONE     = "none"      # 0 — no meaningful similarity
    GENERIC  = "generic"   # 1 — generic / unprotectable only (scenes à faire)
    POSSIBLE = "possible"  # 2 — expression-level similarity, independent creation plausible
    CLEAR    = "clear"     # 3 — clear expression-level similarity, defense could not rebut

_SCORE_VALUES: dict[SimilarityScore, int] = {
    SimilarityScore.NONE:     0,
    SimilarityScore.GENERIC:  1,
    SimilarityScore.POSSIBLE: 2,
    SimilarityScore.CLEAR:    3,
}

class SubDimension(BaseModel):
    name: str
    description: str
    importance: Importance = Importance.MEDIUM

class Dimension(BaseModel):
    name: str
    description: str
    sub_dimensions: list[SubDimension]
    importance: Importance = Importance.MEDIUM
```

### 2.3 Built-in constants

#### `character.py`

```python
CHARACTER = Dimension(
    name="character",
    description="How characters are developed and expressed.",
    importance=Importance.HIGH,
    sub_dimensions=[
        SubDimension(name="Identity & Properties",      description="Unique traits and characteristics.",            importance=Importance.HIGH),
        SubDimension(name="Character Development",      description="Growth and change over the narrative.",         importance=Importance.HIGH),
        SubDimension(name="Relationships & Dynamics",   description="Interactions with other characters.",           importance=Importance.MEDIUM),
        SubDimension(name="Background & Motivation",    description="Backstory and driving forces.",                 importance=Importance.MEDIUM),
        SubDimension(name="Expression & Behaviour",     description="Manner of acting and speaking.",                importance=Importance.LOW),
        SubDimension(name="Function & Role",            description="Narrative role (e.g. hero, antagonist).",       importance=Importance.LOW),
    ],
)
```

#### `plot.py`

```python
PLOT = Dimension(
    name="plot",
    description="The construction and progression of the story.",
    importance=Importance.HIGH,
    sub_dimensions=[
        SubDimension(name="Event Sequence & Causality", description="Order and causal links between events.",        importance=Importance.CRITICAL),
        SubDimension(name="Story Architecture",         description="Acts, subplots, and structural organisation.",  importance=Importance.HIGH),
        SubDimension(name="Conflict Structure",         description="Tension build-up and obstacles.",               importance=Importance.HIGH),
        SubDimension(name="Turning Points & Reversals", description="Plot twists and reversals.",                    importance=Importance.MEDIUM),
        SubDimension(name="Temporal Structure",         description="Flashbacks, pacing, and time handling.",        importance=Importance.MEDIUM),
        SubDimension(name="Plot Functions & Convergence", description="How plot lines meet and resolve.",            importance=Importance.LOW),
    ],
)
```

#### `world_building.py`

```python
WORLD_BUILDING = Dimension(
    name="world-building",
    description="The fictional world in which the story takes place.",
    importance=Importance.MEDIUM,
    sub_dimensions=[
        SubDimension(name="World Rules & Systems",          description="Magic, technology, and governing laws.",        importance=Importance.HIGH),
        SubDimension(name="World Function & Logic",         description="Internal consistency of the world.",            importance=Importance.HIGH),
        SubDimension(name="Geographic & Spatial Design",    description="Locations, maps, and layouts.",                 importance=Importance.MEDIUM),
        SubDimension(name="Cultural & Social Architecture", description="Norms, hierarchies, and social structures.",    importance=Importance.MEDIUM),
        SubDimension(name="Historical & Temporal Design",   description="Timelines, eras, and historical context.",      importance=Importance.LOW),
        SubDimension(name="Material & Sensory Details",     description="Objects, atmosphere, and sensory texture.",     importance=Importance.LOW),
    ],
)
```

#### `scenes_a_faire.py`

```python
SCENES_A_FAIRE = Dimension(
    name="scenes-a-faire",
    description="Stock elements that are not copyright-protected.",
    importance=Importance.MEDIUM,
    sub_dimensions=[
        SubDimension(name="Genre Conventions & Setting",       description="Standard genre elements used.",                importance=Importance.CRITICAL),
        SubDimension(name="Standard Characters & Archetypes",  description="Whether characters are clichéd archetypes.",   importance=Importance.HIGH),
        SubDimension(name="Standard Plot Devices & Tropes",    description="Use of clichéd storylines.",                   importance=Importance.HIGH),
        SubDimension(name="Thematic Commonplaces",             description="Whether themes are generic.",                  importance=Importance.MEDIUM),
        SubDimension(name="Necessary Technical Elements",      description="Functionally necessary elements.",              importance=Importance.MEDIUM),
        SubDimension(name="Creative Elaboration",              description="How much original elaboration exists.",         importance=Importance.LOW),
    ],
)
```

`SCENES_A_FAIRE` is opt-in — not included in the default `DebateConfig.dimensions`.

### 2.4 Config changes

`DebateConfig.dimensions` changes from `list[str]` to `list[Dimension]`. The `_VALID_DIMENSIONS` hardcoded string validator is removed. Any `Dimension` instance is valid. Default: `[CHARACTER, PLOT, WORLD_BUILDING]`.

`CaseInput.dimensions` changes from `list[str]` to `list[Dimension]` accordingly.

---

## 3. Argumentation Phase Redesign

### 3.1 Symmetric round structure

One round consists of four sequential sub-steps, each followed by judge validation:

| Step | Node | Description |
|---|---|---|
| 1 | `prosecution_argue` | Prosecution makes affirmative arguments across sub-dimensions |
| 2 | `defense_counter` | Defense counters prosecution arguments |
| 3 | `defense_argue` | Defense makes independent affirmative arguments |
| 4 | `prosecution_counter` | Prosecution counters defense affirmative arguments |

Each step passes through a dedicated judge validation node before the next step begins.

### 3.2 Graph topology

```
prosecution_argue
  → judge_validate_prosecution
  → defense_counter
  → judge_validate_defense_counter
  → defense_argue
  → judge_validate_defense
  → prosecution_counter
  → judge_validate_prosecution_counter
  → check_next_round
  → [continue → prosecution_argue | done → finalize_arguments]
```

### 3.3 Stop conditions

The round ends (routing to `finalize_arguments`) when **any** of the following:

- Both `prosecution_argue` AND `defense_argue` return empty in the same round
- `current_round >= max_rounds`
- Stability detected (same claims repeated from prior round)

If only one side is empty, the round still proceeds — the other side continues to argue and counter.

### 3.4 Updated `RoundArguments` model

```python
class RoundArguments(BaseModel):
    round: int
    prosecution_arguments: list[Argument]    # step 1
    defense_counters: list[Argument]         # step 2 — defense responding to prosecution
    defense_arguments: list[Argument]        # step 3
    prosecution_counters: list[Argument]     # step 4 — prosecution responding to defense
```

### 3.5 `ArgumentationState` additions

```python
pending_defense_counters: list[dict[str, Any]] = Field(default_factory=list)
validated_defense_counters: list[dict[str, Any]] = Field(default_factory=list)
pending_prosecution_counters: list[dict[str, Any]] = Field(default_factory=list)
validated_prosecution_counters: list[dict[str, Any]] = Field(default_factory=list)
```

### 3.6 Prompt changes (Issue 2 fix)

**Prosecution prompt** removes all "be aware the defense will challenge X" self-censorship language. The prompt receives the active `Dimension` with its sub-dimensions and importance levels. It is required to produce at least one argument per `HIGH` and `CRITICAL` sub-dimension where any similarity exists — including generic or weak ones. Framing shifts to: "Surface all similarities. The court filters; you argue."

**Defense prompt** similarly receives sub-dimensions and must address each sub-dimension the prosecution argued, plus produce at least one affirmative argument per `HIGH`/`CRITICAL` sub-dimension.

Both prompts receive a formatted sub-dimension context block:

```
Dimension: character — How characters are developed and expressed.
Sub-dimensions (argue ALL marked HIGH or CRITICAL):
  [CRITICAL] Event Sequence & Causality: Order and causal links between events.
  [HIGH]     Story Architecture: Acts, subplots, and structural organisation.
  [MEDIUM]   Conflict Structure: Tension build-up and obstacles.
  ...
```

---

## 4. Deliberation Phase Redesign

### 4.1 Vote-first graph topology

```
distribute_context
  → jury_vote              ← round 1: no prior discussion
  → aggregate_votes
  → check_consensus
  → [consensus   → finalize_verdict
   | exhausted   → apply_voting_strategy → finalize_verdict
   | continue    → jury_discussion → jury_vote → aggregate_votes → check_consensus → ...]
```

`jury_discussion` only appears from round 2 onward. Before discussing, jurors receive all prior votes and rationales, giving them concrete positions to engage with.

### 4.2 Rubric-supplemented `JurorVote`

```python
class DimensionScore(BaseModel):
    sub_dimension: str
    score: SimilarityScore
    reasoning: str

class JurorVote(BaseModel):
    juror_id: str
    vote: Literal["Guilty", "Not Guilty", "Undecided"]
    rationale: str
    dimension_scores: list[DimensionScore]   # one per sub-dimension argued
```

The rubric is embedded in the juror system prompt:

| Score | Label | Meaning |
|---|---|---|
| 0 | `none` | No meaningful similarity |
| 1 | `generic` | Similarity exists but is generic / unprotectable |
| 2 | `possible` | Expression-level similarity, independent creation plausible |
| 3 | `clear` | Clear expression-level similarity, defense could not credibly rebut |

### 4.3 Weighted score aggregation

For each sub-dimension, juror scores are averaged and multiplied by the sub-dimension's importance multiplier. The weighted values sum and normalise into a per-dimension `weighted_score`. This score:

- Supplements the binary majority vote
- Serves as the primary tiebreaker input before escalating to `JudgeTiebreakerVoting`
- Feeds the final verdict aggregation (Section 5.3)

### 4.4 `DeliberationState` addition

```python
current_dimension: Dimension   # active dimension for this deliberation phase
```

Under `FULLY_SEPARATE`, each `DeliberationPhase` instance is scoped to one dimension. Juror prompts receive sub-dimension context so discussion and scoring stay focused.

---

## 5. Per-Dimension Pipeline Strategy

### 5.1 `EvaluationStrategy` enum

```python
class EvaluationStrategy(str, Enum):
    SHARED_ARG_PER_DIM_DELIBERATION = "shared_arg_per_dim_deliberation"
    FULLY_SEPARATE                  = "fully_separate"           # default
    SHARED_ALL                      = "shared_all"
```

Added to `DebateConfig`:

```python
evaluation_strategy: EvaluationStrategy = EvaluationStrategy.FULLY_SEPARATE
guilty_threshold: float = 0.5   # normalised weighted score threshold for overall Guilty
```

### 5.2 Strategy behaviour

**`FULLY_SEPARATE` (default)**  
N independent `ArgumentationPhase + DeliberationPhase` pairs run in parallel — one per dimension. Each pipeline is scoped to a single `Dimension`. Most focused; N× LLM calls.

**`SHARED_ARG_PER_DIM_DELIBERATION`**  
One shared `ArgumentationPhase` runs across all dimensions (arguments already carry a `dimension` field). Then N `DeliberationPhase` instances run in parallel, each receiving only that dimension's arguments. Moderate cost; argumentation can cross-reference dimensions.

**`SHARED_ALL`**  
One `ArgumentationPhase` and one `DeliberationPhase` across all dimensions. Jurors return one `JurorVote` per dimension within a single deliberation pass — `JurorVote` gains an optional `dimension: str | None = None` field (populated only under `SHARED_ALL`). The juror's `vote()` method returns `list[JurorVote]` in this mode. Least expensive; least focused.

### 5.3 Updated result models

```python
class DimensionVerdict(BaseModel):
    dimension: str
    importance: Importance
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]
    weighted_score: float
    argumentation_log: ArgumentationLog
    debate_log: DebateLog

class PSALMResult(BaseModel):
    verdict: Literal["Guilty", "Not Guilty", "Undecided"]   # overall
    rationale: str    # summary of which dimensions drove the verdict and their weighted scores
    dimension_verdicts: list[DimensionVerdict]
    metadata: ResultMetadata
```

`argumentation_log` and `debate_log` move into `DimensionVerdict`. Under `SHARED_ALL`, both reference the single shared log.

### 5.4 Final verdict aggregation

1. For each dimension: `weighted_contribution = dimension.weighted_score × importance_multiplier`
2. Normalise across all dimensions
3. If normalised score ≥ `guilty_threshold` (default `0.5`): overall `Guilty`
4. Hard override: if any `CRITICAL` dimension verdict is `Guilty`, overall verdict is `Guilty` regardless of score

---

## 6. Builder API Changes

### 6.1 New and updated methods

```python
.with_dimensions(dimensions: list[Dimension]) -> PSALM
.with_evaluation_strategy(strategy: EvaluationStrategy) -> PSALM
```

`with_dimensions()` now accepts `list[Dimension]`. Defaults to `[CHARACTER, PLOT, WORLD_BUILDING]`.

### 6.2 Example

```python
from psalm import PSALM, EvaluationStrategy
from psalm.dimensions import CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE

result = await (
    PSALM()
    .with_prosecutor(base_url=..., api_key=..., model=...)
    .with_defense(base_url=..., api_key=..., model=...)
    .with_judge(base_url=..., api_key=..., model=...)
    .with_jury([...])
    .with_dimensions([CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE])
    .with_evaluation_strategy(EvaluationStrategy.FULLY_SEPARATE)
    .with_debate(argumentation_rounds=3, deliberation_rounds=4)
    .build()
).aevaluate(source_text, target_text)
```

### 6.3 Breaking changes summary

| What | Old | New |
|---|---|---|
| `DebateConfig.dimensions` | `list[str]` | `list[Dimension]` |
| `CaseInput.dimensions` | `list[str]` | `list[Dimension]` |
| `PSALMResult` top-level logs | `argumentation_log`, `debate_log` | removed — now inside `dimension_verdicts` |
| `JurorVote` | `vote + rationale` | adds `dimension_scores: list[DimensionScore]` |
| `RoundArguments` | `arguments + counter_arguments` | 4-field symmetric structure |
| `_VALID_DIMENSIONS` string validator | hardcoded set | removed |

### 6.4 Unchanged

`AgentConfig`, `VotingStrategy` interface, `BaseAgent`, `BasePhase`, `CourtroomSetup`, `DebateConfig` base round/time fields, all voting strategy implementations.

---

## 7. Files Added / Modified

### New files

| File | Purpose |
|---|---|
| `psalm/dimensions/__init__.py` | Re-exports |
| `psalm/dimensions/base.py` | `Dimension`, `SubDimension`, `Importance`, `SimilarityScore` |
| `psalm/dimensions/character.py` | `CHARACTER` constant |
| `psalm/dimensions/plot.py` | `PLOT` constant |
| `psalm/dimensions/world_building.py` | `WORLD_BUILDING` constant |
| `psalm/dimensions/scenes_a_faire.py` | `SCENES_A_FAIRE` constant |

### Modified files

| File | Change |
|---|---|
| `psalm/models/config.py` | `EvaluationStrategy` enum, `list[str]` → `list[Dimension]`, `guilty_threshold` |
| `psalm/models/evidence.py` | No change |
| `psalm/models/result.py` | `DimensionScore`, `DimensionVerdict`, updated `JurorVote`, updated `PSALMResult` |
| `psalm/models/state.py` | 4 new pending/validated lists, `current_dimension` in `DeliberationState` |
| `psalm/agents/prosecutor.py` | Sub-dimension-keyed prompt, removes self-censorship language |
| `psalm/agents/defense.py` | Sub-dimension-keyed prompt |
| `psalm/agents/juror.py` | Rubric in system prompt, `DimensionScore` output, vote-first awareness |
| `psalm/phases/argumentation.py` | 4-node symmetric round graph |
| `psalm/phases/deliberation.py` | Vote-first graph, weighted score aggregation |
| `psalm/builder.py` | `with_dimensions(list[Dimension])`, `with_evaluation_strategy()`, pipeline orchestration |
| `psalm/courtroom/default.py` | Parallel dimension pipeline execution |
