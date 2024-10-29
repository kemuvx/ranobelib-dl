import requests
import time
import os
from bs4 import BeautifulSoup
import collections
import datetime
import imghdr
import itertools
import jinja2
import pathlib
import tempfile
import uuid
import zipfile

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'
}
style = """
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


def get_ranobe_name_from_url(url: str) -> str:
    url = url.strip()
    if "https://" in url and "/read/" in url:
        url = url.split("//")[1].split("/")[2]
    elif "https://" in url:
        url = url.split("//")[1].split("/")[3].split("?")[0]
    else:
        raise Exception("Invalid URL", url)
    return url


def get_ranobe_info(url: str) -> dict:
    """Парсит cover_url, author, title, description"""
    response = requests.get(url, headers=headers)
    data = response.json()['data']
    return {
        'cover_url': data.get('cover', {}).get('default', ''),
        'author': data.get('authors', [{}])[0].get('rus_name') or data.get('authors', [{}])[0].get('name','Unknown Author'),
        'title': data.get('rus_name', data.get('name', '')),
        'description': data.get('summary', '')
    }

def get_volume_chapters(url: str, volume: str) -> dict:
    """Парсит номер и название глав"""
    response = requests.get(url, headers=headers)
    data = response.json()['data']
    chapters_dict = {}
    for chapter in data:
        if chapter['volume'] == volume:
            chapter_num = chapter['number']
            chapter_name = chapter['name'] if chapter['name'].strip() != "" else f"Глава {chapter_num}"
            chapters_dict[chapter_num] = chapter_name
    return chapters_dict


def download_cover(url: str) -> None:
    cover_data = requests.get(url, headers=headers).content
    with open('cover/cover.jpg', 'wb') as handler:
        handler.write(cover_data)


def remove_bad_chars(text: str) -> str:
    return ''.join(c for c in text if c not in '"?<>|\/:–')


def get_chapter_content(url: str, chapter_num: str, chapter_name: str) -> tuple[str, dict]:
    response = requests.get(url, headers=headers)
    json_response = response.json()
    try:
        json_response['data']['content']['type'] == "doc"  # если ошибка значит легаси
        is_legacy = False
        print(f"\nГлава {chapter_num}: {chapter_name}: {url}  \nТип главы: не легаси")
    except TypeError:
        is_legacy = True
        print(f"\nГлава {chapter_num}: {chapter_name}: {url}  \nТип главы: легаси")
    os.makedirs("images", exist_ok=True)
    images_dict = {}
    image_counter = 1
    if is_legacy:
        content_soup = BeautifulSoup(json_response['data']['content'], 'lxml')
        bad_sites = ["novel.tl", "ruranobe.ru", "rulate.ru"]

        for img in content_soup.find_all('img'):
            img_url = img['src']
            if not any(x in img_url for x in bad_sites):
                img_url = "https://ranobelib.me" + img_url
            if img_url.count("ranobelib.me") > 1:
                img_url = img_url[20:]
            print(f"Арт {chapter_num}-{image_counter}: " + img_url)
            with open(f'images/{chapter_num}-{image_counter}.jpg', 'wb') as f:
                f.write(requests.get(img_url, headers=headers).content)
            del img['loading']
            img['src'] = f'images/{chapter_num}-{image_counter}.jpg'
            images_dict[str(image_counter)] = img['src']
            image_counter += 1
        for p in content_soup.find_all('p'):
            del p['data-paragraph-index']
        content = ((f"<h1>Глава {str(chapter_num)}. {str(chapter_name)}</h1>" + str(content_soup))
                   .replace('<html>', "")
                   .replace("</html>", "")
                   .replace("<body>", "")
                   .replace("</body>", ""))


    else:  # не легаси
        attachments = json_response['data']['attachments']
        chapter_content = json_response['data']['content']['content']
        content = f"<h1>Глава {chapter_num}. {chapter_name}</h1>\n"
        for element in chapter_content:
            if element['type'] == 'image':
                images = element['attrs']['images']
                for image in images:
                    image_id = image['image']
                    for attachment in attachments:
                        if attachment['name'] == image_id:
                            img_url = ' https://ranobelib.me' + attachment['url']
                            print(f"Арт {chapter_num}-{image_counter}: " + img_url)
                            img_content = requests.get(img_url, headers=headers).content
                            with open(f'images/{chapter_num}-{image_counter}.png', 'wb') as handler:
                                handler.write(img_content)
                            content += f'<p><img src="images/{chapter_num}-{image_counter}.png"></img></p>\n'
                            images_dict[str(image_counter)] = f"images/{chapter_num}-{image_counter}.png"
                            image_counter += 1
            elif element['type'] == "paragraph":
                if "content" in element:
                    for line_of_element in element['content']:
                        if line_of_element['type'] == 'text':
                            if "marks" and "italic" in str(line_of_element):
                                content += f"<p><i>{line_of_element['text']}</i></p>\n"
                            else:
                                content += f"<p>{line_of_element['text']}</p>\n"
                        elif line_of_element['type'] == 'hardBreak':
                            content += "<br>\n"
                        else:
                            print(line_of_element['text'])
                            raise Exception(f"не текст {line_of_element['type']}, {line_of_element}")

                    content += f"<p></p>\n"
            elif element['type'] == "heading":
                if "content" in element:
                    for line_of_element in element['content']:
                        if line_of_element['type'] == 'text':
                            content += f"<h3>{line_of_element['text']}</h3>\n"
                        else:
                            raise Exception(f"не текст {element}, {line_of_element}")
            elif element['type'] == "horizontalRule" and "content" not in element:
                pass
            elif element['type'] == "bulletList":
                bullet_list_content = element['content']
                for element_of_list in bullet_list_content:
                    if element_of_list['type'] == 'listItem':
                        for content_of_list_item in element_of_list['content']:
                            if content_of_list_item['type'] == 'paragraph':
                                content_of_content = content_of_list_item['content'][0]
                                if content_of_content['type'] == 'text':
                                    content += f"<p><li>{content_of_content['text']}</li></p>\n"
                                else:
                                    raise Exception(element)
                            else:
                                raise Exception(element)
                    else:
                        raise Exception("not listitem?", element_of_list, "\n", element)
            elif element['type'] == "blockquote":
                if "content" in element:
                    for line_of_element in element['content']:
                        if line_of_element['type'] == 'paragraph':
                            content += f"<blockquote><p>{line_of_element['content'][0]['text']}</p></blockquote>\n"
                        else:
                            raise Exception(f"не текст {element}, {line_of_element}")
                else:
                    raise Exception(f"не текст {element}, {line_of_element}")
            else:
                raise Exception(f"Новый тип {element['type']}, {element}")
    return content, images_dict


###############################################################################
#  Дальше пофикшенный код mkepub
###############################################################################
def mediatype(name):
    ext = name.split('.')[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'svg','webp'):
        raise ValueError('Image format "{}" is not supported.'.format(ext))
    if ext == 'jpg':
        ext = 'jpeg'
    return 'image/' + ext


def fonttype(name):
    ext = name.split('.')[-1].lower()
    mimetypes = {
        'otf': 'application/font-sfnt',
        'ttf': 'application/font-sfnt',
        'woff': 'font/woff',
        'woff2': 'font/woff2',
    }
    if ext not in mimetypes.keys():
        raise ValueError('Font format "{}" is not supported.'.format(ext))
    return mimetypes[ext]


env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
env.filters['mediatype'] = mediatype
env.filters['fonttype'] = fonttype
###############################################################################

Page = collections.namedtuple('Page', 'page_id title children')
Image = collections.namedtuple('Image', 'image_id name')


class Book:
    """EPUB book."""

    def __init__(self, title, **metadata):
        """"Create new book."""
        self.title = title
        self.metadata = metadata

        self.tempdir = tempfile.TemporaryDirectory()
        self.root = []
        self.fonts = []
        self.images = []
        self.uuid = uuid.uuid4()
        self._page_id = map('{:04}'.format, itertools.count(1))
        self._image_id = map('{:03}'.format, itertools.count(1))

        self.path = pathlib.Path(self.tempdir.name).resolve()
        for dirname in [
                'EPUB', 'META-INF', 'EPUB/images', 'EPUB/css', 'EPUB/covers']:
            (self.path / dirname).mkdir()

        self.set_stylesheet('')
        self._cover = None

    ###########################################################################
    # Public Methods
    ###########################################################################

    def add_page(self, title, content, parent=None):
        """
        Add a new page.

        The page will be added as a subpage of the parent. If no parent is
        provided, the page will be added to the root of the book.
        """
        page = Page(next(self._page_id), title, [])
        self.root.append(page) if not parent else parent.children.append(page)
        self._write_page(page, content)
        return page

    def add_image(self, name, data):
        """Add image file."""
        self.images.append(Image(next(self._image_id), name))
        self._add_file(pathlib.Path('images') / name, data)

    def add_font(self, name, data):
        """Add font file."""
        self.fonts.append(name)
        self._add_file(pathlib.Path('fonts') / name, data)

    def set_cover(self, data):
        """Set the cover image to the given data."""
        self._cover = 'cover.' + imghdr.what(None, h=data)
        self._add_file(pathlib.Path('covers') / self._cover, data)
        self._write('cover.xhtml', 'EPUB/cover.xhtml', cover=self._cover)

    def set_stylesheet(self, data):
        """Set the stylesheet to the given css data."""
        self._add_file(
            pathlib.Path('css') / 'stylesheet.css', data.encode('utf-8'))

    def save(self, filename):
        """Save book to a file."""
        if pathlib.Path(filename).exists():
            raise FileExistsError
        self._write_spine()
        self._write('container.xml', 'META-INF/container.xml')
        self._write_toc()
        with open(str(self.path / 'mimetype'), 'w') as file:
            file.write('application/epub+zip')
        with zipfile.ZipFile(filename, 'w') as archive:
            archive.write(
                str(self.path / 'mimetype'), 'mimetype',
                compress_type=zipfile.ZIP_STORED)
            for file in self.path.rglob('*.*'):
                archive.write(
                    str(file), str(file.relative_to(self.path)),
                    compress_type=zipfile.ZIP_DEFLATED)

    ###########################################################################
    # Private Methods
    ###########################################################################

    def _add_file(self, name, data):
        """Add a file."""
        filepath = self.path / 'EPUB' / name
        if not filepath.parent.exists():
            filepath.parent.mkdir()

        with open(str(filepath), 'wb') as file:
            file.write(data)

    def _write(self, template, path, **data):
        with open(str(self.path / path), 'w', encoding="utf-8") as file:
            file.write(env.get_template(template).render(**data))

    def _write_page(self, page, content):
        """Write the contents of the page into an html file."""
        self._write(
            'page.xhtml', 'EPUB/page{}.xhtml'.format(page.page_id),
            title=page.title, body=content)

    def _write_spine(self):
        self._write(
            'package.opf', 'EPUB/package.opf',
            title=self.title,
            date=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            pages=list(self._flatten(self.root)), images=self.images,
            fonts=self.fonts, uuid=self.uuid, cover=self._cover,
            **self.metadata)

    def _write_toc(self):
        self._write(
            'toc.xhtml', 'EPUB/toc.xhtml', pages=self.root, title=self.title)
        self._write(
            'toc.ncx', 'EPUB/toc.ncx',
            pages=self.root, title=self.title, uuid=self.uuid)

    def _flatten(self, tree):
        for item in tree:
            yield item
            yield from self._flatten(item.children)