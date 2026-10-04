"""A materialised panel brief must reach the API seat without double append."""
import importlib.util
from pathlib import Path
import tempfile
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


if __name__ == '__main__':unittest.main()
