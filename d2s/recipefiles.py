"""Design System files for recipes: Recipes.md, recipes.json, an example slide per recipe (rendered from the recipe with its own
evidence slide's words) and showcase cards."""
import json, re
from . import recipes as R, components as C


def spec_lines(r, tk, styles):
    L = []
    def el_line(el, prefix=''):
        x = R.xpos(el['x'], tk)
        w = R.width(el, tk)
        s = el.get('style')
        st = styles.get(s)
        return '- %s**%s** (%s): x %d, y %d, %d wide, %d high%s%s%s' % (
            prefix, el['id'], el['type'], x, el['y'], w, el.get('h', 0),
            (', style `%s` (%gpx, weight %s, colour `%s`)' % (s, st['px'], st['weight'], st['colour'])) if st else '',
            (', holds about %d characters' % el['max_chars']) if el.get('max_chars') else '', (', %s' % el['note']) if el.get('note') else '')
    if r.get('furniture'):
        L.append('Furniture:')
        L += [el_line(e) for e in r['furniture']]
    L.append('Slots:')
    L += [el_line(e) for e in r.get('slots', [])]
    for rp in r.get('repeats', []):
        L.append('Repeat **%s** (up to %d, %d per row, steps of %d px across and %d px down):' % (rp['id'], rp['max'], rp['per_row'], rp['x_step'], rp['y_step']))
        L += [el_line(e, '  ') for e in rp['slots']]
    return L


def build(recipes_json, results, tk, descs, font='DM Sans'):
    spec = json.load(open(recipes_json))
    styles = spec['styles']
    out, md = {}, ['# Recipes', '',
                   'A recipe describes one type of slide: what is on it, where (in grid columns and px), in which text styles, how much each slot holds, and which slides of the source it came from. '
                   'It is not a component and not a token. Each was proposed by Claude from exemplar slides and then **tested by recreating its source slides from the recipe plus their own words and comparing them with the originals**; the figures below are the share of the 1920x1080 slide that differs. '
                   'Positions are in the grid (`grid-margin`, `grid-column`, `grid-gutter` in `tokens.json`); the machine-readable form is `recipes.json`. '
                   'Colours are tokens: `ink` and `paper` follow the theme class on the section (`th-dark` or `th-light`).', '']
    for r in spec['recipes']:
        r = dict(r, font=font, styles=styles)
        res = results.get(r['id'], {})
        mean = sum(res.values()) / max(len(res), 1)
        md += ['## %s' % r['name'], '', r['usage'], '',
               '**Theme:** %s. **Source slides:** %s. **Recreated:** %d slide%s, %.1f%% of pixels differ on average (worst %.1f%%).%s' % (
                   r['theme'], ', '.join(map(str, r['evidence'])), len(res), '' if len(res) == 1 else 's', mean, max(res.values()) if res else 0,
                   '' if len(res) >= 3 else ' Evidence is a single slide, so this tests the recipe against its own exemplar only.'), '']
        md += spec_lines(r, tk, styles) + ['']
        n = r['evidence'][0]
        content = R.extract(r, descs[n - 1], tk, n)
        sec = R.render(r, content, tk)
        out['recipes/%s.html' % r['id']] = sec + '\n'
        out['components/Recipe%s/preview.html' % ''.join(w.capitalize() for w in r['name'].split())] = (
            '<!-- @dsCard group="Recipes" page height=1080 width=1920 subtitle="%.1f%% differs from %d source slide%s" -->\n<style>body{margin:0}section{position:relative;width:1920px;height:1080px;overflow:hidden}</style>\n%s\n'
            % (mean, len(res), '' if len(res) == 1 else 's', sec))
    out['Recipes.md'] = '\n'.join(md)
    out['recipes.json'] = json.dumps(dict(spec, results=results), indent=1)
    return out
