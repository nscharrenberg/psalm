from psalm.dimensions.base import Dimension, Importance, SubDimension

CITATIONS = Dimension(
    name="Quotation/Citation",
    description="How portions of other works are used for legitimate purposes.",
    sub_dimensions=[
        SubDimension(
            name="Quotation Identification & Extraction",
            description=(
                "Quotation presence (whether target reproduces extracts from source - "
                "verbatim/near-verbatim quotations, close paraphrase maintaining source "
                "expression) and quotation explicitness (whether quotations are marked/attributed "
                "vs unmarked - quotation marks/block quotes used, attribution markers like "
                "'According to [source]', citation indicators like footnotes, or implicit/unmarked "
                "reproduction appearing as original text)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Legitimate Purpose",
            description=(
                "Purpose identification (what purpose quotations serve - criticism of source work, "
                "review/assessment, news reporting incorporating source, teaching/education, "
                "scientific research/analysis, public debate/commentary using source as evidence) "
                "and purpose substantiation (whether purpose is genuinely pursued with substantive "
                "engagement - depth of analysis/critique of quoted material, extent of original "
                "commentary/argument on quotes, integration into target's discourse, ratio of "
                "quotation to commentary, meaningful vs superficial engagement)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Fair Practice & Proportionality",
            description=(
                "Extent of taking (how much source text is reproduced - brief excerpts, several "
                "passages, or extensive reproduction; is amount necessary/proportionate for stated "
                "purpose; could purpose be achieved with less) and transformative context (whether "
                "quotations are integrated into original analysis vs standalone - do quotations "
                "embed within target's commentary/critique, does target add substantial original "
                "content, do quotations serve new purpose/function, could quotations stand alone "
                "as substitute for source, is added value provided)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Attribution & Source Acknowledgment",
            description=(
                "Source identification (whether source work is identified - title mentioned, work "
                "recognizable from context, ordinary reader could determine quoted work, "
                "identified for all quotations or only once) and author identification (whether "
                "author/rightholder is named - full name stated, author identifiable from context, "
                "named for all quotations or only once)."
            ),
            importance=Importance.HIGH,
        ),
        SubDimension(
            name="Fair Balance & Justification",
            description=(
                "Necessity (whether quotations are necessary for the purpose - could the point be "
                "made without quoting, are quotations the most efficient means) and market impact "
                "(whether quotation affects market for original work - potential substitution "
                "effect, impact on commercial value, harm to author's interests)."
            ),
            importance=Importance.MEDIUM,
        ),
        SubDimension(
            name="Work Already Disclosed",
            description=(
                "Prior disclosure (whether source work was already lawfully made available to the "
                "public before target was created - published in any form, accessible to target's "
                "audience, timing of disclosure relative to target creation)."
            ),
            importance=Importance.MEDIUM,
        ),
    ],
    importance=Importance.HIGH,
    dimension_type="exception",
)