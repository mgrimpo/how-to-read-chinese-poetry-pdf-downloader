from dataclasses import dataclass
import dataclasses
from numbers import Number
import requests
import os
from PyPDF2 import PdfMerger, PdfReader
import asyncio
import aiohttp
from functools import partial

from get_pdf_links import EpisodeLink, get_episode_links

DOWNLOAD_FOLDER = "downloads"


@dataclass
class EpisodePdf:
    episode_number: int
    path: str
    num_pages: int | None  # None represents 'number of pages unknown'


async def main():
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        episode_links = get_episode_links()

        episode_pdfs_without_page_meta_data = map(
            partial(download_episode_pdf, session=session), episode_links
        )

        episode_pdfs = map(read_pdf_meta_data, episode_pdfs_without_page_meta_data)
        merge_pdfs(await asyncio.gather(*episode_pdfs))


def merge_pdfs(episode_pdfs: list[EpisodePdf]):
    pdfMerger = PdfMerger()
    current_page = 0
    for episode_pdf in episode_pdfs:
        pdfMerger.append(episode_pdf.path)
        pdfMerger.add_outline_item(
            pagenum=current_page, title=f"Episode {episode_pdf.episode_number}"
        )
        current_page += episode_pdf.num_pages
    pdfMerger.write("merged.pdf")


async def read_pdf_meta_data(episode_pdf: EpisodePdf) -> list[EpisodePdf]:
    episode_pdf = await episode_pdf
    pdfReader = PdfReader(episode_pdf.path)
    num_pages = len(pdfReader.pages)
    return dataclasses.replace(episode_pdf, num_pages=num_pages)


async def download_episode_pdf(
    episode_link: EpisodeLink, session: aiohttp.ClientSession
) -> EpisodePdf:
    """Download pdfs for the given links, writes them to disk and returns EpisodePdf metatdata"""
    episode_pdf = EpisodePdf(
        episode_number=episode_link.episode_number,
        path=_download_pdf_path(episode_link.episode_number),
        num_pages=None,  # unknown as of yet
    )
    if os.path.exists(episode_pdf.path):
        async with session.head(episode_link.url) as response:
            headers = response.headers
            response_size = headers.get("content-length", -1)
            response_size = int(response_size)
            if response_size > 0 and response_size == os.path.getsize(episode_pdf.path):
                _log_skip(episode_link, response_size)
                return episode_pdf
    async with session.get(episode_link.url) as response:
        content = await response.read()
        with open(episode_pdf.path, "wb") as f:
            f.write(content)
    return episode_pdf


def _log_skip(episode_link, response_size):
    print(
        f"Skipping download of episode {episode_link.episode_number} PDF as local file exists with same size as remote file ({response_size} bytes)"
    )


def _download_pdf_path(episode_number: Number):
    return f"{DOWNLOAD_FOLDER}{os.sep}{episode_number}.pdf"


if __name__ == "__main__":
    asyncio.run(main())
