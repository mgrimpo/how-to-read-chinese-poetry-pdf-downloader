from dataclasses import dataclass
from doctest import UnexpectedException
from functools import reduce
import re
import aiohttp
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag
from errors import UnexpectedPatternException

HTRCP_PODCAST_PAGE_URL = "https://howtoreadchinesepoetry.com/"


@dataclass
class EpisodeLink:
    url: str
    episode_number: int
    title: str | None


async def get_episode_links(session: aiohttp.ClientSession):
    async with session.get(HTRCP_PODCAST_PAGE_URL) as response:
        podcast_page_html = await response.text()
        soup = BeautifulSoup(podcast_page_html, "html.parser")
        strong_elements = soup.find_all("strong")
        episode_labels = filter(content_starts_with_episode, strong_elements)
        episode_links: list[EpisodeLink] = []

        for episode_label in episode_labels:
            episode_links.append(
                EpisodeLink(
                    url=episode_pdf_url(episode_label),
                    episode_number=episode_number(episode_label),
                    title=episode_title(episode_label),
                )
            )
        print(*episode_links, sep="\n")
        return episode_links

def episode_title(episode_label: Tag):
    def _tag_text_join(first_tag, second_tag):
        match [first_tag, second_tag]:
            case [str(first_text), str(second_text)]: return first_text + second_text
            case [Tag(text=first_text), str(second_text)]: return first_text + second_text
            case [str(first_text), Tag(text=second_text)]: return first_text + second_text
            case [Tag(text=first_text), Tag(text=second_text)]: return first_text + second_text
    siblings = filter( lambda tag: tag.name != 'a', episode_label.next_siblings)
    title = reduce(_tag_text_join, siblings)
    title = title.replace('[]', '')
    title = title.replace('\xa0', ' ')
    return title.strip()

def episode_pdf_url(episode_label):
    match find_link_in_siblings(episode_label):
        case str(url):
            return url
        case unexpected:
            raise UnexpectedPatternException(unexpected)


def episode_number(episode_label):
    result = re.search("Episode (\d+)", episode_label.text.strip()).group(1)
    return int(result)


def find_link_in_siblings(elem: Tag) -> Tag:
    anchor_element = elem.find_next_sibling("a")
    match anchor_element:
        case Tag(attrs={"href": href, **rest}):
            return href
        case None:
            return None
        case unexpected:
            raise UnexpectedPatternException(unexpected)


def content_starts_with_episode(elem: Tag) -> bool:
    """Check for elements with string content starting with 'Episode'"""

    match elem:
        case Tag(contents=contents):
            if not isinstance(contents[0], str):
                return False
            return contents[0].strip().startswith("Episode")
        case None:
            return False
