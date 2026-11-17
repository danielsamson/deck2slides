"""Contact sheets (HTML) for extracted components and layouts, so a person can judge them by eye."""
import html, json
from . import components as C, gslides2claude as G


def sheet(result, theme_bg='#fff'):
    cells = []
    for c in result['components']:
        w, h = c['size']
        body = c['preview_body']
        dark = 'color:#fff' if False else ''
        slots = ''.join('<div class="s"><b>%s</b> %s <i>%s</i></div>' % (s['role'], 'fixed' if s['fixed'] else 'slot', html.escape((s['examples'][0] or '')[:44])) for s in c['slots'][:4])
        cells.append('<div class="cell"><div class="t">%s <span>%d instances on %d slides</span></div>'
                     '<div class="stage" style="width:%dpx;height:%dpx;background:%s">%s</div>%s</div>' % (html.escape(c['name']), c['instances'], c['n_slides'], w, h, c.get('bg', '#fafafa'), body, slots))
    return ('<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap">'
            '<style>*{box-sizing:border-box}body{margin:24px;background:#fff;font-family:DM Sans}.cell{display:inline-block;vertical-align:top;margin:0 32px 32px 0;'
            'border:1px dashed #bbb;padding:16px;max-width:520px}.t{font:700 22px DM Sans;margin-bottom:10px}.t span{font:400 16px DM Sans;color:#777;margin-left:8px}'
            '.stage{position:relative;background:#fafafa;outline:1px solid #eee;overflow:hidden;margin-bottom:10px}.s{font:15px DM Sans;color:#444}.s i{color:#888}</style></head>'
            '<body>%s</body></html>') % ''.join(cells)
