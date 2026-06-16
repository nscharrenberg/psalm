from rich.console import Console
import polars as pl
import requests
from requests.exceptions import RequestException

console = Console()


def add_text_from_text_url(df: pl.DataFrame, verbose: bool = False, max_concurrency: int = 15) -> tuple[
    pl.DataFrame, list[str]]:
    import asyncio
    import aiohttp

    async def fetch_text(session: aiohttp.ClientSession, row: dict, sem: asyncio.Semaphore):
        text_url = row["text_url"]
        ti_id = row["ti_id"]
        async with sem:
            if text_url:
                try:
                    async with session.get(text_url) as response:
                        response.raise_for_status()
                        text = await response.text()
                        return text.strip(), None
                except Exception:
                    return "", ti_id
            else:
                return "", ti_id

    async def process_urls():
        texts = []
        failed_ti_ids = []
        sem = asyncio.Semaphore(max_concurrency)

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_text(session, row, sem)
                     for row in df.iter_rows(named=True)]
            results = await asyncio.gather(*tasks)

            for text, failed_id in results:
                texts.append(text)
                if failed_id:
                    failed_ti_ids.append(failed_id)

        return texts, failed_ti_ids

    with console.status("Adding text from 'text_url' column..."):
        texts, failed_ti_ids = asyncio.run(process_urls())

        df = df.with_columns(pl.Series(name="text", values=texts))

        if verbose:
            success_count = len(df) - len(failed_ti_ids)
            fail_count = len(failed_ti_ids)

            console.print(f"Added {success_count} texts, {fail_count} failed.")
            if fail_count > 0:
                console.print(f"Failed TI IDs: {', '.join(failed_ti_ids)}")

        return df, failed_ti_ids


def download(url: str) -> str:
    with console.status(f"Downloading text from '{url}'..."):
        try:
            response = requests.get(url)
            response.raise_for_status()
            text = response.text
        except RequestException as e:
            console.print(f"[red]Error downloading text from '{url}': {str(e)}[/red]")
            text = ""

        return text