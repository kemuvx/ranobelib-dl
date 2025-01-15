import requests
import os
from bs4 import BeautifulSoup
import collections
import datetime
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

def remove_bad_chars(text: str) -> str:
    return ''.join(c for c in text if c not in r'"?<>|\/:–')



class ChapterContentParser:
    def __init__(self, url: str, chapter_num: str, chapter_name: str):
        self.url = url
        self.chapter_num = chapter_num
        self.chapter_name = chapter_name
        self.headers = headers
        self.images_dict = {}
        os.makedirs("images", exist_ok=True)

    def fetch_content(self) -> tuple[str, dict]:
        """Парсит и анализирует главу"""
        response = requests.get(self.url, headers=self.headers)
        response.raise_for_status()
        json_response = response.json()


        try: # Проверка легаси глава или нет
            json_response['data']['content']['type'] == "doc"  # если выдает ошибку значит легаси
            is_legacy = False
        except TypeError:
            is_legacy = True
        print(f"\nГлава {self.chapter_num}: {self.chapter_name}: {self.url}")
        

        if is_legacy:
            content = self._parse_legacy_content(json_response['data']['content'])
        else:
            content = self._parse_modern_content(json_response['data'])
        

        content = f"<h1>Глава {self.chapter_num}. {self.chapter_name}</h1>\n{content}"
        return content, self.images_dict

    def _parse_legacy_content(self, content_html: str) -> str:
        """Парсит легаси главу (html контент)"""
        content_soup = BeautifulSoup(content_html, 'lxml')
        image_counter = 1
        bad_sites = ["novel.tl", "ruranobe.ru", "rulate.ru"]

        for img in content_soup.find_all('img'):
            img_url = img['src']
            if not any(x in img_url for x in bad_sites):
                img_url = "https://ranobelib.me" + img_url
            if img_url.count("ranobelib.me") > 1:
                img_url = img_url[20:]
                print(f"Арт {self.chapter_num}-{image_counter}: " + img_url)
                
            img_path = os.path.join("images", f"{self.chapter_num}-{image_counter}.jpg")
            self._save_image(img_url, img_path)
            self.images_dict[str(image_counter)] = img_path
            img['src'] = img_path
            image_counter += 1

        
        content = str(content_soup).replace('<html>', "").replace("</html>", "").replace("<body>", "").replace("</body>", "")
        return content

    def _parse_modern_content(self, data: dict) -> str:
        """Парсит модерн главу (json контент)"""
        content = ""
        image_counter = 1
        attachments = {att['name']: f"https://ranobelib.me{att['url']}" for att in data.get('attachments', [])}
        
        for element in data['content']['content']:
            if element['type'] == 'image':
                content, image_counter = self._process_images(element, attachments, image_counter, content)
            elif element['type'] == "paragraph":
                content += self._process_paragraph(element)
            elif element['type'] == "heading":
                content += self._process_heading(element)
            elif element['type'] == "bulletList":
                content += self._process_bullet_list(element)
            elif element['type'] == "blockquote":
                content += self._process_blockquote(element)
            elif element['type'] == "horizontalRule":
                content += self._process_horizontal_rule(element)
            else:
                raise Exception("Новый тип элемента, надо обработать", element)
        return content
    def _save_image(self, img_url: str, img_path: str):
        """Скачивает и сохраняет картинку."""
        img_content = requests.get(img_url, headers=self.headers).content
        with open(img_path, 'wb') as f:
            f.write(img_content)    

    def _process_images(self, element, attachments, image_counter, content):
        for image in element['attrs']['images']:
            img_url = attachments.get(image['image'])
            if img_url:
                img_path = os.path.join("images", f"{self.chapter_num}-{image_counter}.jpg")
                self._save_image(img_url, img_path)
                content += f'<p><img src="{img_path}"></img></p>\n'
                self.images_dict[str(image_counter)] = img_path
                image_counter += 1
        return content, image_counter

    def _process_paragraph(self, element):
        paragraph_content = ""
        for line in element.get("content", []):
            if line['type'] == 'text':
                text = f"<i>{line['text']}</i>" if any(mark['type'] == "italic" for mark in line.get('marks', [])) else line['text']
                paragraph_content += f"<p>{text}</p>\n"
            elif line['type'] == 'hardBreak':
                paragraph_content += "<br>\n"
            else:
                raise Exception("Другой тип элемента, надо обработать", line + " in" + element)
        return paragraph_content

    def _process_heading(self, element):
        heading_level = element.get("attrs", {}).get("level", 3)
        heading_content = ""

        for line in element.get("content", []):
            if line['type'] == 'text':
                text = line['text']
                
                if any(mark['type'] == "bold" for mark in line.get('marks', [])):
                    text = f"<b>{text}</b>"

                heading_content += text
            else:
                raise Exception("Другой тип элемента, надо обработать", line + " in" + element)

        return f"<h{heading_level}>{heading_content}</h{heading_level}>\n"

    def _process_bullet_list(self, element):
        list_content = ""
        for item in element.get("content", []):
            if item['type'] == 'listItem':
                for sub_item in item.get("content", []):
                    if sub_item['type'] == 'paragraph':
                        paragraph_text = ""
                        for content_item in sub_item.get("content", []):
                            if content_item['type'] == 'text':
                                paragraph_text += content_item['text']
                            else:
                                raise Exception("Другой тип элемента, надо обработать", content_item + " in" + sub_item)
                        list_content += f"<p><li>{paragraph_text}</li></p>\n"
                    else:
                        raise Exception("Другой тип элемента, надо обработать", sub_item + " in" + item)
            else:
                raise Exception("Другой тип элемента, надо обработать", item)
        return list_content

    def _process_blockquote(self, element):
        quote_content = ""
        for item in element.get("content", []):
            if item['type'] == 'paragraph':
                paragraph_text = ""
                for sub_item in item.get("content", []):
                    if sub_item['type'] == 'text':
                        paragraph_text += sub_item['text']
                    else:
                        raise Exception("Другой тип элемента, надо обработать", sub_item + " in" + item)
                quote_content += f"<blockquote><p>{paragraph_text}</p></blockquote>\n"
            else:
                raise Exception("Другой тип элемента, надо обработать", item)
        return quote_content
    def _process_horizontal_rule(self, element):
        return "\n"




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
        magic_numbers = {
            b'\xFF\xD8\xFF': 'jpg',
            b'\x89PNG\r\n': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'RIFF': 'webp'
        }
        
        for magic, ext in magic_numbers.items():
            if data.startswith(magic):
                self._cover = f'cover.{ext}'
                self._add_file(pathlib.Path('covers') / self._cover, data)
                self._write('cover.xhtml', 'EPUB/cover.xhtml', cover=self._cover)
                return
                
        raise ValueError('Unsupported image format')

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