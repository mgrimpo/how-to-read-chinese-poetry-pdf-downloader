import asyncio
import dataclasses
import os
from dataclasses import dataclass
from functools import partial
from typing import Awaitable

import aiofiles
import aiohttp
from PyPDF2 import PdfMerger, PdfReader

from parse_podcast_webpage import EpisodePdfLink, Topic, get_podcast_metadata

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
        podcast_metadata = await get_podcast_metadata(session)

        episode_pdfs_without_num_pages = map(
            partial(download_episode_pdf, session=session), podcast_metadata.episodes
        )

        episode_pdf_awaitables = map(_add_num_pages, episode_pdfs_without_num_pages)
        episode_pdfs: list[EpisodePdfWithNumPages] = await asyncio.gather(  # type: ignore
            *episode_pdf_awaitables
        )

        merge_pdfs(_merge_topics_and_episodes(podcast_metadata.topics, episode_pdfs))


def _merge_topics_and_episodes(
        topics: list[Topic], episode_pdfs: list[EpisodePdfWithNumPages]
):
    remaining_episodes = set(episode_pdfs)
    result: list[TopicWithEpisodes] = []
    for topic in topics:
        if topic.last_episode != -1:
            topic_episodes = set(
                filter(
                    lambda episode: topic.first_episode <= episode.episode_number <= topic.last_episode,
                    remaining_episodes,
                )
            )
            remaining_episodes = remaining_episodes - topic_episodes
        else:
            topic_episodes = remaining_episodes
        result.append(
            TopicWithEpisodes(
                episodes=sorted(topic_episodes, key=lambda e: e.episode_number),
                **dataclasses.asdict(topic),
            )
        )
    return result


def merge_pdfs(topics: list[TopicWithEpisodes]):
    pdf_merger = PdfMerger()
    current_page = 0  # pages start with 0, starting with 1 yields off-by-one errors
    for topic in topics:
        last_episode = topic.last_episode if topic.last_episode != -1 else " "
        title = topic.title.replace(":", " –")
        topic_outline_item = pdf_merger.add_outline_item(
            pagenum=current_page,
            title=f"{topic.first_episode}-{last_episode}: {title}",
        )
        for episode_pdf in topic.episodes:
            pdf_merger.append(episode_pdf.path)
            pdf_merger.add_outline_item(
                pagenum=current_page,
                title=f"Episode {episode_pdf.episode_number} – {episode_pdf.title}",
                parent=topic_outline_item,
            )
            current_page += episode_pdf.num_pages
    pdf_merger.write("merged.pdf")


async def _add_num_pages(
        episode_pdf_awaitable: Awaitable[EpisodePdf],
) -> EpisodePdfWithNumPages:
    episode_pdf = await episode_pdf_awaitable
    pdf_reader = PdfReader(episode_pdf.path)
    num_pages = len(pdf_reader.pages)
    return EpisodePdfWithNumPages(
        num_pages=num_pages, **dataclasses.asdict(episode_pdf)
    )


async def download_episode_pdf(
        episode_link: EpisodePdfLink, session: aiohttp.ClientSession
) -> EpisodePdf:
    """Download pdfs for the given links, writes them to disk and returns EpisodePdf metadata"""
    episode_pdf = EpisodePdf(
        episode_number=episode_link.episode_number,
        title=episode_link.title,
        path=f"{DOWNLOAD_FOLDER}{os.sep}{episode_link.episode_number}.pdf",
    )
    if os.path.exists(episode_pdf.path):
        async with session.head(episode_link.url) as response:
            response_size = response.headers.get("content-length", '-1')
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
        f"Skipping download of episode {episode_link.episode_number} PDF as local file exists with same size as "
        f"remote file ({response_size} bytes) "
    )


if __name__ == "__main__":
    asyncio.run(main())
