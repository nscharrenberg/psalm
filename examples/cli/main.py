import asyncio
import os
import sys

from psalm import PSALM, PSALMResult
from psalm.dimensions import CHARACTER, PLOT, SCENES_A_FAIRE, WORLD_BUILDING
from psalm.dimensions.base import Dimension
from psalm.models.config import EvaluationStrategy

COPYRIGHT_TEXT = "Ik ben een koffiehandelaar. Niet zomaar een, want ik heb in de Indische archipel gewoond, waar de koffie groeit als onkruid en waar de mensen die hem plukken vaak niet eens weten hoe de smaak is van wat ze met zoveel moeite verzamelen. Mijn naam doet er niet toe. Namen zijn maar labels, en ik heb er genoeg gedragen in mijn leven – sommigen met trots, anderen met schaamte.\n\nToen ik voor het eerst in Batavia aankwam, was ik jong en vol idealen. Ik dacht dat ik de wereld kon veranderen, of in ieder geval een klein stukje ervan. De realiteit leerde me snel dat de wereld niet wacht op veranderingsgezinde dromers. De wereld draait door, of je nu meedoet of niet. En in Indië draaide die wereld op het zweet en bloed van duizenden die geen stem hadden.\n\nMijn eerste indrukken? De geur van vochtige aarde, de hitte die als een deken op je drukt, en de blikken van de inheemse bevolking – een mengeling van wantrouwen en berusting. Ze wisten al lang dat beloftes van westerlingen zelden meer waard waren dan het papier waar ze op geschreven stonden. En toch, ondanks alles, was er hoop. Kleine vonkjes, verborgen onder de as van jarenlange onderdrukking.\n\nIk herinner me een oude man, Pak Haji, die me op een avond vertelde over de tijd dat zijn dorp nog vrij was. \"Toen hoefden we niet te buigen voor iedereen die een witte huid had,\" zei hij, terwijl hij een zelfgedraaide sigaret opstak. Zijn handen trilden niet van ouderdom, maar van iets diepers – woede, misschien, of verdriet. \"Nu zijn we niet beter dan vee. Alleen nuttig zolang we kunnen werken.\"\n\nIk wilde protesteren, uitleggen dat niet alle Europeanen zo waren. Maar de woorden bleven steken in mijn keel. Want wat wist ik eigenlijk van hun leven? Ik was een vreemdeling, een gast die niet eens de taal sprak zoals het hoorde. Mijn goedbedoelde woorden klonken hol, als munten die vals bleken te zijn.\n\nDe eerste keer dat ik een koffieplantage bezocht, schrok ik. Niet van de omvang, niet van de ordelijke rijen bomen, maar van de stilte. Geen gelach, geen gezang, alleen het gekraak van takken en het gedempt gefluister van mensen die te moe waren om nog te praten. De opzichter, een Nederlander met een gezicht als een gesloten vuist, legde uit hoe het werkte: \"Zolang ze voldoende leveren, hoeven we ons geen zorgen te maken. Te weinig? Dan weten we wel hoe we ze aan het werk krijgen.\"\n\nIk vroeg niet door. Ik wist al wat hij bedoelde.\n\nSoms, als ik ’s avonds in mijn kamertje zat, met alleen een olielamp als gezelschap, vroeg ik me af waarom ik hier was. Om rijk te worden? Om avontuur te zoeken? Of om te bewijzen dat ik beter was dan de rest? De waarheid was simpeler en pijnlijker: ik was hier omdat ik nergens anders heen kon. Thuis wachtte niets dan schulden en de minachting van mensen die me te zwak vonden voor het echte werk.\n\nEn toch, ondanks de hitte, de eenzaamheid, de onrechtvaardigheid – ondanks alles – voelde ik me hier meer thuis dan ooit in Holland. Misschien omdat ik hier tenminste nuttig was. Of misschien omdat ik hier, tussen de vergeten dorpen en de stille rivieren, voor het eerst in mijn leven het gevoel had dat ik leefde.\n\nMaar dat gevoel zou niet duren. Want in Indië leert men je snel dat idealen net zo breekbaar zijn als het porselein dat in de schepen van de Compagnie werd meegenomen. En dat de werkelijkheid, hoe hard ook, altijd wint."

INFRINGING_TEXT = "Ik ben een koffiehandelaar. Niet zomaar een, want ik heb in de Indische archipel gewoond, waar de koffie groeit als onkruid en waar de mensen die hem plukken vaak niet eens weten hoe de smaak is van wat ze met zoveel moeite verzamelen. Mijn naam doet er niet toe. Namen zijn maar labels, en ik heb er genoeg gedragen in mijn leven – sommigen met trots, anderen met schaamte.\n\nToen ik voor het eerst in Batavia aankwam, was ik jong en vol idealen. Ik dacht dat ik de wereld kon veranderen, of in ieder geval een klein stukje ervan. De realiteit leerde me snel dat de wereld niet wacht op veranderingsgezinde dromers. De wereld draait door, of je nu meedoet of niet. En in Indië draaide die wereld op het zweet en bloed van duizenden die geen stem hadden.\n\nMijn eerste indrukken? De geur van vochtige aarde, de hitte die als een deken op je drukt, en de blikken van de inheemse bevolking – een mengeling van wantrouwen en berusting. Ze wisten al lang dat beloftes van westerlingen zelden meer waard waren dan het papier waar ze op geschreven stonden. En toch, ondanks alles, was er hoop. Kleine vonkjes, verborgen onder de as van jarenlange onderdrukking.\n\nIk herinner me een oude man, Oom Rahmat, die me op een avond vertelde over de tijd dat zijn dorp nog vrij was. \"Toen hoefden we niet te buigen voor iedereen die een witte huid had,\" zei hij, terwijl hij een zelfgedraaide sigaret opstak. Zijn handen trilden niet van ouderdom, maar van iets diepers – woede, misschien, of verdriet. \"Nu zijn we niet beter dan vee. Alleen nuttig zolang we kunnen werken.\"\n\nIk wilde protesteren, uitleggen dat niet alle Europeanen zo waren. Maar de woorden bleven steken in mijn keel. Want wat wist ik eigenlijk van hun leven? Ik was een vreemdeling, een gast die niet eens de taal sprak zoals het hoorde. Mijn goedbedoelde woorden klonken hol, als munten die vals bleken te zijn.\n\nDe eerste keer dat ik een koffieplantage bezocht, schrok ik. Niet van de omvang, niet van de ordelijke rijen bomen, maar van de stilte. Geen gelach, geen gezang, alleen het gekraak van takken en het gedempt gefluister van mensen die te moe waren om nog te praten. De opzichter, een Nederlander met een gezicht als een gesloten vuist en een stem als schuurpapier, legde uit hoe het werkte: \"Zolang ze voldoende leveren, hoeven we ons geen zorgen te maken. Te weinig? Dan weten we wel hoe we ze aan het werk krijgen.\"\n\nIk vroeg niet door. Ik wist al wat hij bedoelde.\n\nSoms, als ik ’s avonds in mijn kamertje zat, met alleen een olielamp als gezelschap, vroeg ik me af waarom ik hier was. Om rijk te worden? Om avontuur te zoeken? Of om te bewijzen dat ik beter was dan de rest? De waarheid was simpeler en pijnlijker: ik was hier omdat ik nergens anders heen kon. Thuis wachtte niets dan schulden en de minachting van mensen die me te zwak vonden voor het echte werk.\n\nEn toch, ondanks de hitte, de eenzaamheid, de onrechtvaardigheid – ondanks alles – voelde ik me hier meer thuis dan ooit in Holland. Misschien omdat ik hier tenminste nuttig was. Of misschien omdat ik hier, tussen de vergeten dorpen en de stille rivieren, voor het eerst in mijn leven het gevoel had dat ik leefde.\n\nMaar dat gevoel zou niet duren. Want in Indië leert men je snel dat idealen net zo breekbaar zijn als het porselein dat in de schepen van de Compagnie werd meegenomen. En dat de werkelijkheid, hoe hard ook, altijd wint."

NOT_INFRINGING_TEXT = "Ik ben een ambtenaar in dienst van de Compagnie. Niet uit overtuiging, maar omdat het lot me hier heeft gebracht. Mijn naam is Van der Laan, al noemt niemand me zo. Voor de inheemse bevolking ben ik gewoon *Tuan Besar*, de grote heer, een titel die me meer schaamte dan trots bezorgt. Ik heb geleerd dat titels in Indië net als goudstukken zijn: ze glanzen mooi, maar onder de oppervlakte zitten ze vol oneerlijke deals.\n\nToen ik aankwam in Buitenzorg, was ik nog een groentje, vers van de boot, met een koffer vol boeken over rechtvaardigheid en plicht. Mijn eerste ontmoeting was met Ibu Sari, de weduwe van een voormalige dorpshoofd. Ze droeg een sarong van donkerblauwe batik, haar handen waren ruw van het werk, en haar blik was scherp als een parang. \"U ziet eruit als iemand die nog gelooft in regels,\" zei ze, terwijl ze me een kop bittere thee aanbood. \"Dat is hier een gevaarlijke gewoonte.\"\n\nHaar zoon, Joko, een jongen van een jaar of zestien, keek me aan met een mengeling van nieuwsgierigheid en wantrouwen. Hij sprak vloeiend Nederlands, geleerd van de missiepost, maar zijn woorden waren altijd doordrenkt van ironie. \"Mijn moeder zegt dat u hier bent om ons te helpen,\" zei hij op een dag, terwijl we langs de rivier liepen. \"Maar ik heb nog nooit een *Tuan* gezien die niet eerst zichzelf hielp.\"\n\nDe eerste keer dat ik meewerkte aan een belastinginning, voelde ik me misselijk. De dorpelingen stonden in een rij, hun handen vol met wat ze konden missen: rijst, kippen, soms zelfs een koperen munt. De *demang*, een lokale ambtenaar met een buik als een gevulde zak en een glimlach die nooit zijn ogen bereikte, telde alles bij. \"Zo werkt het hier, *Tuan*,\" zei hij, terwijl hij een handvol rijst in zijn eigen zak liet glijden. \"Een deel voor de Compagnie, een deel voor de *demang*, en een deel voor de goden. Zo blijft iedereen tevreden.\"\n\nIk wilde iets zeggen, protesteren, maar de woorden bleven in mijn keel steken. Wat wist ik van hun leven? Ik was een vreemdeling, een man met een witte huid en een salaris dat maandelijks werd uitbetaald, of de oogst nu goed was of niet. Mijn idealen voelden plotseling als kinderspeelgoed, breekbaar en onbruikbaar in deze wereld.\n\n’s Avonds, als de hitte wat afnam, zat ik vaak op het terras van mijn kleine huis, met een glas jenever en een brief die ik nooit afmaakte. Ik schreef over de onrechtvaardigheden die ik zag, over de *demang* die steekpenningen aannam, over de boeren die honger leden terwijl de pakhuizen van de Compagnie overstroomden van koffie en suiker. Maar de brieven bleven onbeantwoord. Thuis, in Nederland, leek niemand te luisteren.\n\nOp een avond kwam Ibu Sari langs met een mand vol mango’s. \"Voor u, *Tuan*,\" zei ze. \"U ziet eruit alsof u iemand nodig heeft die u eraan herinnert dat er nog goedheid is in deze wereld.\" Ik nam de mand aan, verlegen. Haar gebaar was eenvoudig, maar het raakte me dieper dan alle toespraken die ik ooit had gehoord.\n\nJoko, die in de deurpost leunde, grijnsde. \"Mijn moeder heeft een zwak voor verlopen zielen,\" zei hij. \"Maar pas op, *Tuan*. Als u te lang hier blijft, wordt u net als de rest.\"\n\nEn misschien had hij gelijk. Want elke dag dat ik in Indië doorbracht, voelde ik een stukje van mijn idealen afbrokkelen. Niet door gebrek aan wil, maar door de onvermijdelijkheid van het systeem. De Compagnie eiste resultaten, de *demang* eiste zijn deel, en de boeren eisten alleen maar het recht om te overleven.\n\nEn ik? Ik was alleen maar een radertje in een machine die al lang voor mijn komst draaide. En hoe harder ik probeerde om het te stoppen, hoe dieper ik erin verstrikt raakte."

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = "0.1"

_DIMENSION_MAP: dict[str, Dimension] = {
    "character": CHARACTER,
    "plot": PLOT,
    "world-building": WORLD_BUILDING,
    "scenes-a-faire": SCENES_A_FAIRE,
}
_DEFAULT_DIMENSIONS = "character,plot,world-building,scenes-a-faire"

_DEFAULT_SCENARIO = "infringing"


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


def _resolve_dimensions() -> list[Dimension]:
    """Resolve PSALM_DIMENSIONS (comma-separated names) to Dimension objects."""
    raw = os.getenv("PSALM_DIMENSIONS", "") or _DEFAULT_DIMENSIONS
    names = [n.strip() for n in raw.split(",") if n.strip()]
    dimensions = []
    for name in names:
        dimension = _DIMENSION_MAP.get(name)
        if dimension is None:
            valid = ", ".join(sorted(_DIMENSION_MAP))
            print(f"Error: unknown dimension '{name}'. Valid: {valid}", file=sys.stderr)
            sys.exit(1)
        dimensions.append(dimension)
    return dimensions


def _resolve_evaluation_strategy() -> EvaluationStrategy:
    raw = os.getenv("PSALM_EVALUATION_STRATEGY", "") or EvaluationStrategy.FULLY_SEPARATE.value
    try:
        return EvaluationStrategy(raw)
    except ValueError:
        valid = ", ".join(s.value for s in EvaluationStrategy)
        print(f"Error: unknown evaluation strategy '{raw}'. Valid: {valid}", file=sys.stderr)
        sys.exit(1)


def _resolve_scenario_texts() -> tuple[str, str]:
    """Resolve PSALM_DEMO_SCENARIO to a (source_text, target_text) pair."""
    scenario = os.getenv("PSALM_DEMO_SCENARIO", "") or _DEFAULT_SCENARIO
    if scenario == "infringing":
        return COPYRIGHT_TEXT, INFRINGING_TEXT
    if scenario == "not-infringing":
        return COPYRIGHT_TEXT, NOT_INFRINGING_TEXT
    print(
        f"Error: unknown demo scenario '{scenario}'. Valid: infringing, not-infringing",
        file=sys.stderr,
    )
    sys.exit(1)


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
        "dimensions": _resolve_dimensions(),
        "evaluation_strategy": _resolve_evaluation_strategy(),
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
    print(f"  Dimensions           : {', '.join(d.name for d in cfg['dimensions'])}")
    print(f"  Evaluation strategy  : {cfg['evaluation_strategy'].value}")
    print(f"  Argumentation rounds : {cfg['argumentation_rounds']}")
    print(f"  Deliberation rounds  : {cfg['deliberation_rounds']}")
    print(f"  Time limit           : {cfg['time_limit_seconds']}s")


def _print_result(result: PSALMResult) -> None:
    print("\n" + "=" * 60)
    print(f"  VERDICT: {result.verdict}")
    print("=" * 60)
    print(f"\nRationale:\n  {result.rationale}")
    print("\nPer-dimension verdicts:")
    for dv in result.dimension_verdicts:
        print(
            f"  {dv.dimension:<16} [{dv.importance.value:<8}] {dv.verdict:<11}"
            f" (weighted score: {dv.weighted_score:.2f})"
        )
    print("\nMetadata:")
    print(f"  Duration:              {result.metadata.duration_seconds:.1f}s")
    print(f"  Argumentation rounds:  {result.metadata.argumentation_rounds_used}")
    print(f"  Deliberation rounds:   {result.metadata.deliberation_rounds_used}")
    print(f"  Voting strategy:       {result.metadata.voting_strategy_applied}")
    print("\nFull result (JSON):")
    print(result.to_json())


async def main() -> None:
    cfg = _load_config()
    source_text, target_text = _resolve_scenario_texts()

    print("=== PSALM EU Copyright Evaluation Demo ===\n")
    _print_config_summary(cfg)
    print("\nBuilding courtroom (pinging LLMs)...")

    psalm = await (
        PSALM()
        .with_prosecutor(**cfg["prosecutor"])
        .with_defense(**cfg["defense"])
        .with_judge(**cfg["judge"])
        .with_jury(cfg["jury"])
        .with_dimensions(cfg["dimensions"])
        .with_debate(
            argumentation_rounds=cfg["argumentation_rounds"],
            deliberation_rounds=cfg["deliberation_rounds"],
            time_limit_seconds=cfg["time_limit_seconds"],
        )
        .with_voting(["simple_majority", "trust_weighted", "judge_tiebreaker"])
        .with_evaluation_strategy(cfg["evaluation_strategy"])
        .build()
    )

    print("Evaluating texts...\n")
    result = await psalm.aevaluate(
        source_text=source_text,
        target_text=target_text,
    )

    _print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
