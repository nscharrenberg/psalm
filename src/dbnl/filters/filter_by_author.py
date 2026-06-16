import polars as pl
from rich.console import Console

console = Console()

def filter_by_authors(temp_df: pl.DataFrame, authors: list[str], verbose: bool = False) -> pl.DataFrame:
    with console.status(f"Filtering by authors '{', '.join(authors)}'..."):
        df = temp_df.filter(pl.col("pers_id").is_in(authors)).filter(pl.col("text_url").is_not_null())

        if verbose:
            console.print(f"Found {len(df)} books for author(s) '{', '.join(authors)}'.")

        return df

def filter_by_author(temp_df: pl.DataFrame, pers_id: str, verbose: bool = False) -> pl.DataFrame:
    with console.status(f"Filtering by author '{pers_id}'..."):
        df = temp_df.filter(pl.col("pers_id") == pers_id).filter(pl.col("text_url").is_not_null())

        if verbose:
            console.print(f"Found {len(df)} books for author '{pers_id}'.")

        return df

def filter_by_authors_separated(temp_df: pl.DataFrame, authors: list[str], verbose: bool = False) -> dict[str, pl.DataFrame]:
    dfs = {}
    for author in authors:
        dfs[author] = filter_by_author(temp_df, author, verbose)

    return dfs