"""Read-only characterization of the exact inherited history; zero actions."""
import collections
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PIN = 'e675f36184f1cee8775fb0b4a7cbdea3362d7beb'


def valid_position(value):
    return (type(value) is list and len(value) == 2 and
            all(type(x) is int and -2 <= x <= 2 for x in value))


@unittest.skipUnless((ROOT/'state/organism.json').is_file(), 'historical file not present locally')
class HistoricalShapeTests(unittest.TestCase):
    def test_read_exact_historical_record_shapes_without_changing_them(self):
        path = ROOT/'state/organism.json'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), PIN)
        state = json.loads(raw)
        lab = state['planning_lab']
        rows = lab['transition_observations']
        shapes = collections.Counter()
        missing_by_world = collections.Counter()
        examples = {}
        for index, row in enumerate(rows):
            shape = (str(row.get('source')), str(row.get('world_version')),
                     ','.join(sorted(row)))
            shapes[shape] += 1
            if not valid_position(row.get('before')) or not valid_position(row.get('after')):
                missing_by_world[str(row.get('world_version'))] += 1
                examples.setdefault(shape, {'index': index, 'record': row})
        report = {'schema_version': state['schema_version'], 'cycle': state['cycles'],
                  'identity': state['identity'], 'position': lab['position'],
                  'world': lab['world_version'], 'delivered_rows': len(rows),
                  'shapes': [{'source': s, 'world': w, 'keys': k, 'count': n}
                             for (s, w, k), n in sorted(shapes.items())],
                  'invalid_or_absent_positions_by_world': dict(missing_by_world),
                  'first_example_per_affected_shape': list(examples.values()),
                  'world_actions': 0, 'source_mutated': False}
        print('ORA2_HISTORY_SHAPES ' + json.dumps(report, sort_keys=True), flush=True)
        self.assertEqual(path.read_bytes(), raw)
