from dataclasses import dataclass
from functools import reduce
import re
import aiohttp
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, PageElement
from errors import UnexpectedPatternException

HTRCP_PODCAST_PAGE_URL = "https://howtoreadchinesepoetry.com/"


@dataclass
class EpisodeLink:
    url: str
    episode_number: int
    title: str


async def get_episode_links(session: aiohttp.ClientSession) -> list[EpisodeLink]:
    async with session.get(HTRCP_PODCAST_PAGE_URL) as response:
        podcast_page_html = await response.text()
        soup = BeautifulSoup(podcast_page_html, "html.parser")
        strong_elements = soup.find_all("strong")
        episode_labels = filter(_content_starts_with_episode, strong_elements)
        episode_links: list[EpisodeLink] = []

        for episode_label in episode_labels:
            episode_links.append(
                EpisodeLink(
                    url=_episode_pdf_url(episode_label),
                    episode_number=_episode_number(episode_label),
                    title=_episode_title(episode_label),
                )
            )
        print(*episode_links, sep="\n")
        return episode_links

def _episode_title(episode_label: Tag) -> str:
    siblings = filter(lambda sibling: not isinstance(sibling, Tag) or sibling.name != 'a', episode_label.next_siblings)
    title = reduce(lambda acc, element: acc + element.text, siblings, "")
    title = title.replace('[]', '')
    title = title.replace('\xa0', ' ')
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
    match_result = re.search("Episode (\d+)", episode_label.text.strip())
    match match_result:
        case re.Match(): return int(match_result.group(1))
        case unknown: raise UnexpectedPatternException(unknown)

def _content_starts_with_episode(elem: Tag) -> bool:
    """Check for elements with string content starting with 'Episode'"""
    match elem:
        case Tag(contents=contents):
            if not isinstance(contents[0], str):
                return False
            return contents[0].strip().startswith("Episode")
        case None:
            return False
