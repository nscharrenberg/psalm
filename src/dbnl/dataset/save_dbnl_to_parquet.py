from pathlib import Path
from typing import Union

import polars as pl
from rich.console import Console

console = Console()

def save_dbnl_to_parquet(df: pl.DataFrame, output_file: Union[str, Path], verbose: bool = False, **kwargs):
    """
    Save the given Polars DataFrame to a PARQUET file.

    This function takes a Polars DataFrame and writes it to a specified location
    as a PARQUET file. If the directory structure required for the file does not exist,
    it will be created automatically. You can pass optional keyword arguments to
    customize the PARQUET writing process.

    Args:
        df: The Polars DataFrame to be saved.
        output_file: The file path where the DataFrame should be saved. This can be
            a string or a Path object.
        **kwargs: Additional keyword arguments passed to the Polars `write_parquet` method.
    """
    with console.status(f"Saving DBNL to PARQUET at '{output_file}'...'"):
        # Convert output_file to Path
        if not isinstance(output_file, Path):
            output_file = Path(output_file)

        # Create parent directories if they don't exist'
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write DataFrame to PARQUET
        df.write_parquet(output_file, **kwargs)

        if verbose:
            console.print(f"Saved DBNL to PARQUET at '{output_file}'.")