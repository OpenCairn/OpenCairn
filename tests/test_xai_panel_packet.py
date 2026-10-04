"""A materialised panel brief must reach the API seat without double append."""
import importlib.util
from pathlib import Path
import tempfile
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('xai_panel', Path(__file__).resolve().parents[1] / '.claude/scripts/xai_client.py')
XAI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(XAI)


class PanelPacket(unittest.TestCase):
    def test_fresh_prepared_packet_reaches_grok_verbatim_without_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            brief, source, packet = root/'brief', root/'source', root/'packet'
            brief.write_text('Read the source and disagree where warranted.\n')
            source.write_text('Verified fixture evidence.\n')
            XAI.prepare_panel_brief(str(brief), [str(source)], str(packet))
            original = packet.read_text()
            source.write_text('Later drift must not change the delivered packet.\n')
            with patch.object(XAI, 'deep', return_value='review') as send:
                self.assertEqual('review', XAI.panel_review(str(packet), [], prepared=True))
                self.assertEqual(original, send.call_args.args[0])
            self.assertEqual(1, original.count('## Inlined source appendix'))
            self.assertIn('Verified fixture evidence.', original)
            self.assertNotIn('Later drift', original)

    def test_prepared_plus_sources_rejected_before_request(self):
        with tempfile.TemporaryDirectory() as d:
            packet = Path(d)/'packet';packet.write_text('ready')
            with patch.object(XAI, 'deep') as send:
                with self.assertRaisesRegex(ValueError, 'prepared.*source'):
                    XAI.panel_review(str(packet), ['anything'], prepared=True)
                send.assert_not_called()

    def test_missing_source_or_oversize_never_publishes_packet(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);brief=root/'brief';brief.write_text('brief')
            with self.assertRaises(FileNotFoundError):
                XAI.prepare_panel_brief(str(brief), [str(root/'missing')], str(root/'packet'))
            self.assertFalse((root/'packet').exists())
            source=root/'source';source.write_text('12345')
            with patch.object(XAI, 'MAX_INLINE_BYTES', 4):
                with self.assertRaises(XAI.InlineTooLarge):
                    XAI.prepare_panel_brief(str(brief), [str(source)], str(root/'packet'))
            self.assertFalse((root/'packet').exists())

    def test_existing_packet_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);brief=root/'brief';source=root/'source';packet=root/'packet'
            brief.write_text('brief');source.write_text('source');packet.write_text('original')
            with self.assertRaises(FileExistsError):
                XAI.prepare_panel_brief(str(brief), [str(source)], str(packet))
            self.assertEqual('original', packet.read_text())


    def test_prepare_rejects_dry_run_before_output_and_review_preview_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);brief=root/'brief';source=root/'source';packet=root/'packet'
            brief.write_text('Read the original work.\n');source.write_text('Controlled evidence.\n')
            env=dict(os.environ,HOME=d,CLAUDE_CONFIG_DIR=str(root/'claude'),CODEX_HOME=str(root/'codex'))
            for name in ['OPENCAIRN_SESSION_ID','CLAUDE_CODE_SESSION_ID','CODEX_THREAD_ID']:
                env.pop(name,None)
            cli=[sys.executable,str(Path(XAI.__file__))]
            prepare=cli+['--prepare-panel',str(brief),'--source',str(source),'--output',str(packet)]
            r=subprocess.run(prepare+['--dry-run'],env=env,text=True,capture_output=True)
            self.assertNotEqual(0,r.returncode)
            self.assertIn('--dry-run',r.stderr)
            self.assertFalse(packet.exists())
            r=subprocess.run(prepare,env=env,text=True,capture_output=True)
            self.assertEqual(0,r.returncode,r.stderr)
            original=packet.read_bytes()
            r=subprocess.run(cli+['--panel-review',str(packet),'--prepared','--dry-run'],env=env,text=True,capture_output=True)
            self.assertEqual(0,r.returncode,r.stderr)
            self.assertEqual(original,packet.read_bytes())
            self.assertIn('Controlled evidence.',r.stdout)


if __name__ == '__main__':unittest.main()
