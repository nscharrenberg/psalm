import polars as pl
from rich.console import Console

console = Console()

def filter_by_genres(temp_df: pl.DataFrame, genres: list[str], verbose: bool = False) -> pl.DataFrame:
    with console.status(f"Filtering by genre '{','.join(genres)}'..."):
        df = temp_df.filter(pl.col("genre").is_in(genres)).filter(pl.col("text_url").is_not_null())

        if verbose:
            console.print(f"Found {len(df)} books for genre '{','.join(genres)}'.")

        return df

def filter_by_genre(temp_df: pl.DataFrame, genre: str, verbose: bool = False) -> pl.DataFrame:
    with console.status(f"Filtering by genre '{genre}'..."):
        df = temp_df.filter(pl.col("genre") == genre).filter(pl.col("text_url").is_not_null())

        if verbose:
            console.print(f"Found {len(df)} books for genre '{genre}'.")

        return df

def filter_by_genres_separated(temp_df: pl.DataFrame, genres: list[str], verbose: bool = False) -> dict[str, pl.DataFrame]:
    dfs = {}
    for genre in genres:
        dfs[genre] = filter_by_genre(temp_df, genre, verbose)

    return dfs