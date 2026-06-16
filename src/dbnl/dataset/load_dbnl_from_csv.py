from rich.console import Console
import polars as pl

console = Console()

def load_dbnl_from_csv(file_path: str, verbose: bool = False, dbnl_config: bool = False, **kwargs):
    with console.status("Loading dataset from CSV"):
        if dbnl_config:
            if verbose:
                console.print("Using DBNL default config.")

            kwargs["has_header"] = True
            kwargs["separator"] = "|"
            kwargs["encoding"] = "utf-8"
            kwargs["skip_rows"] = 1

        df = pl.read_csv(file_path, **kwargs)

        if verbose:
            console.print(f"Loaded {len(df)} books from CSV.")

        return df