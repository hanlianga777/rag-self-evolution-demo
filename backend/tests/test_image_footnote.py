import unittest

from app.knowledge_pipeline import parent_child


class ImageFootnoteTests(unittest.TestCase):
    def test_image_footnotes_reach_parent_child_and_page_text(self):
        blocks = [
            {'type': 'text', 'text': '4. 点击用户名的输入栏', 'page_idx': 49},
            {'type': 'image', 'image_caption': ['用户名输入栏'],
             'image_footnote': ['5. 利用屏幕上的键盘输入用户名，点击回车键完成',
                                '6. 按下“密码”按钮'], 'page_idx': 49},
            {'type': 'text', 'text': '7. 点击“密码输入”输入栏', 'page_idx': 49},
        ]
        parents, children, parsed = parent_child({'id': 'DOC-001', 'name': 'manual.pdf'}, blocks, len)
        for records in (parents, children, parsed):
            text = '\n'.join(row['text'] for row in records)
            self.assertIn('用户名输入栏', text)
            self.assertIn('5. 利用屏幕上的键盘输入用户名，点击回车键完成', text)
            self.assertIn('6. 按下“密码”按钮', text)
            self.assertLess(text.index('5.'), text.index('6.'))
            self.assertLess(text.index('6.'), text.index('7.'))


if __name__ == '__main__':
    unittest.main()
