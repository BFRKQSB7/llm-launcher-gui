import json
import tempfile
import threading
import unittest
from pathlib import Path

import llm_gui


class ConfigDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.paths = {
            'DATA_FILE': base / 'llm_gui_data.json',
            'LEGACY_CONFIG_FILE': base / 'llm_gui_config.json',
            'LEGACY_PRESETS_FILE': base / 'llm_presets.json',
            'LEGACY_DEFAULTS_FILE': base / 'llm_default_presets.json',
        }
        self.originals = {name: getattr(llm_gui, name) for name in self.paths}
        for name, path in self.paths.items():
            setattr(llm_gui, name, str(path))

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(llm_gui, name, value)
        self.tmp.cleanup()

    @staticmethod
    def _write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def test_migrates_three_legacy_files_into_one(self):
        self._write(self.paths['LEGACY_CONFIG_FILE'], {'server_path': 'llama-server.exe'})
        self._write(self.paths['LEGACY_PRESETS_FILE'], {'model.gguf': {'fast': {'ctx': 4096}}})
        self._write(self.paths['LEGACY_DEFAULTS_FILE'], {'model.gguf': {'ctx': 8192}})

        self.assertEqual(llm_gui.load_cfg()['server_path'], 'llama-server.exe')
        self.assertIn('model.gguf', llm_gui.load_presets())
        self.assertEqual(llm_gui.load_defaults()['model.gguf']['ctx'], 8192)
        self.assertTrue(self.paths['DATA_FILE'].exists())
        self.assertFalse(any(path.exists() for name, path in self.paths.items() if name.startswith('LEGACY_')))

    def test_section_saves_preserve_other_sections(self):
        llm_gui.save_cfg({'remember_size': False})
        llm_gui.save_presets({'model.gguf': {'default': {}}})
        llm_gui.save_defaults({'model.gguf': {'ctx': 16384}})

        data = json.loads(self.paths['DATA_FILE'].read_text(encoding='utf-8'))
        self.assertEqual(data['config'], {'remember_size': False})
        self.assertIn('model.gguf', data['presets'])
        self.assertEqual(data['defaults']['model.gguf']['ctx'], 16384)

    def test_concurrent_section_saves_do_not_overwrite_each_other(self):
        writers = (
            lambda i: llm_gui.save_cfg({'revision': i}),
            lambda i: llm_gui.save_presets({'model.gguf': {'p': {'revision': i}}}),
            lambda i: llm_gui.save_defaults({'model.gguf': {'revision': i}}),
        )
        def write_all(fn):
            for i in range(20):
                fn(i)

        threads = [threading.Thread(target=write_all, args=(fn,)) for fn in writers]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        data = json.loads(self.paths['DATA_FILE'].read_text(encoding='utf-8'))
        self.assertEqual(data['config']['revision'], 19)
        self.assertEqual(data['presets']['model.gguf']['p']['revision'], 19)
        self.assertEqual(data['defaults']['model.gguf']['revision'], 19)


if __name__ == '__main__':
    unittest.main()
