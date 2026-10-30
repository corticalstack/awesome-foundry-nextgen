"""Checks on lab 08-05c's covering document and its two diagrams: the guide's steps and sections,
the diagrams' actors and numbered steps, PNGs that carry the exact diagram they were exported
from, no GUIDs in any of them, and the CHANGELOG entry.
"""

import re
import struct
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest

LAB = Path(__file__).parents[1]
REPO = LAB.parents[1]
GUIDE = LAB / '08-05c-00-news-mcp-per-user-access.md'
DIAGRAMS = REPO / 'docs' / 'diagrams'
NAMES = ('08-05c-track-a-wrapper', '08-05c-track-b-apim')
GUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


@pytest.fixture(scope='module')
def guide():
    return GUIDE.read_text()


@pytest.mark.parametrize('phrase', ['sign in', 'Responses endpoint', 'on behalf of', 'enforcement point',
                                    'validates', '`X-Api-Key`', '`isError`'])
def test_guide_walks_through_the_flow(guide, phrase):
    assert phrase.lower() in guide.lower()


def test_guide_embeds_both_diagrams(guide):
    for name in NAMES:
        assert f'](../../docs/diagrams/{name}.png)' in guide


def test_guide_sections(guide):
    headings = [line.lstrip('#').strip().lower() for line in guide.splitlines() if line.startswith('#')]
    assert any('per-agent' in h for h in headings)
    assert any('teardown' in h for h in headings)
    assert any('if the connection api refuses' in h for h in headings)  # 08-05c-01's error message points here


def _labels(path):
    return [re.sub(r'<[^>]+>', ' ', cell.get('value', '')) for cell in ET.parse(path).iter('mxCell')]


@pytest.mark.parametrize('name', NAMES)
def test_diagram_actors_and_steps(name):
    labels = _labels(DIAGRAMS / f'{name}.drawio')
    text = ' '.join(labels).lower()
    for actor in ('user a', 'user b', 'client app', 'agent service', 'entra id', 'enforcement point', 'gnews'):
        assert actor in text
    assert {str(n) for n in range(1, 8)} <= {label.strip() for label in labels}


def _embedded_diagram(png):
    """The diagram XML draw.io writes into a PNG exported with --embed-diagram."""
    data = png.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    i = 8
    while i < len(data):
        length, kind = struct.unpack('>I4s', data[i:i + 8])
        body = data[i + 8:i + 8 + length]
        if kind == b'zTXt' and body.startswith(b'mxGraphModel\0'):
            return urllib.parse.unquote(zlib.decompress(body.split(b'\0', 1)[1][1:]).decode('latin-1'))
        i += 12 + length
    return None


@pytest.mark.parametrize('name', NAMES)
def test_png_is_the_exported_source(name):
    """A PNG matches its source when it carries that exact diagram; file times do not survive a clone."""
    png = DIAGRAMS / f'{name}.png'
    assert struct.unpack('>I', png.read_bytes()[16:20])[0] >= 1600  # width in pixels
    assert _embedded_diagram(png) == (DIAGRAMS / f'{name}.drawio').read_text()


def test_no_guids(guide):
    assert not GUID.search(guide)
    for name in NAMES:
        assert not GUID.search((DIAGRAMS / f'{name}.drawio').read_text())
        assert not GUID.search((DIAGRAMS / f'{name}.png').read_bytes().decode('latin-1'))


def test_changelog_unreleased_mentions_the_lab():
    changelog = (REPO / 'CHANGELOG.md').read_text()
    assert '## [Unreleased]' in changelog
    unreleased = changelog.split('## [Unreleased]', 1)[1].split('\n## [', 1)[0]
    assert '08-05c' in unreleased
