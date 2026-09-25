import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from utils import (
    ImageManager,
    BadLinesFilter,
    detect_image_ext,
    Book,
    ChapterContentParser,
)


class TestBadLinesFilter(unittest.TestCase):
    def setUp(self):
        self.filter = BadLinesFilter()

    def test_positive_ad_patterns(self):
        """Verify that genuine translator ads, plugs, and links are detected."""
        ad_lines = [
            "Над переводом работал @ivan_trans. Наш телеграм: https://t.me/ranobe",
            "Не забудьте вступить в группу вк https://vk.com/club123456",
            "Не забудьте подписаться на наш телеграм канал @novels!",
            "Переводчик: Alex, Редактор: Bob",
            "Вычитка: Mary",
            "https://t.me/ranobelib",
            "t.me/cool_ranobe",
            "@ranobe_translations",
            "Поддержать переводчика: boosty.to/ranobe",
            "Переведено специально для ranobelib.me",
            "Вступайте в нашу группу вк!",
            "Приятного чтения! Наш тг-канал: @novel_tg",
            "— Наш телеграм: https://t.me/ranobe_channel",
            "Донат на кофе переводчику: номер карты 1234 5678",
            "Платные главы на boosty.to/novel",
            "Источник: https://ranobelib.me/some-novel",
            "Работала над переводом (команда RanobeList)",
        ]
        for line in ad_lines:
            is_ad, reason = self.filter.is_ad_line(line)
            self.assertTrue(is_ad, f"Expected '{line}' to be identified as an ad, but got False")

    def test_negative_literature_and_story_patterns(self):
        """Verify that genuine novel text (mangakas, editors, translators, dialogue) is NOT falsely flagged."""
        story_lines = [
            "— Я работал над переводом этой главы всю неделю, — устало вздохнул Акуто.",
            "Главный герой устроился в издательство, где работал над переводом классики.",
            "Редактор манги взглянул на эскизы и покачал головой: сюжет нужно переписать.",
            "Учитель напомнил: «Не забудьте вступить в группу подготовки к экзаменам».",
            "Она вступила в литературный кружок в начале семестра.",
            "— Подписывайтесь на мой канал! — весело закричала стримерша в игре.",
            "Переводчик в древней библиотеке расшифровывал свитки древней магии.",
            "Редактор издательства посмотрел на новую рукопись молодого мангаки.",
            "В этот день гильдмастер объявил, что пора вступить в группу искателей приключений.",
            "Герой получил в награду 500 золотых монет и отправился в таверну.",
        ]
        for line in story_lines:
            is_ad, reason = self.filter.is_ad_line(line)
            self.assertFalse(is_ad, f"False positive detected: '{line}' flagged as ad ({reason})")

    def test_filter_chapter_html_pure_and_mixed(self):
        """Test HTML cleaning on pure ad tags and mixed paragraphs with <br>."""
        html = """
        <p>Герой открыл глаза и посмотрел на редактора журнала.</p>
        <p>— Я работал над переводом этой книги всю прошлую неделю, — сказал он.</p>
        <p>Над переводом работал @alex. Наш тг: https://t.me/ranobe</p>
        <p>История продолжается дальше.<br>Не забудьте вступить в группу вк vk.com/club123456</p>
        <p><img src="images/art1.jpg"/></p>
        <p>Переводчик: John, Редактор: Mary</p>
        """
        cleaned = self.filter.filter_chapter_html(html, "1")

        # Story lines must remain
        self.assertIn("Герой открыл глаза и посмотрел на редактора журнала.", cleaned)
        self.assertIn("— Я работал над переводом этой книги всю прошлую неделю, — сказал он.", cleaned)
        self.assertIn("История продолжается дальше.", cleaned)
        self.assertIn('<img src="images/art1.jpg"/>', cleaned)

        # Ad lines must be deleted
        self.assertNotIn("Над переводом работал @alex", cleaned)
        self.assertNotIn("https://t.me/ranobe", cleaned)
        self.assertNotIn("vk.com/club123456", cleaned)
        self.assertNotIn("Переводчик: John", cleaned)


class TestImageManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_name = os.path.join(self.test_dir, "test_novel") + "/"
        os.makedirs(f"{self.folder_name}images", exist_ok=True)
        self.book = Book(title="Test Novel", author="Test Author")
        self.image_manager = ImageManager(
            folder_name=self.folder_name,
            book=self.book,
            headers={}
        )
        # 1x1 valid PNG image bytes
        self.sample_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('requests.get')
    def test_image_deduplication_same_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = self.sample_png
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # First encounter
        epub_path1, disk_path1, is_dup1 = self.image_manager.process_image(
            img_url="https://example.com/art1.png",
            img_key="1-1",
            chapter_num="1",
            image_counter=1
        )
        self.assertFalse(is_dup1)
        self.assertTrue(os.path.exists(disk_path1))
        self.assertEqual(mock_get.call_count, 1)

        # Second encounter with the EXACT same URL (URL cache hit)
        epub_path2, disk_path2, is_dup2 = self.image_manager.process_image(
            img_url="https://example.com/art1.png",
            img_key="2-1",
            chapter_num="2",
            image_counter=1
        )
        self.assertTrue(is_dup2)
        # Should reuse identical epub path and disk path
        self.assertEqual(epub_path1, epub_path2)
        self.assertEqual(disk_path1, disk_path2)
        # Requests should NOT be called again
        self.assertEqual(mock_get.call_count, 1)

    @patch('requests.get')
    def test_image_deduplication_different_url_same_content(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = self.sample_png
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Image from URL A
        epub_path1, disk_path1, is_dup1 = self.image_manager.process_image(
            img_url="https://cdn1.example.com/chapter1_art.png",
            img_key="1-1",
            chapter_num="1",
            image_counter=1
        )
        self.assertFalse(is_dup1)

        # Identical image from URL B (content hash match)
        epub_path2, disk_path2, is_dup2 = self.image_manager.process_image(
            img_url="https://cdn2.example.com/chapter5_repeat_art.png",
            img_key="5-1",
            chapter_num="5",
            image_counter=1
        )
        self.assertTrue(is_dup2)
        # Must reuse the first canonical image
        self.assertEqual(epub_path1, epub_path2)
        self.assertEqual(disk_path1, disk_path2)

        # Check that Book images manifest only contains 1 image
        self.assertEqual(len(self.book.images), 1)

    def test_book_cover_deduplication(self):
        """Ensure volume cover pages reuse identical cover image files in whole-book mode."""
        vol1_page = self.book.add_cover_page("Том 1", self.sample_png)
        vol2_page = self.book.add_cover_page("Том 2", self.sample_png)

        # Both pages must exist
        self.assertIsNotNone(vol1_page)
        self.assertIsNotNone(vol2_page)

        # But only 1 image file must be registered in the EPUB manifest
        self.assertEqual(len(self.book.images), 1)


class TestChapterContentParserIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_name = os.path.join(self.test_dir, "test_novel") + "/"
        os.makedirs(f"{self.folder_name}images", exist_ok=True)
        self.book = Book(title="Test Novel", author="Test Author")
        self.image_manager = ImageManager(
            folder_name=self.folder_name,
            book=self.book,
            headers={}
        )
        self.sample_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('requests.get')
    def test_legacy_chapter_parsing_with_ad_filtering_and_images(self, mock_get):
        # Mock chapter API response
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {
            'data': {
                'content': (
                    '<p>Начало интересной главы.</p>'
                    '<p>Над переводом работал @alex_translator. Канал: t.me/ranobeteam</p>'
                    '<p>Диалог: — Я работал над переводом древнего свитка, — сказал маг.</p>'
                    '<p><img src="/uploads/chapter_art.png"/></p>'
                    '<p>Конец главы.<br>Не забудьте вступить в группу вк vk.com/club999</p>'
                )
            }
        }
        # Image download response
        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.content = self.sample_png
        img_resp.raise_for_status.return_value = None

        # Route requests.get based on URL
        def side_effect(url, headers=None):
            if "/api/manga/" in url:
                return api_resp
            return img_resp

        mock_get.side_effect = side_effect

        parser = ChapterContentParser(
            url="https://api.cdnlibs.org/api/manga/test/chapter?number=1&volume=1",
            chapter_num="1",
            chapter_name="Начало пути",
            folder_name=self.folder_name,
            image_prefix="v1-",
            image_manager=self.image_manager,
            filter_ads=True,
        )
        content, images_dict = parser.fetch_content()

        # Check content
        self.assertIn("<h1>Глава 1. Начало пути</h1>", content)
        self.assertIn("Начало интересной главы.", content)
        self.assertIn("— Я работал над переводом древнего свитка, — сказал маг.", content)
        self.assertIn("Конец главы.", content)
        self.assertIn('<img src="images/v1-1-1.png"/>', content)

        # Ads must be removed
        self.assertNotIn("Над переводом работал @alex_translator", content)
        self.assertNotIn("t.me/ranobeteam", content)
        self.assertNotIn("vk.com/club999", content)

        # Image should be saved to disk and registered
        self.assertEqual(len(images_dict), 1)
        self.assertEqual(len(self.book.images), 1)

    @patch('requests.get')
    def test_modern_chapter_parsing_with_ad_filtering_and_images(self, mock_get):
        # Mock modern chapter API response (ProseMirror JSON)
        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.raise_for_status.return_value = None
        api_resp.json.return_value = {
            'data': {
                'attachments': [
                    {'name': 'img1', 'url': '/images/novel_art.png'}
                ],
                'content': {
                    'type': 'doc',
                    'content': [
                        {
                            'type': 'paragraph',
                            'content': [{'type': 'text', 'text': 'Первый абзац современного формата.'}]
                        },
                        {
                            'type': 'paragraph',
                            'content': [{'type': 'text', 'text': 'Переводчик: John, Редактор: Mary'}]
                        },
                        {
                            'type': 'image',
                            'attrs': {'images': [{'image': 'img1'}]}
                        },
                        {
                            'type': 'paragraph',
                            'content': [
                                {'type': 'text', 'text': 'Второй абзац текста.'},
                                {'type': 'hardBreak'},
                                {'type': 'text', 'text': 'Подписывайтесь на наш паблик ВК: https://vk.com/my_group'}
                            ]
                        }
                    ]
                }
            }
        }
        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.content = self.sample_png
        img_resp.raise_for_status.return_value = None

        def side_effect(url, headers=None):
            if "chapter" in url:
                return api_resp
            return img_resp

        mock_get.side_effect = side_effect

        parser = ChapterContentParser(
            url="https://api.cdnlibs.org/api/manga/test/chapter?number=2&volume=1",
            chapter_num="2",
            chapter_name="Новый мир",
            folder_name=self.folder_name,
            image_prefix="v1-",
            image_manager=self.image_manager,
            filter_ads=True,
        )
        content, images_dict = parser.fetch_content()

        self.assertIn("<h1>Глава 2. Новый мир</h1>", content)
        self.assertIn("Первый абзац современного формата.", content)
        self.assertIn("Второй абзац текста.", content)
        self.assertIn('<img src="images/v1-2-1.png"', content)

        # Ads must be removed
        self.assertNotIn("Переводчик: John, Редактор: Mary", content)
        self.assertNotIn("https://vk.com/my_group", content)

    def test_epub_generation_manifest_uniqueness(self):
        """Verify that saving the EPUB file produces valid manifest with unique image items."""
        import zipfile
        self.book.set_cover(self.sample_png)
        self.book.add_image("shared_art.png", self.sample_png)
        # Attempting to add the same image name again
        self.book.add_image("shared_art.png", self.sample_png)

        self.book.add_page("Глава 1", '<p><img src="images/shared_art.png"/></p>')
        self.book.add_page("Глава 2", '<p><img src="images/shared_art.png"/></p>')

        epub_path = os.path.join(self.test_dir, "test.epub")
        self.book.save(epub_path)
        self.assertTrue(os.path.exists(epub_path))

        # Inspect EPUB zip
        with zipfile.ZipFile(epub_path, 'r') as zf:
            opf_content = zf.read("EPUB/package.opf").decode("utf-8")
            # Count occurrences of href="images/shared_art.png" in manifest
            self.assertEqual(opf_content.count('href="images/shared_art.png"'), 1)
            # Both pages must exist
            self.assertIn("EPUB/page0001.xhtml", zf.namelist())
            self.assertIn("EPUB/page0002.xhtml", zf.namelist())


if __name__ == '__main__':
    unittest.main()
