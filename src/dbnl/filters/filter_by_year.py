from typing import Optional

import polars as pl
from rich.console import Console

console = Console()

def filter_by_year(temp_df: pl.DataFrame, min_year: int = 1900, max_year: Optional[int] = None, strict: bool = False, verbose: bool = False) -> pl.DataFrame:
    """
    Filters a DataFrame by publication year, either inclusively or strictly, within a specified range.

    The method allows filtering rows of a given DataFrame based on the publication year column. The `min_year` specifies the
    lower bound of the filter, and `max_year`, if provided, specifies the upper bound. The filtering can be done in a strict
    manner (exclusive of boundary years) or non-strict manner (inclusive of boundary years). Optionally, it can provide
    information about the number of matched entries.

    Args:
        temp_df (pl.DataFrame): The input DataFrame to be filtered. It is expected to contain a column representing publication year.
        min_year (int): The starting year for the filtering range. Defaults to 1900.
        max_year (Optional[int]): The ending year for the filtering range. If None, the upper bound is not applied.
        strict (bool): A flag to control whether the filtering is strict. If False, includes boundary years; if True, excludes
                       boundary years. Defaults to False.
        verbose (bool): A flag to control verbosity. If True, prints the number of records found after filtering. Defaults to False.

    Returns:
        pl.DataFrame: A filtered DataFrame containing only rows that meet the criteria based on the publication year.
    """
    after_message = f" and before '{max_year}'" if max_year else ""
    with console.status(f"Filtering by books published after year '{min_year}'{after_message}..."):
        if not strict:
            # Must be greater than or equal to year
            df = temp_df.filter(
                pl.col("_jaar").is_not_null() & (pl.col("_jaar") >= min_year)
            )

            if max_year:
                df = df.filter(pl.col("_jaar") <= max_year)
        else:
            # Must be strictly greater than year
            df = temp_df.filter(
                pl.col("_jaar").is_not_null() & (pl.col("_jaar") > min_year)
            )

            if max_year:
                df = df.filter(pl.col("_jaar") < max_year)

        if verbose:
            console.print(f"Found {len(df)} books published after '{min_year}'{after_message}.")

        return df