import asyncio
import os
import sys

from psalm import PSALM, PSALMResult

COPYRIGHT_TEXT = """
### Chapter: The Crescent Moon Scar\n\nLiora Veyne's left eyebrow always twitched when she lied, a habit she had spent years trying to suppress. It was a tell, a crack in the facade she had so carefully constructed. The crescent-moon scar on her right temple—gifted to her at seven by a rusted factory gear—pulled taut whenever she frowned, which was often. She spoke in a rhythmic cadence, pausing before every third word, as if the silence itself was a punctuation mark only she could hear.\n\nThe workshop smelled of oil and old wood, the air thick with the ticking of a hundred unfinished clocks. Elias, her mentor, hunched over a workbench, his gnarled fingers coaxing life into a pocket watch that had stopped mid-chime. He never spoke of the night her father died in the factory, the night he had been the foreman on duty. Guilt had a way of manifesting in silence, and Elias's was a library of unspoken words.\n\nLiora's hands moved with precision, winding gears and polishing brass, but her mind was elsewhere. The ritual always began the same: three checks of the workshop's lock, then the kettle. Boil the water first. Warm the cup. Steep the tea for exactly two minutes—no more, no less. It was the only thing that kept the memories at bay, the ones that slithered in when she wasn't looking: the scream of the machinery, the way her father's apron had billowed as he fell.\n\nShe had learned to cope through isolation, a skill honed after her best friend, Mara, sold her secrets to the city's overseers at sixteen. Betrayal, she decided, was just another kind of gear—one that stripped you down to nothing. But then there was the stranger from the market, the one who had handed her a single silver coin and said, *'You look like you could use this more than I could.'* It was the first act of kindness she had accepted in years, and it had unraveled her.\n\nNow, she stood at the edge of the city's great clock tower, the one Elias had forbidden her to touch. The tower's mechanism was broken, its chimes silent for a decade. The city, she realized, had its own rhythm—one of whispers and hidden currents. And for the first time, she wanted to listen.
"""

INFRINGING_TEXT = """
### Chapter: The Crescent Scar

Lyra Vane's left brow twitched whenever she was being dishonest — a reflex she had never managed to train away. The curved scar at her right temple, the keepsake of a childhood encounter with a factory machine, pulled tight each time her expression darkened. Her speech had a strange cadence: a deliberate pause before each third word, as though silence were punctuation only she could read.

The repair shop carried the scent of lubricant and seasoned timber, its air filled with the rhythmic ticking of unfinished timepieces. Her teacher Elias bent low over a pocket watch on the bench, his old fingers teasing the mechanism back to life. He never mentioned the night Lyra's father had died at the factory, the night he had stood as foreman. Guilt, she had learned, lives most comfortably in silence.

She worked with calm precision — adjusting springs, polishing brass faces — while her mind drifted. The same routine every evening: three checks of the door bolt, then the kettle. Boil first. Heat the cup. Steep the tea for two minutes exactly. It was the only ritual that kept the old memories at bay, the ones that slipped in unguarded: the shriek of the machinery, the way her father's apron had billowed as he fell.

She had grown comfortable with solitude after her closest friend Mara had betrayed her secrets to the city authorities at sixteen. Betrayal, she concluded, was merely another mechanism — one that stripped a person bare. But then the stranger at the market had pressed a silver coin into her hand: "You look like you need this more than I do." It was the first kindness she had let in for years, and it had cracked something open.

Now she stood before the great city clock tower, the one Elias had always forbidden her to touch. Its bells had been silent for a decade. The city, she realised, had a rhythm of its own — made of whispers and undertows. And for the first time, she wanted to be part of it.
"""


_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_TEMPERATURE = "0.7"


def _resolve(key: str, *fallbacks: str, required: bool = False) -> str:
    """Return the first non-empty env var from key then fallbacks.

    If required and none found, print an error and exit.
    """
    for name in (key, *fallbacks):
        value = os.getenv(name, "")
        if value:
            return value
    if required:
        tried = ", ".join((key, *fallbacks))
        print(f"Error: required env var not set. Tried: {tried}", file=sys.stderr)
        sys.exit(1)
    return ""


def _agent_config(role_prefix: str) -> dict:
    """Resolve config for a named role (PROSECUTOR / DEFENSE / JUDGE).

    Fallback chain: PSALM_{ROLE}_* → PSALM_*
    """
    api_key = _resolve(
        f"PSALM_{role_prefix}_API_KEY",
        "PSALM_API_KEY",
        required=True,
    )
    return {
        "api_key": api_key,
        "base_url": (
            _resolve(f"PSALM_{role_prefix}_BASE_URL", "PSALM_BASE_URL") or _DEFAULT_BASE_URL
        ),
        "model": _resolve(f"PSALM_{role_prefix}_MODEL", "PSALM_MODEL") or _DEFAULT_MODEL,
        "temperature": float(
            _resolve(f"PSALM_{role_prefix}_TEMPERATURE", "PSALM_TEMPERATURE")
            or _DEFAULT_TEMPERATURE
        ),
    }


def _juror_config(index: int) -> dict:
    """Resolve config for juror at zero-based index.

    Fallback chain: PSALM_JUROR_{i}_* → PSALM_JURY_* → PSALM_*
    """
    juror_prefix = f"PSALM_JUROR_{index}"
    api_key = _resolve(
        f"{juror_prefix}_API_KEY",
        "PSALM_JURY_API_KEY",
        "PSALM_API_KEY",
        required=True,
    )
    seed = int(_resolve(f"{juror_prefix}_SEED") or str(index))
    return {
        "api_key": api_key,
        "base_url": (
            _resolve(f"{juror_prefix}_BASE_URL", "PSALM_JURY_BASE_URL", "PSALM_BASE_URL")
            or _DEFAULT_BASE_URL
        ),
        "model": (
            _resolve(f"{juror_prefix}_MODEL", "PSALM_JURY_MODEL", "PSALM_MODEL")
            or _DEFAULT_MODEL
        ),
        "temperature": float(
            _resolve(f"{juror_prefix}_TEMPERATURE", "PSALM_JURY_TEMPERATURE", "PSALM_TEMPERATURE")
            or _DEFAULT_TEMPERATURE
        ),
        "seed": seed,
    }


def _load_config() -> dict:
    jury_size = int(os.getenv("PSALM_JURY_SIZE", "3"))
    return {
        "prosecutor": _agent_config("PROSECUTOR"),
        "defense": _agent_config("DEFENSE"),
        "judge": _agent_config("JUDGE"),
        "jury": [_juror_config(i) for i in range(jury_size)],
        "argumentation_rounds": int(os.getenv("PSALM_ARGUMENTATION_ROUNDS", "3")),
        "deliberation_rounds": int(os.getenv("PSALM_DELIBERATION_ROUNDS", "2")),
        "time_limit_seconds": int(os.getenv("PSALM_TIME_LIMIT_SECONDS", "120")),
    }


def _print_config_summary(cfg: dict) -> None:
    def fmt(agent: dict) -> str:
        return f"{agent['model']} @ {agent['base_url']}"

    print(f"  Prosecutor : {fmt(cfg['prosecutor'])}")
    print(f"  Defense    : {fmt(cfg['defense'])}")
    print(f"  Judge      : {fmt(cfg['judge'])}")
    for i, juror in enumerate(cfg["jury"]):
        print(f"  Juror {i}     : {fmt(juror)}  (seed={juror['seed']})")
    print(f"  Argumentation rounds : {cfg['argumentation_rounds']}")
    print(f"  Deliberation rounds  : {cfg['deliberation_rounds']}")
    print(f"  Time limit           : {cfg['time_limit_seconds']}s")


def _print_result(result: PSALMResult) -> None:
    print("\n" + "=" * 60)
    print(f"  VERDICT: {result.verdict}")
    print("=" * 60)
    print(f"\nRationale:\n  {result.rationale}")
    print("\nMetadata:")
    print(f"  Duration:              {result.metadata.duration_seconds:.1f}s")
    print(f"  Argumentation rounds:  {result.metadata.argumentation_rounds_used}")
    print(f"  Deliberation rounds:   {result.metadata.deliberation_rounds_used}")
    print(f"  Voting strategy:       {result.metadata.voting_strategy_applied}")
    print("\nFull result (JSON):")
    print(result.to_json())


async def main() -> None:
    cfg = _load_config()

    print("=== PSALM EU Copyright Evaluation Demo ===\n")
    _print_config_summary(cfg)
    print("\nBuilding courtroom (pinging LLMs)...")

    psalm = await (
        PSALM()
        .with_prosecutor(**cfg["prosecutor"])
        .with_defense(**cfg["defense"])
        .with_judge(**cfg["judge"])
        .with_jury(cfg["jury"])
        .with_dimensions(["character", "world-building", "plot"])
        .with_debate(
            argumentation_rounds=cfg["argumentation_rounds"],
            deliberation_rounds=cfg["deliberation_rounds"],
            time_limit_seconds=cfg["time_limit_seconds"],
        )
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .build()
    )

    print("Evaluating texts...\n")
    result = await psalm.aevaluate(
        source_text=COPYRIGHT_TEXT,
        target_text=INFRINGING_TEXT,
    )

    _print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
