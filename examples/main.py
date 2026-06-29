import asyncio
import os
import sys

from psalm import PSALM, PSALMResult

COPYRIGHT_TEXT = """
De machine in de hoek van de verlaten textielfabriek hoestte. Niet als een mens, niet als een dier, maar als een mechanisme dat zich herinnerde hoe het ooit had geleefd. Elara Voss, met haar handen vol littekens van draden die nooit hadden moeten breken, veegde het stof van een bankschroef die groter was dan haar torso. Ze had de fabriek niet gekozen; de fabriek had haar uitgekozen, drie weken geleden, toen de stad besloot dat oude gebouwen alleen nog waarde hadden als herinnering.

De deur achter haar kraakte. Niet van de wind—de wind waagde zich niet in deze hal—maar van iemand die niet wilde opvallen. Elara draaide zich niet om. In plaats daarvan tikte ze met haar vinger tegen de metalen arm van de weefgetouw, die trilde alsof hij een hart had.

"Je bent te laat," zei ze. "De laatste schroef is al uit de muur."

Achter haar schraapte een schoen over beton. "Ik ben niet hier voor de schroeven." De stem was ruw, alsof hij door roest was gefilterd. Elara kende die stem. Iedereen in de stad kende die stem, hoewel niemand hem ooit had gehoord. Het was de stem van Dain Marrow, de man die zijn eigen schaduw had verloren in een gokspel met een reiziger die nooit was aangekomen.

"Dan ben je hier voor de weefgetouwen," zei Elara. "Die zijn ook al weg. Behalve deze." Ze klopte op de machine, die antwoordde met een diepe, metalen zucht.

Dain liep dichterbij. Zijn laarzen lieten geen afdrukken na in het stof. "Ik zoek iets dat niet gestolen kan worden."

Elara snoof. "In deze stad is alles al gestolen. Zelfs de herinneringen." Ze trok aan een hefboom. De weefgetouw kwam met een schok tot leven, zijn naalden dansend over een lap stof die er niet was. "Behalve misschien dit."

Dain boog zich voorover. Zijn handen, bedekt met inkt die nooit droogde, zweefden boven het niets waar de stof had moeten zijn. "Wat is het?"

"Een patroon," zei Elara. "Eentje dat nooit is geweven. De draad is van een kleur die niet bestaat. De naalden zijn van een metaal dat niet smelt. En de wever..." Ze aarzelde. "De wever is al dood voordat hij begon."

Dain’s vinger raakte de lucht waar de stof had moeten hangen. Zijn vingertop werd doorschijnend, alsof hij zelf het patroon werd. "Hoeveel?"

Elara schudde haar hoofd. "Het is niet te koop. Het is niet eens af. Maar als je luistert, hoor je het."

Ze hielden allebei hun adem in. Ergens in de diepten van de machine, tussen het gekras van roest en het piepen van vergeten veren, was een geluid. Een fluistering. Niet van woorden, maar van bedoelingen. Alsof de weefgetouw niet alleen stof, maar ook keuzes weefde.

Dain trok zijn hand terug. Zijn vingertop was weer vast. "Ik neem het."

Elara glimlachte voor het eerst in weken. "Ik dacht al dat je dat zou zeggen." Ze greep een hamer van de werkbank en sloeg op een klep in de zijkant van de machine. De fluistering werd luider, een koor van stemmen die nooit een mond hadden gehad. "Maar je moet betalen met iets dat je niet kunt missen."

Dain’s ogen vernauwden zich. "Ik heb niets meer."

"Iedereen heeft iets," zei Elara. "Zelfs jij." Ze wees naar zijn borst, waar zijn hart had moeten kloppen. "Daar. Het ding dat je verliest elke keer als je ademhaalt."

Dain legde zijn hand op zijn borst. Zijn ademhaling stokte. "Mijn..."

"Je schaduw is al weg," onderbrak Elara. "Maar je verleden is nog hier. Geef me de herinnering die je het meest haat."

De fabriek hield zijn adem in. De weefgetouw wachtte. Dain’s handen balden zich tot vuisten, en toen, langzaam, ontspanden ze. "De dag dat ik mijn dochter beloofde dat ik zou stoppen met gokken." Zijn stem brak niet. Hij was al lang geleden gebroken.

Elara knikte. "Dat is genoeg."

Ze draaide aan een rad. De machine begon te weven, niet met draad, maar met licht en schaduw, met geluiden die geen naam hadden. Dain’s herinnering loste op in de lucht, werd deel van het patroon. De fluistering werd een lied, een lied zonder woorden, zonder melodie, maar vol betekenis.

Toen het voorbij was, stond Dain voor een lap stof die niet bestond, maar die hij toch kon aanraken. En op de plek waar zijn herinnering was geweest, voelde hij iets nieuws: een leegte die niet pijn deed.

"Wat is het?" vroeg hij.

Elara raakte de stof aan, die onder haar vingers veranderde in een spiegel. "Een begin," zei ze. "Of een einde. Dat hangt ervan af hoe je ernaar kijkt."

Buiten begon de stad te ontwaken. Maar in de fabriek was het nog steeds nacht. En ergens, diep in de machine, fluisterde iets hun namen.
"""

INFRINGING_TEXT = """
In de hoek van de verlaten fabriek hoestte de machine. Niet als een levend wezen, niet als een mechaniek dat nog functioneerde, maar als iets dat zich herinnerde hoe het ooit had geklonken. Elara Voss had handen vol littekens van draden die niet hadden mogen breken. Ze veegde stof van een bankschroef die groter was dan haar bovenlichaam. De fabriek had haar niet gekozen; ze was hier gebleven toen de stad besloot dat oude muren alleen nog dienden als schaduwen van het verleden.

De deur achter haar kreunde. Niet door de wind—die waagde zich niet in deze hal—maar door iemand die niet wilde dat zijn komst opviel. Elara draaide zich niet om. In plaats daarvan tikte ze met haar knokkel tegen de metalen arm van de weefgetouw, die trilde alsof hij nog steeds leefde.

"Je komt te laat," zei ze. "De laatste schroef is al verwijderd."

Achter haar schraapte een laars over het beton. "Ik ben niet voor de schroeven gekomen." De stem was schor, alsof hij door roest en tijd was gefilterd. Elara kende die stem. Iedereen in de stad kende die stem, ook al had niemand hem ooit horen spreken. Het was Dain Marrow, de man wiens schaduw was verdwenen in een gokspel met een reiziger die nooit was verschenen.

"Dan ben je voor de weefgetouwen gekomen," zei Elara. "Die zijn ook al weg. Behalve deze." Ze klopte op de machine, die reageerde met een diepe, holle zucht.

Dain liep naderbij. Zijn laarzen lieten geen sporen na in het stof. "Ik zoek iets dat niet kan worden meegenomen."

Elara snoof. "In deze stad is alles al meegenomen. Zelfs de echo’s." Ze trok aan een hefboom. De weefgetouw schokte tot leven, zijn naalden bewogen over een lap stof die niet bestond. "Behalve misschien dit."

Dain boog zich voorover. Zijn handen, bedekt met inkt die nooit opdroogde, zweefden boven de leegte waar de stof had moeten hangen. "Wat is het?"

"Een ontwerp," zei Elara. "Eentje dat nooit was geweven. De draad is van een kleur die geen naam heeft. De naalden zijn van een metaal dat niet smelt. En de wever..." Ze aarzelde. "De wever is al dood voordat hij begon met weven."

Dains vingertop raakte de lucht waar de stof had moeten zijn. Zijn huid werd voor een moment doorschijnend, alsof hij zelf het patroon werd. "Hoeveel?"

Elara schudde haar hoofd. "Het is niet te koop. Het is niet eens af. Maar als je luistert, hoor je het."

Ze hielden allebei hun adem in. Ergens diep in de machine, tussen het gekras van roest en het piepen van vergeten veren, klonk een geluid. Een fluistering, niet van woorden, maar van bedoelingen. Alsof de weefgetouw niet alleen stof, maar ook loten weefde.

Dain trok zijn hand terug. Zijn vingertop was weer vast. "Ik neem het."

Elara glimlachte voor het eerst in weken. "Ik dacht al dat je dat zou doen." Ze greep een hamer van de werkbank en sloeg op een klep in de zijkant van de machine. De fluistering werd luider, een koor van stemmen die nooit een mond hadden gehad. "Maar je moet betalen met iets dat je niet kunt missen."

Dains ogen vernauwden zich. "Ik heb niets meer."

"Iedereen heeft iets," zei Elara. "Zelfs jij." Ze wees naar zijn borst, waar zijn hart had moeten kloppen. "Daar. Het ding dat je verliest elke keer als je ademhaalt."

Dain legde zijn hand op zijn borst. Zijn ademhaling stokte. "Mijn..."

"Je schaduw is al weg," onderbrak Elara. "Maar je verleden is nog hier. Geef me de herinnering die je het meest verafschuwt."

De fabriek hield zijn adem in. De weefgetouw wachtte. Dains handen balden zich tot vuisten, en toen, langzaam, ontspanden ze. "De dag waarop ik mijn dochter beloofde te stoppen met gokken." Zijn stem was kalm. Hij was al lang geleden gebroken.

Elara knikte. "Dat is genoeg."

Ze draaide aan een rad. De machine begon te weven, niet met garen, maar met licht en duisternis, met geluiden die geen benaming kenden. Dains herinnering loste op in de lucht, werd deel van het patroon. De fluistering werd een lied, een lied zonder melodie, zonder woorden, maar vol betekenis.

Toen het voorbij was, stond Dain voor een lap stof die niet bestond, maar die hij toch kon aanraken. En op de plek waar zijn herinnering was geweest, voelde hij iets nieuws: een leegte die niet pijn deed.

"Wat is het?" vroeg hij.

Elara raakte de stof aan, die onder haar vingers veranderde in een spiegel. "Een nieuw begin," zei ze. "Of een afsluiting. Dat hangt af van je perspectief."

Buiten kwam de stad langzaam tot leven. Maar in de fabriek heerste nog steeds de nacht. En diep in de machine fluisterde iets hun namen.
"""

NOT_INFRINGING_TEXT = """
De oude pers in de hoek van de verlaten drukkerij kreunde. Niet als een mens, niet als een dier, maar als een machine die zich herinnerde hoe het ooit had geklonken. Liora Vex had handen vol littekens van loden letters die nooit hadden moeten vallen. Ze veegde het stof van een letterkast die hoger was dan haar schouder. De drukkerij had haar niet gekozen; ze was gebleven toen de stad besloot dat oude woorden alleen nog waarde hadden als herinnering.

De deur achter haar piepte. Niet door de wind—die durfde niet binnen te dringen—maar door iemand die niet wilde opvallen. Liora draaide zich niet om. In plaats daarvan tikte ze met haar knokkel tegen de ijzeren arm van de pers, die trilde alsof hij nog steeds leefde.

"Je bent te laat," zei ze. "De laatste letter is al gesmolten."

Achter haar schraapte een schoen over de vloer. "Ik ben niet hier voor de letters." De stem was ruw, alsof hij door jaren van stilte was geslepen. Liora kende die stem. Iedereen in de wijk kende die stem, ook al had niemand hem ooit horen spreken. Het was Kael Dusk, de man wiens stem was verdwenen na een ruzie met een man die nooit was teruggekomen.

"Dan ben je hier voor de pers," zei Liora. "Die is ook al weg. Behalve deze." Ze klopte op de machine, die antwoordde met een diepe, metalen zucht.

Kael liep dichterbij. Zijn laarzen lieten geen afdrukken na in het stof. "Ik zoek iets dat niet kan worden gestolen."

Liora snoof. "In deze stad is alles al gestolen. Zelfs de echo’s van de woorden." Ze trok aan een hefboom. De pers schokte tot leven, zijn walsen draaiden over papier dat niet bestond. "Behalve misschien dit."

Kael boog zich voorover. Zijn handen, bedekt met littekens van woorden die nooit waren uitgesproken, zweefden boven de leegte waar het papier had moeten liggen. "Wat is het?"

"Een tekst," zei Liora. "Eentje die nooit is gedrukt. De inkt was van een kleur die geen naam had. De letters waren van een metaal dat niet roestte. En de drukker..." Ze aarzelde. "De drukker is al dood voordat hij begon."

Kael’s vingertop raakte de lucht waar het papier had moeten zijn. Zijn huid werd voor een moment doorschijnend, alsof hij zelf de tekst werd. "Hoeveel?"

Liora schudde haar hoofd. "Het is niet te koop. Het is niet eens af. Maar als je luistert, hoor je het."

Ze hielden allebei hun adem in. Ergens diep in de machine, tussen het gekras van metaal en het piepen van vergeten veren, klonk een geluid. Een gefluister, niet van woorden, maar van bedoelingen. Alsof de pers niet alleen tekst, maar ook keuzes drukte.

Kael trok zijn hand terug. Zijn vingertop was weer vast. "Ik neem het."

Liora glimlachte voor het eerst in maanden. "Ik dacht al dat je dat zou doen." Ze greep een hamer van de werkbank en sloeg op een klep in de zijkant van de machine. Het gefluister werd luider, een koor van stemmen die nooit een mond hadden gehad. "Maar je moet betalen met iets dat je niet kunt missen."

Kael’s ogen vernauwden zich. "Ik heb niets meer."

"Iedereen heeft iets," zei Liora. "Zelfs jij." Ze wees naar zijn keel, waar zijn stem had moeten klinken. "Daar. Het ding dat je verliest elke keer als je zwijgt."

Kael legde zijn hand op zijn keel. Zijn ademhaling stokte. "Mijn..."

"Je stem is al weg," onderbrak Liora. "Maar je woorden zijn nog hier. Geef me het woord dat je nooit hebt uitgesproken."

De drukkerij hield zijn adem in. De pers wachtte. Kael’s handen balden zich tot vuisten, en toen, langzaam, ontspanden ze. "Het woord dat ik had moeten zeggen tegen mijn zoon." Zijn stem was niet meer dan een schor gefluister.

Liora knikte. "Dat is genoeg."

Ze draaide aan een rad. De machine begon te drukken, niet met inkt, maar met geluid en stilte, met klanken die geen betekenis hadden. Kael’s onuitgesproken woord loste op in de lucht, werd deel van de tekst. Het gefluister werd een stem, een stem zonder woorden, zonder geluid, maar vol betekenis.

Toen het voorbij was, stond Kael voor een vel papier dat niet bestond, maar dat hij toch kon aanraken. En op de plek waar zijn woord was geweest, voelde hij iets nieuws: een stilte die niet pijn deed.

"Wat is het?" vroeg hij.

Liora raakte het papier aan, dat onder haar vingers veranderde in een spiegel. "Een begin," zei ze. "Of een einde. Dat hangt ervan af of je luistert."

Buiten begon de stad te ontwaken. Maar in de drukkerij was het nog steeds stil. En diep in de pers fluisterde iets hun verhalen.
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
        target_text=NOT_INFRINGING_TEXT,
    )

    _print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
