import os
import time
import mkepub
import shutil
from utils import get_ranobe_info, get_volume_chapters, download_cover, remove_bad_chars, get_chapter_content, get_ranobe_name_from_url
RANOBE_NAME = get_ranobe_name_from_url(input("Ссылка на ранобе: "))
RANOBE_VOLUME = input("Том: ").strip()
print(f"Ранобе {RANOBE_NAME}, том {RANOBE_VOLUME}")
STYLE = """
@page {
    margin-bottom: 5pt;
    margin-top: 5pt
    }

.block_ {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    text-align: center;
    margin: 0 0 10pt;
    padding: 0
    }
.block_1 {
    display: block;
    font-family: serif;
    font-size: 0.83333em;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_2 {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    text-align: center;
    margin: 0 0 10pt;
    padding: 0
    }
.block_3 {
    display: block;
    font-size: 1.29167em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_4 {
    display: block;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_5 {
    display: block;
    font-size: 0.83333em;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_6 {
    display: block;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_7 {
    display: block;
    font-size: 1.29167em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_8 {
    display: block;
    font-size: 1em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_9 {
    display: block;
    font-size: 1em;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_10 {
    display: block;
    font-weight: bold;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.block_11 {
    display: block;
    font-size: 1.29167em;
    font-weight: normal;
    line-height: 1.2;
    margin: 0 0 10pt;
    padding: 0
    }
.calibre {
    color: black;
    display: block;
    font-family: "Arial", sans-serif;
    font-size: 1em;
    padding-left: 0;
    padding-right: 0;
    margin: 0 5pt
    }
.calibre1 {
    display: block;
    height: auto;
    line-height: 1.2;
    width: auto
    }
.calibre2 {
    font-size: 1em;
    line-height: 1.2;
    vertical-align: super
    }
.calibre3 {
    font-size: 0.75em;
    line-height: 1.2;
    vertical-align: super
    }
.calibre4 {
    line-height: 1.2
    }
.calibre5 {
    display: block;
    font-size: 1.29167em;
    line-height: 1.2
    }
.calibre6 {
    line-height: 1.2;
    text-decoration: none
    }
.calibre7 {
    display: block;
    margin-left: 40px
    }
.footnote {
    display: block;
    margin: 1em 0
    }
.footnote1 {
    display: block;
    page-break-after: avoid;
    margin: 1em 0
    }
.noteref {
    text-decoration: none
    }
.text_ {
    font-size: 1.2em;
    line-height: 1.2
    }

"""
URL_TO_CHAPTERS = "https://api.lib.social/api/manga/" + RANOBE_NAME + "/chapters"
URL_TO_RANOBE = "https://api.lib.social/api/manga/" + RANOBE_NAME + ("?fields[]=background&fields[]=eng_name&fields["
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
                                                                     "]=status_id&fields[]=artists&fields[]=format")
print(f"url к информации о ранобе: {URL_TO_RANOBE}\n")
print(f"url к главам: {URL_TO_CHAPTERS}\n")

try:
    shutil.rmtree("cover")
except:
    pass
try:
    shutil.rmtree("images")
except:
    pass
os.makedirs("cover", exist_ok=True)
os.makedirs("images", exist_ok=True)
ranobe_info_dict = get_ranobe_info(URL_TO_RANOBE)
ranobe_title = ranobe_info_dict["title"]
ranobe_description = ranobe_info_dict["description"]
ranobe_cover = ranobe_info_dict["cover_url"]
ranobe_author = ranobe_info_dict["author"]
ranobe_chapters_dict = get_volume_chapters(url=URL_TO_CHAPTERS, volume=RANOBE_VOLUME)

download_cover(ranobe_cover)

book = mkepub.Book(title=ranobe_title, author=ranobe_author, description=ranobe_description)
with open('cover/cover.jpg', 'rb') as file:
    book.set_cover(file.read())
book.set_stylesheet(STYLE)

book.add_page(title=f"{ranobe_title} Том {RANOBE_VOLUME}", content=f"""
<h1>{ranobe_title} Том  {RANOBE_VOLUME}</h1>
<p><i>
{ranobe_description}
</i></p>
""")

for chapter_num, chapter_name in ranobe_chapters_dict.items():
    time.sleep(1)
    url_to_chapter = ("https://api.lib.social/api/manga/" + RANOBE_NAME +
                      "/chapter?number=" + str(chapter_num) + "&volume=" + str(RANOBE_VOLUME))

    chapter_content, images_dict = get_chapter_content(url=url_to_chapter, chapter_num=chapter_num, chapter_name=chapter_name)
    book.add_page(title=f"Глава {chapter_num}. {chapter_name}", content=chapter_content)
    if images_dict:
        for image in images_dict.values():
            with open(image, 'rb') as image_file:
                book.add_image(image[7:], image_file.read())


book_name = remove_bad_chars(ranobe_title) + f" Том {RANOBE_VOLUME}.epub"
try:
    os.remove(book_name)
except:
    pass
book.save(book_name)
print(f'Книга сохранена как {book_name}')