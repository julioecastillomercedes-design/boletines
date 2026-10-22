import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import types

spec = importlib.util.spec_from_file_location('importar_drive', Path(__file__).resolve().parents[1] / 'tools/importar_drive.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class ImportadorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.entrada = Path(self.tmp.name) / 'entrada'
        self.entrada.mkdir()
        self.root_patch = patch.object(d, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.synth = patch.object(d, 'sintetizar', side_effect=self.audio)
        self.fake_audio = self.synth.start()
        self.addCleanup(self.synth.stop)

    def audio(self, guion, destino, *args):
        destino.write_bytes(b'MP3:' + guion.read_bytes())
        return True

    def fuente(self, en=False, guion=False, revision='', contenido='nuevo', carpeta=''):
        nombre = 'nefrologia-2026-10-08' + ('.en' if en else '')
        nombre += ('.r' + revision if revision else '') + '.v' + ('.guion.txt' if guion else '.md')
        p = self.entrada / carpeta / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        text = contenido + '\n\nSegundo párrafo.\n\nTercer párrafo.' if guion else '---\nspecialty: nefrologia\ndate: 2026-10-08\n---\n' + contenido
        p.write_text(text)
        return p

    def revision(self, sello='20261010T100000Z', contenido='nuevo'):
        for en in (False, True):
            for guion in (False, True):
                self.fuente(en, guion, sello, contenido)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_crea_legacy_y_segunda_ejecucion_no_regraba(self):
        self.fuente()
        self.fuente(guion=True)
        d.main(self.entrada)
        before = self.snapshot()
        d.main(self.entrada)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.fake_audio.call_count, 1)

    def test_revision_actualiza_ambos_idiomas_y_audio(self):
        self.fuente()
        self.fuente(guion=True)
        d.main(self.entrada)
        self.revision()
        d.main(self.entrada)
        self.assertIn('nuevo', (self.root / 'issues/nefrologia/2026-10-08.en.md').read_text())
        self.assertTrue((self.root / 'audio/nefrologia-2026-10-08-en.mp3').exists())
        before = self.snapshot()
        d.main(self.entrada)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.fake_audio.call_count, 2)  # ES sin cambios; solo faltaba EN.

    def test_elige_sello_mayor_y_no_vuelve_atras(self):
        self.revision(contenido='anterior')
        self.revision('20261011T100000Z', 'final')
        d.main(self.entrada)
        before = self.snapshot()
        for p in self.entrada.rglob('*20261011*'):
            p.unlink()
        d.main(self.entrada)
        self.assertEqual(before, self.snapshot())
        self.assertIn('final', (self.root / 'issues/nefrologia/2026-10-08.md').read_text())

    def test_cambia_guion_regenera_y_conserva_idempotencia(self):
        self.revision(contenido='primera')
        d.main(self.entrada)
        self.revision('20261011T100000Z', 'segunda')
        d.main(self.entrada)
        self.assertEqual(self.fake_audio.call_count, 4)
        self.assertIn(b'segunda', (self.root / 'audio/nefrologia-2026-10-08.mp3').read_bytes())

    def test_fallo_de_segundo_audio_no_publica_nada(self):
        self.revision(contenido='primera')
        d.main(self.entrada)
        before = self.snapshot()
        self.revision('20261011T100000Z', 'segunda')
        self.fake_audio.side_effect = [True, RuntimeError('fallo TTS')]
        # El primer resultado verdadero también debe tener archivo para ser válido.
        contador = []
        def falla_segundo(*args):
            contador.append(1)
            if len(contador) == 2:
                raise RuntimeError('fallo TTS')
            return self.audio(*args)
        self.fake_audio.side_effect = falla_segundo
        with self.assertRaisesRegex(RuntimeError, 'fallo TTS'):
            d.main(self.entrada)
        self.assertEqual(before, self.snapshot())

    def test_duplicados_distintos_bloquean_antes_de_escribir(self):
        self.fuente(contenido='uno', carpeta='id1')
        self.fuente(contenido='dos', carpeta='id2')
        with self.assertRaisesRegex(ValueError, 'contradictorios'):
            d.main(self.entrada)
        self.assertEqual(self.snapshot(), {})

    def test_duplicados_identicos_son_validos(self):
        self.fuente(carpeta='id1')
        self.fuente(carpeta='id2')
        d.main(self.entrada)
        self.assertTrue((self.root / 'issues/nefrologia/2026-10-08.md').exists())

    def test_revision_incompleta_bloquea(self):
        self.fuente(revision='20261010T100000Z')
        with self.assertRaisesRegex(ValueError, 'incompleta'):
            d.main(self.entrada)
        self.assertEqual(self.snapshot(), {})

    def test_sello_publicado_es_inmutable(self):
        self.revision()
        d.main(self.entrada)
        before = self.snapshot()
        self.fuente(revision='20261010T100000Z', contenido='manipulado')
        with self.assertRaisesRegex(ValueError, 'ya publicada modificada'):
            d.main(self.entrada)
        self.assertEqual(before, self.snapshot())

    def test_legacy_no_sobrescribe_publicado(self):
        self.fuente(contenido='primera')
        d.main(self.entrada)
        before = self.snapshot()
        self.fuente(contenido='otra')
        with self.assertRaisesRegex(ValueError, 'sin sello'):
            d.main(self.entrada)
        self.assertEqual(before, self.snapshot())

    def test_encabezado_o_guion_invalido_no_escribe(self):
        p = self.fuente()
        p.write_text('---\nspecialty: cardiologia\ndate: 2026-10-08\n---\nmal')
        with self.assertRaisesRegex(ValueError, 'Encabezado'):
            d.main(self.entrada)
        p.unlink()
        p = self.fuente(guion=True)
        p.write_text('Corto')
        with self.assertRaisesRegex(ValueError, 'Guion demasiado corto'):
            d.main(self.entrada)
        self.assertEqual(self.snapshot(), {})

    def test_descarga_preserva_ids_duplicados_y_fallo_es_visible(self):
        self.entrada.rmdir()
        archivos = [types.SimpleNamespace(id=i, path='nefrologia-2026-10-08.v.md') for i in ['id1', 'id2']]
        def bajar(**kw):
            Path(kw['output']).write_text(kw['id'])
            return kw['output']
        fake = types.SimpleNamespace(download_folder=lambda **kw: archivos, download=bajar)
        with patch.dict(sys.modules, {'gdown': fake}), patch.dict('os.environ', {'DRIVE_PENDIENTES': 'https://drive.google.com/drive/folders/test'}):
            d.descargar(self.entrada)
            self.assertEqual(len(list(self.entrada.rglob('*.md'))), 2)
            with self.assertRaisesRegex(ValueError, 'vacía'):
                d.descargar(self.entrada)

    def test_borradores_no_se_importan(self):
        p = self.fuente()
        p.rename(p.with_name(p.name.replace('.v.', '.')))
        d.main(self.entrada)
        self.assertEqual(self.snapshot(), {})


if __name__ == '__main__':
    unittest.main()
