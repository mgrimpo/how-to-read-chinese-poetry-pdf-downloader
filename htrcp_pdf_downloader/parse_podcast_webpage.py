import re
from dataclasses import dataclass
from functools import reduce

import aiohttp
from bs4 import BeautifulSoup, PageElement, Tag

from errors import UnexpectedPatternException

HTRCP_PODCAST_PAGE_URL = "https://howtoreadchinesepoetry.com/"


@dataclass
class EpisodePdfLink:
    url: str
    episode_number: int
    title: str


@dataclass(kw_only=True)
class Topic:
    first_episode: int
    last_episode: int
    title: str


@dataclass
class PodcastMetadata:
    topics: list[Topic]
    episodes: list[EpisodePdfLink]


async def get_podcast_metadata(session: aiohttp.ClientSession) -> PodcastMetadata:
    async with session.get(HTRCP_PODCAST_PAGE_URL) as response:
        podcast_page_html = await response.text()
        soup = BeautifulSoup(podcast_page_html, "html.parser")

        return PodcastMetadata(_find_topics(soup), _find_episode_links(soup))


def _find_topics(soup: BeautifulSoup):
    def _text_starts_with_topic(elem: Tag) -> bool:
        match elem:
            case Tag():
                return elem.text.strip().startswith("Topic")
            case None:
                return False

    strong_elements: list[Tag] = soup.find_all("strong")
    topic_labels = filter(_text_starts_with_topic, strong_elements)

    topics = [*map(_topic_from_label, topic_labels)]
    _set_last_episode(topics)
    return topics


def _set_last_episode(topics):
    last_topic = topics[-1]
    for topic in reversed(topics[0:-1]):
        topic.last_episode = last_topic.first_episode - 1
        last_topic = topic


def _topic_from_label(topic_label):
    episode_label = None
    while not episode_label:
        next_paragraph: PageElement = topic_label.parent.next_sibling  # type: ignore
        maybe_episode_label: Tag = next_paragraph.find_next("strong")  # type: ignore
        if _content_starts_with_episode(maybe_episode_label):
            episode_label = maybe_episode_label
    beginning_number = _episode_number(episode_label)

    return Topic(
        first_episode=beginning_number, last_episode=-1, title=_topic_title(topic_label)
    )


def _topic_title(topic_label: Tag) -> str:
    match_result = re.search(r"Topic\s+\d+\s+(.+)", topic_label.text.strip())
    match match_result:
        case re.Match():
            return match_result.group(1)
        case unknown:
            raise UnexpectedPatternException(unknown)


def _find_episode_links(soup):
    strong_elements = soup.find_all("strong")
    episode_labels = filter(_content_starts_with_episode, strong_elements)
    episode_links: list[EpisodePdfLink] = []

    for episode_label in episode_labels:
        episode_links.append(
            EpisodePdfLink(
                url=_episode_pdf_url(episode_label),
                episode_number=_episode_number(episode_label),
                title=_episode_title(episode_label),
            )
        )
    print(*episode_links, sep="\n")
    return episode_links


def _episode_title(episode_label: Tag) -> str:
    siblings = filter(
        lambda sibling: not isinstance(sibling, Tag) or sibling.name != "a",
        episode_label.next_siblings,
    )
    title = reduce(lambda acc, element: acc + element.text, siblings, "")
    title = title.replace("[]", "")
    title = title.replace("\xa0", " ")
    return title.strip()


def _episode_pdf_url(episode_label) -> str:
    def _find_link_in_siblings(elem: Tag) -> str:
        anchor_element = elem.find_next_sibling("a")
        match anchor_element:
            case Tag(attrs={"href": href, **rest}):
                return href
            case unexpected:
                raise UnexpectedPatternException(unexpected)

    match _find_link_in_siblings(episode_label):
        case str(url):
            return url
        case unexpected:
            raise UnexpectedPatternException(unexpected)


def _episode_number(episode_label) -> int:
    match_result = re.search(r"Episode (\d+)", episode_label.text.strip())
    match match_result:
        case re.Match():
            return int(match_result.group(1))
        case unknown:
            raise UnexpectedPatternException(unknown)


def _content_starts_with_episode(elem: Tag) -> bool:
    """Check for elements with string content starting with 'Episode'"""
    match elem:
        case Tag(contents=contents):
            if not isinstance(contents[0], str):
                return False
            return contents[0].strip().startswith("Episode")
        case None:
            return False
