import os
import time
import shutil
import requests
from utils import remove_bad_chars, get_ranobe_name_from_url, headers, style, Book,  ChapterContentParser

TIME_TO_SLEEP = 0.5  # задержка между запросами к каждой главе

class RanobeDownloader:
    def __init__(self, ranobe_name, ranobe_volume):
        self.ranobe_name = ranobe_name
        self.ranobe_volume = ranobe_volume
        self.ranobe_info_dict = None
        self.ranobe_chapters_dict = None
        self.book = None

    def fetch_ranobe_info(self):
        url_to_ranobe = f"https://api.lib.social/api/manga/{self.ranobe_name}?fields[]=background&fields[]=eng_name&fields[]=otherNames&fields[]=summary&fields[]=releaseDate&fields[]=type_id&fields[]=caution&fields[]=views&fields[]=close_view&fields[]=rate_avg&fields[]=rate&fields[]=genres&fields[]=tags&fields[]=teams&fields[]=user&fields[]=franchise&fields[]=authors&fields[]=publisher&fields[]=userRating&fields[]=moderated&fields[]=metadata&fields[]=metadata.count&fields[]=metadata.close_comments&fields[]=manga_status_id&fields[]=chap_count&fields[]=status_id&fields[]=artists&fields[]=format"
        response = requests.get(url_to_ranobe, headers=headers)
        data = response.json()['data']
        self.ranobe_info_dict = {
            'cover_url': data.get('cover', {}).get('default', ''),
            'author': data.get('authors', [{}])[0].get('rus_name') or data.get('authors', [{}])[0].get('name', 'Unknown Author'),
            'title': data.get('rus_name', data.get('name', '')),
            'description': data.get('summary', '')
        }


    def fetch_ranobe_chapters(self):
        url_to_chapters = f"https://api.lib.social/api/manga/{self.ranobe_name}/chapters"
        response = requests.get(url_to_chapters, headers=headers)
        data = response.json()['data']
        self.ranobe_chapters_dict =  {
            chapter['number']: (chapter['name'] if chapter['name'].strip() else f"Глава {chapter['number']}")
            for chapter in data if chapter.get('volume') == self.ranobe_volume
        }


    def download_cover_image(self):
        cover_data = requests.get(self.ranobe_info_dict["cover_url"], headers=headers).content
        with open('cover/cover.jpg', 'wb') as handler:
            handler.write(cover_data)


    def fetch_cover_image(self):
        url_to_covers = f"https://api2.mangalib.me/api/manga/{self.ranobe_name}/covers"
        json_data = requests.get(url_to_covers).json()
        covers = {item["info"]: item["cover"]["orig"] for item in json_data["data"] if item["info"] and "orig" in item["cover"]}
        if str(self.ranobe_volume) in covers:
            self.ranobe_info_dict["cover_url"] = covers[str(self.ranobe_volume)]


    def create_book_object(self):
        self.book = Book(title=self.ranobe_info_dict["title"],
                         author=self.ranobe_info_dict["author"],
                         description=self.ranobe_info_dict["description"])
        with open('cover/cover.jpg', 'rb') as file:
            self.book.set_cover(file.read())
        self.book.set_stylesheet(style)


    def add_chapters_to_book_object(self):
        for chapter_num, chapter_name in self.ranobe_chapters_dict.items():
            url_to_chapter = (f"https://api.lib.social/api/manga/{self.ranobe_name}/chapter?number={chapter_num}"
                              f"&volume={self.ranobe_volume}")
            parser = ChapterContentParser(url=url_to_chapter, chapter_num=chapter_num, chapter_name=chapter_name)
            chapter_content, images_dict = parser.fetch_content()
            self.book.add_page(title=f"Глава {chapter_num}. {chapter_name}", content=chapter_content)
            if images_dict:
                for image in images_dict.values():
                    with open(image, 'rb') as image_file:
                        self.book.add_image(image[7:], image_file.read())
            time.sleep(TIME_TO_SLEEP)  # Чтобы не получить error 429


    def save_book_to_file(self):
        book_name = remove_bad_chars(self.ranobe_info_dict["title"]) + f" Том {self.ranobe_volume}.epub"
        if os.path.exists(book_name):
            print(f'\nФайл {book_name} уже существует. Перезаписываю...')
            os.remove(book_name)
        self.book.save(book_name)
        print(f'\nКнига сохранена как {book_name}')



if __name__ == "__main__":
    shutil.rmtree("cover", ignore_errors=True)
    shutil.rmtree("images", ignore_errors=True)
    os.makedirs("cover", exist_ok=True)
    os.makedirs("images", exist_ok=True)

    ranobe_name = get_ranobe_name_from_url(input("Ссылка на ранобе: "))
    ranobe_volume = input("Том: ").strip()
    print(f"Ранобе id {ranobe_name}, том {ranobe_volume}")

    downloader = RanobeDownloader(ranobe_name, ranobe_volume)
    downloader.fetch_ranobe_info()
    downloader.fetch_ranobe_chapters()
    downloader.fetch_cover_image()
    downloader.download_cover_image()
    downloader.create_book_object()
    downloader.add_chapters_to_book_object()
    downloader.save_book_to_file()
