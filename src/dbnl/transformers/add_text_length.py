from typing import Any

from langchain_core.messages.utils import count_tokens_approximately
from rich.console import Console
import polars as pl
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, \
    MofNCompleteColumn, TaskID

console = Console()


async def add_text_length(df: pl.DataFrame, max_concurrency: int = 15, column_name: str = "text") -> pl.DataFrame:
    import asyncio

    df = df.with_row_index()

    semaphore = asyncio.Semaphore(max_concurrency)

    with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
    ) as progress:
        task = progress.add_task("Calculating Text Token Lengths...", total=len(df))

        async def count_text_length(index: int, row: dict[str, Any], task_id: TaskID):
            async with semaphore:
                text: str = row[column_name]
                ti_id: str = row["ti_id"]
                progress.update(
                    task_id,
                    advance=0,
                    description=f"Calculating Text Token Lengths ({ti_id})..."
                )


                if not text or not text.strip():
                    progress.update(
                        task_id,
                        advance=1
                    )

                    return index, 0, 0

                text_length = len(text.split())

                try:
                    token_length = count_tokens_approximately(text)
                except Exception as e:
                    console.print(f"\n[red]❌ Book {ti_id} ({index + 1}) failed to be counted (defaulting to -1): {str(e)}[/red]\n")
                    progress.update(
                        task_id,
                        advance=1,
                    )
                    return index, text_length, -1
                else:
                    progress.update(
                        task_id,
                        advance=1
                    )
                    return index, text_length, token_length

        tasks = [
            count_text_length(row["index"], row, task) for row in df.iter_rows(named=True)
        ]

        results = await asyncio.gather(*tasks)

        progress.update(
            task,
            completed=len(df),
            description="Finished counting text lengths."
        )

        await asyncio.sleep(0.3)

    results.sort(key=lambda x: x[0])
    counted_text = [result[1] for result in results]
    counted_tokens = [result[2] for result in results]

    df_with_counted = df.with_columns(
        pl.Series(name="text_length", values=counted_text),
        pl.Series(name="token_length", values=counted_tokens),
    )

    return df_with_counted