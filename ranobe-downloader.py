import os
import time
import shutil
from utils import get_ranobe_info, get_volume_chapters, download_cover, remove_bad_chars, get_chapter_content, get_ranobe_name_from_url, Book, style


ranobe_name = get_ranobe_name_from_url(input("Ссылка на ранобе: "))
ranobe_volume = input("Том: ").strip()
print(f"Ранобе id {ranobe_name}, том {ranobe_volume}")

url_to_chapters = "https://api.lib.social/api/manga/" + ranobe_name + "/chapters"
url_to_ranobe = "https://api.lib.social/api/manga/" + ranobe_name + ('''?fields[]=background&fields[]=eng_name&fields["
                                                                     "]=otherNames&fields[]=summary&fields["
                                                                     "]=releaseDate&fields[]=type_id&fields["
                                                                     "]=caution&fields[]=views&fields["
                                                                     "]=close_view&fields[]=rate_avg&fields["
                                                                     "]=rate&fields[]=genres&fields[]=tags&fields["
                                                                     "]=teams&fields[]=franchise&fields["
                                                                     "]=authors&fields[]=publisher&fields["
                                                                     "]=userRating&fields[]=moderated&fields["
                                                                     "]=metadata&fields[]=metadata.count&fields["
                                                                     "]=metadata.close_comments&fields["
                                                                     "]=manga_status_id&fields[]=chap_count&fields["
                                                                     "]=status_id&fields[]=artists&fields[]=format''')

print(f"url к информации о ранобе: {url_to_ranobe}")
print(f"url к главам: {url_to_chapters}\n")

shutil.rmtree("cover", ignore_errors=True)
shutil.rmtree("images", ignore_errors=True)
os.makedirs("cover", exist_ok=True)
os.makedirs("images", exist_ok=True)

ranobe_info_dict = get_ranobe_info(url_to_ranobe)
ranobe_title = ranobe_info_dict["title"]
ranobe_description = ranobe_info_dict["description"]
ranobe_cover = ranobe_info_dict["cover_url"]
ranobe_author = ranobe_info_dict["author"]

ranobe_chapters_dict = get_volume_chapters(url=url_to_chapters, volume=ranobe_volume)
download_cover(ranobe_cover)

book = Book(title=ranobe_title, author=ranobe_author, description=ranobe_description)
with open('cover/cover.jpg', 'rb') as file:
    book.set_cover(file.read())
book.set_stylesheet(style)

book.add_page(title=f"{ranobe_title} Том {ranobe_volume}", content=f"""
<h1>{ranobe_title} Том  {ranobe_volume}</h1>
<p><i>
{ranobe_description}
</i></p>
""")

for chapter_num, chapter_name in ranobe_chapters_dict.items():
    time.sleep(1)
    url_to_chapter = ("https://api.lib.social/api/manga/" + ranobe_name +
                      "/chapter?number=" + str(chapter_num) + "&volume=" + str(ranobe_volume))

    chapter_content, images_dict = get_chapter_content(url=url_to_chapter, chapter_num=chapter_num, chapter_name=chapter_name)
    book.add_page(title=f"Глава {chapter_num}. {chapter_name}", content=chapter_content)
    if images_dict:
        for image in images_dict.values():
            with open(image, 'rb') as image_file:
                book.add_image(image[7:], image_file.read())


book_name = remove_bad_chars(ranobe_title) + f" Том {ranobe_volume}.epub"
if os.path.exists(book_name):
    os.remove(book_name)
book.save(book_name)

print(f'Книга сохранена как {book_name}')