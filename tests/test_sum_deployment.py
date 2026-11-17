from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SumDeploymentTests(unittest.TestCase):
    def test_retired_command_has_no_code_plugin_contract_or_worker_installer(self):
        self.assertFalse((ROOT / 'openclaw-plugins/shrink-command').exists())
        self.assertFalse((ROOT / 'scripts/install-shrink-worker.py').exists())
        self.assertEqual(list((ROOT / 'scripts').glob('shrink_*.py')), [])
        self.assertEqual(list((ROOT / 'config').glob('shrink*.md')), [])

    def test_fresh_setup_and_template_install_only_sum_command(self):
        setup = (ROOT / 'scripts/setup.sh').read_text()
        template = (ROOT / 'config/openclaw.json.template').read_text()
        self.assertNotIn('shrink', setup.lower())
        self.assertNotIn('shrink', template.lower())
        self.assertIn('__SUM_PLUGIN_PATH__', template)
        self.assertIn('"sum-command"', template)
        self.assertIn('ffmpeg ffprobe', setup)

    def test_current_configuration_and_runtime_instructions_do_not_advertise_retired_command(self):
        for relative in ('.env.example', '.cursorrules', 'workspace/AGENTS.md'):
            with self.subTest(path=relative):
                self.assertNotIn('shrink', (ROOT / relative).read_text().lower())
        self.assertIn('SUM_YTDLP_MODULE_DIR=', (ROOT / '.env.example').read_text())
        self.assertIn('output/shrink/', (ROOT / '.gitignore').read_text())


if __name__ == '__main__': unittest.main()
