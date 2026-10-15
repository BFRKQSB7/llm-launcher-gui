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

    def test_auto_check_updates_round_trips_in_config(self):
        llm_gui.save_cfg({'auto_check_updates': False})
        self.assertFalse(llm_gui.load_cfg()['auto_check_updates'])
        self.assertFalse(llm_gui.default_auto_check_updates(llm_gui.load_cfg()))
        llm_gui.save_cfg({'server_path': 'x'})   # 旧配置无该字段
        self.assertTrue(llm_gui.default_auto_check_updates(llm_gui.load_cfg()))

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


class CommandBuildingTests(unittest.TestCase):
    @staticmethod
    def _app():
        app = object.__new__(llm_gui.App)
        app.cfg = {'server_path': 'llama-server.exe'}
        app.is_gemma = lambda _model: False
        app.append_log = lambda _message: None
        return app

    def test_build_cmd_includes_top_k_ubatch_and_cache_reuse(self):
        args = self._app().build_cmd('model.gguf', {
            'top_k': 40,
            'n_ubatch': 512,
            'cache_reuse': 256,
            'thinking': False,
        })

        self.assertIn(['--top-k', '40'], [args[i:i + 2] for i in range(len(args) - 1)])
        self.assertIn(['--ubatch-size', '512'], [args[i:i + 2] for i in range(len(args) - 1)])
        self.assertIn(['--cache-reuse', '256'], [args[i:i + 2] for i in range(len(args) - 1)])

    def test_build_cmd_omits_blank_new_parameters(self):
        args = self._app().build_cmd('model.gguf', {
            'top_k': '',
            'n_ubatch': '',
            'cache_reuse': '',
            'thinking': False,
        })

        self.assertNotIn('--top-k', args)
        self.assertNotIn('--ubatch-size', args)
        self.assertNotIn('--cache-reuse', args)


class ComputedDefaultsTests(unittest.TestCase):
    @staticmethod
    def _app():
        app = object.__new__(llm_gui.App)
        app.cfg = {}
        app.is_gemma = lambda _model: False
        return app

    def test_general_category_delegates_hardware_fit_to_llama(self):
        app = self._app()
        params, detail = app.compute_defaults('missing.gguf', '通用')
        args = app.build_cmd('missing.gguf', params)

        self.assertEqual(params['ctx'], '')
        self.assertEqual(params['ngl'], '')
        self.assertEqual(params['flash'], 'auto')
        self.assertEqual(params['cache'], '')
        self.assertNotIn('-c', args)
        self.assertNotIn('-ngl', args)
        self.assertNotIn('-ctk', args)
        self.assertIn(['--flash-attn', 'auto'], [args[i:i + 2] for i in range(len(args) - 1)])
        self.assertIn('--fit', detail)

    def test_fim_category_applies_official_example_defaults(self):
        params, detail = self._app().compute_defaults('missing.gguf', llm_gui.FIM_CATEGORY)

        self.assertEqual(params['n_batch'], 1024)
        self.assertEqual(params['n_ubatch'], 512)
        self.assertEqual(params['cache_reuse'], 256)
        self.assertEqual(params['n_predict'], 128)
        self.assertEqual(params['temp'], 0.0)
        self.assertEqual(params['top_k'], 40)
        self.assertEqual(params['top_p'], 0.99)
        self.assertEqual(params['parallel'], 1)
        self.assertFalse(params['thinking'])
        self.assertEqual(params['ctx'], '')
        self.assertEqual(params['ngl'], '')
        self.assertEqual(params['flash'], 'auto')
        self.assertEqual(params['cache'], 'q8_0')
        self.assertIn('FIM', detail)

    def test_fim_cache_reuse_must_exceed_max_output(self):
        with self.assertRaisesRegex(ValueError, '严格大于最大输出'):
            llm_gui.validate_fim_cache_reuse(llm_gui.FIM_CATEGORY, 128, 128)
        llm_gui.validate_fim_cache_reuse(llm_gui.FIM_CATEGORY, 256, 128)
        llm_gui.validate_fim_cache_reuse(llm_gui.FIM_CATEGORY, 0, 128)
        llm_gui.validate_fim_cache_reuse('聊天', 64, 128)


if __name__ == '__main__':
    unittest.main()
