from typing import Optional

import polars as pl
from rich.console import Console

console = Console()

def filter_by_text_length(temp_df: pl.DataFrame, min_length: int = 300, max_length: Optional[int] = None, verbose: bool = False) -> pl.DataFrame:
    max_length_message = f" and less than '{max_length}'" if max_length else ""
    with console.status(f"Filtering by text length '{min_length}'{max_length_message}..."):
        # Must be greater than or equal to year
        df = temp_df.filter(
            pl.col("text").is_not_null() & (pl.col("text").str.len_chars() >= min_length)
        )

        if max_length:
            df = df.filter(pl.col("text").str.len_chars() <= max_length)

        if verbose:
            console.print(f"Found {len(df)} books with length with more than '{min_length}'{max_length_message} characters.")

        return df