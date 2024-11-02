import os
import time
import shutil
from utils import get_ranobe_info, get_volume_chapters, download_cover, remove_bad_chars, get_ranobe_name_from_url, Book, style, ChapterContentParser
TIME_TO_SLEEP = 0.5 # задержка между запросами к каждой главе

class RanobeDownloader:
    def __init__(self, ranobe_name, ranobe_volume):
        self.ranobe_name = ranobe_name
        self.ranobe_volume = ranobe_volume
        self.ranobe_info_dict = None
        self.ranobe_chapters_dict = None
        self.book = None

    def get_ranobe_info(self):
        url_to_ranobe = f"https://api.lib.social/api/manga/{self.ranobe_name}"
        self.ranobe_info_dict = get_ranobe_info(url_to_ranobe)
        return self.ranobe_info_dict

    def get_ranobe_chapters(self):
        url_to_chapters = f"https://api.lib.social/api/manga/{self.ranobe_name}/chapters"
        self.ranobe_chapters_dict = get_volume_chapters(url=url_to_chapters, volume=self.ranobe_volume)
        return self.ranobe_chapters_dict

    def download_cover(self):
        download_cover(self.ranobe_info_dict["cover_url"])

    def create_book(self):
        self.book = Book(title=self.ranobe_info_dict["title"],
                         author=self.ranobe_info_dict["author"],
                         description=self.ranobe_info_dict["description"])
        with open('cover/cover.jpg', 'rb') as file:
            self.book.set_cover(file.read())
        self.book.set_stylesheet(style)

    def add_chapters_to_book(self):
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
            time.sleep(TIME_TO_SLEEP) # Чтобы не получить error 429
    def save_book(self):
        book_name = remove_bad_chars(self.ranobe_info_dict["title"]) + f" Том {self.ranobe_volume}.epub"
        if os.path.exists(book_name):
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
    downloader.get_ranobe_info()
    downloader.get_ranobe_chapters()
    downloader.download_cover()
    downloader.create_book()
    downloader.add_chapters_to_book()
    downloader.save_book()  
