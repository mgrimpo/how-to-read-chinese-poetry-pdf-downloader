from dataclasses import dataclass
import dataclasses
from numbers import Number
import os
from typing import Awaitable
from PyPDF2 import PdfMerger, PdfReader
import asyncio
import aiofiles
import aiohttp
from functools import partial

from get_pdf_links import EpisodePdfLink, PodcastMetaData, Topic, get_episode_links

DOWNLOAD_FOLDER = "downloads"


@dataclass(kw_only=True, frozen=True)
class EpisodePdf:
    episode_number: int
    title: str
    path: str


@dataclass(kw_only=True, frozen=True)
class EpisodePdfWithNumPages(EpisodePdf):
    num_pages: int


@dataclass(kw_only=True)
class TopicWithEpisodes(Topic):
    episodes: list[EpisodePdfWithNumPages]


async def main():
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        podcast_meta_data = await get_episode_links(session)

        episode_pdfs_without_page_meta_data = map(
            partial(download_episode_pdf, session=session), podcast_meta_data.episodes
        )

        episode_pdf_awaitables = map(add_num_pages, episode_pdfs_without_page_meta_data)
        episode_pdfs: list[EpisodePdfWithNumPages] = await asyncio.gather(
            *episode_pdf_awaitables
        )

        merge_pdfs(_merge_topics_and_episodes(podcast_meta_data.topics, episode_pdfs))


def _merge_topics_and_episodes(topics: list[Topic], episode_pdfs: list[EpisodePdfWithNumPages]):
    remaining_episodes = set(episode_pdfs)
    result: list[TopicWithEpisodes] = []
    for topic in topics:
        if topic.last_episode != -1:
            topic_episodes = set(
                filter(
                    lambda episode: topic.first_episode <= episode.episode_number
                    and episode.episode_number <= topic.last_episode,
                    remaining_episodes,
                )
            )
            remaining_episodes = remaining_episodes - topic_episodes
        else:
            topic_episodes = remaining_episodes
        result.append(
            TopicWithEpisodes(
                episodes=sorted(topic_episodes, key=lambda e: e.episode_number), **dataclasses.asdict(topic)
            )
        )
    return result


def merge_pdfs(topics: list[TopicWithEpisodes]):
    pdfMerger = PdfMerger()
    current_page = 0  # starts with 0, starting with 1 yields off by one errors
    for topic in topics:
        last_episdoe = topic.last_episode if topic.last_episode != -1 else " "
        title = topic.title.replace(":", " –")
        topic_outline_item = pdfMerger.add_outline_item(
            pagenum=current_page,
            title=f'{topic.first_episode}-{last_episdoe}: {title}',
        )
        for episode_pdf in topic.episodes:
            pdfMerger.append(episode_pdf.path)
            pdfMerger.add_outline_item(
                pagenum=current_page,
                title=f"Episode {episode_pdf.episode_number} – {episode_pdf.title}",
                parent=topic_outline_item
            )
            current_page += episode_pdf.num_pages
    pdfMerger.write("merged.pdf")


async def add_num_pages(
    episode_pdf_awaitable: Awaitable[EpisodePdf],
) -> EpisodePdfWithNumPages:
    episode_pdf = await episode_pdf_awaitable
    pdfReader = PdfReader(episode_pdf.path)
    num_pages = len(pdfReader.pages)
    return EpisodePdfWithNumPages(
        num_pages=num_pages, **dataclasses.asdict(episode_pdf)
    )


async def download_episode_pdf(
    episode_link: EpisodePdfLink, session: aiohttp.ClientSession
) -> EpisodePdf:
    """Download pdfs for the given links, writes them to disk and returns EpisodePdf metatdata"""
    episode_pdf = EpisodePdf(
        episode_number=episode_link.episode_number,
        title=episode_link.title,
        path=_download_pdf_path(episode_link.episode_number),
    )
    if os.path.exists(episode_pdf.path):
        async with session.head(episode_link.url) as response:
            response_size = response.headers.get("content-length", -1)
            response_size = int(response_size)
            if response_size > 0 and response_size == os.path.getsize(episode_pdf.path):
                _log_skip(episode_link, response_size)
                return episode_pdf
    async with session.get(episode_link.url) as response:
        content = await response.read()
        async with aiofiles.open(episode_pdf.path, mode="wb") as f:
            await f.write(content)
        return episode_pdf


def _log_skip(episode_link, response_size):
    print(
        f"Skipping download of episode {episode_link.episode_number} PDF as local file exists with same size as remote file ({response_size} bytes)"
    )


def _download_pdf_path(episode_number: int):
    return f"{DOWNLOAD_FOLDER}{os.sep}{episode_number}.pdf"


if __name__ == "__main__":
    asyncio.run(main())
