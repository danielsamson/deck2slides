"""Map the picture ids a deck uses (/_blob/<id>) to local files, for tools/viewer_render.js.

    python tools/blobs_map.py <project/slides dir> <known.json> [<fonts.json>] > blobs.json

known.json: {id: absolute file} from the deck's own asset map (the one passed to `d2s.py convert --assets`). Extra ids (an uploaded outline font)
can be added with --extra id=path. Prints the ids that have no file and exits 1 if there are any: the viewer would show them as empty boxes.
"""
import json, os, re, sys

def main(slides, known, extras):
    m = json.load(open(known)); [m.__setitem__(k, v) for k, v in extras]
    ids = set()
    for f in os.listdir(slides): ids |= set(re.findall(r'/_blob/([0-9a-f]{32})', open(os.path.join(slides, f)).read()))
    gaps = sorted(i for i in ids if i not in m or not os.path.exists(m[i]))
    json.dump(m, sys.stdout); sys.stderr.write('%d picture ids, missing: %s\n' % (len(ids), gaps or 'none'))
    return 1 if gaps else 0

if __name__ == '__main__':
    a = sys.argv[1:]; ex = [x.split('=', 1) for x in a if '=' in x and not x.startswith('/')]; a = [x for x in a if x not in ['='.join(e) for e in ex]]
    sys.exit(main(a[0], a[1], ex))
