from rich.console import Console
import polars as pl

console = Console()

def load_dbnl_from_parquet(file_path: str, verbose: bool = False, **kwargs):
    with console.status("Loading dataset from Parquet"):
        df = pl.read_parquet(file_path, **kwargs)

        if verbose:
            console.print(f"Loaded {len(df)} books from Parquet.")

        return df