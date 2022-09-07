from dataclasses import dataclass
import re
import requests
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag

HTRCP_PODCAST_PAGE_URL = "https://howtoreadchinesepoetry.com/"


@dataclass
class EpisodeLink:
    url: str
    episode_number: int


def get_episode_links():
    podcast_page_html = requests.get(HTRCP_PODCAST_PAGE_URL).text
    soup = BeautifulSoup(podcast_page_html, "html.parser")
    strong_elements = soup.find_all("strong")
    episode_labels = filter(content_starts_with_episode, strong_elements)
    episode_links: list[EpisodeLink] = []

    for episode_label in episode_labels:
        match find_link_in_siblings(episode_label):
            case str(link):
                episode_number = re.search(
                    "Episode (\d+)", episode_label.text.strip()
                ).group(1)
                episode_links.append(EpisodeLink(link, int(episode_number)))
            case unknown:
                raise Exception("Unknown result ", unknown)
    print(*episode_links, sep="\n")
    return episode_links


def find_link_in_siblings(elem: Tag) -> Tag:
    anchor_element = elem.find_next_sibling("a")
    match anchor_element:
        case None:
            return None
        case Tag(attrs={"href": href, **rest}):
            return href
        case _:
            raise Exception(anchor_element, " was unexpected")


def content_starts_with_episode(elem: Tag) -> bool:
    """Check for elements with string content starting with 'Episode'"""

    match elem:
        case None:
            return False
        case Tag(contents=contents):
            if not isinstance(contents[0], str):
                return False
            return contents[0].strip().startswith("Episode")
        case unexpected_value:
            raise Exception("Didn't expect: ", unexpected_value)
