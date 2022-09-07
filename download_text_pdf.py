from dataclasses import dataclass
from numbers import Number
import requests
import os
from PyPDF2 import PdfMerger, PdfReader

from get_pdf_links import EpisodeLink, get_episode_links

DOWNLOAD_FOLDER = 'downloads'

def main():
    episode_links = get_episode_links()

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    for episode_link in episode_links:
        download_episode_pdf(episode_link)

    episode_pdfs = map(read_pdf_meta_data, episode_links)
    merge_pdfs(episode_pdfs)

@dataclass
class EpisodePdf:
    episode_number: int
    num_pages: int

def merge_pdfs(episode_pdfs: list[EpisodePdf]):
    pdfMerger = PdfMerger()
    current_page = 0
    for episode_pdf in episode_pdfs:
        pdfMerger.append(_out_pdf_path(episode_pdf.episode_number))
        pdfMerger.add_outline_item(pagenum=current_page, title=f'Episode {episode_pdf.episode_number}')
        current_page += episode_pdf.num_pages
    pdfMerger.write("merged.pdf")
    

def read_pdf_meta_data(episode_link: EpisodeLink) -> list[EpisodePdf]:
    pdfReader = PdfReader(_download_pdf_path(episode_link.episode_number))
    return EpisodePdf(int(episode_link.episode_number), len(pdfReader.pages))
    

def download_episode_pdf(episode_link: EpisodeLink):
    if os.path.exists(_download_pdf_path(episode_link.episode_number)):
        response_size = requests.head(episode_link.url).headers.get('content-length', -1)
        response_size = int(response_size)
        if response_size > 0 and response_size == os.path.getsize(_download_pdf_path(episode_link.episode_number)):
            print(f'Skipping download of episode {episode_link.episode_number} PDF as local file exists with same size as remote file ({response_size} bytes)')
            return
    with open(_download_pdf_path(episode_link.episode_number), 'wb') as f:
        f.write(requests.get(episode_link.url).content)

def _download_pdf_path(episode_number: Number):
     return f'{DOWNLOAD_FOLDER}{os.sep}{episode_number}.pdf'

def _out_pdf_path(episode_number: Number):
     return f'out{os.sep}{episode_number}.pdf'




if __name__ == "__main__":
    main()
