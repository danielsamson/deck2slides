"""Builders for the Google Slides batchUpdate requests and parsers for the (masked) presentation reads. Pure functions: the
agent passes JSON saved from `read_presentation` in, and pastes the returned request list into `update_presentation`."""
import json, re

READ_IMAGES_MASK = ['revisionId', 'slides.objectId', 'slides.pageElements(objectId,description,image.contentUrl)']

def _elements(pres):
    for si, s in enumerate(pres.get('slides', [])):
        for e in s.get('pageElements', []): yield si, s.get('objectId'), e

def page_ids(pres): return [s['objectId'] for s in pres.get('slides', [])]
def revision(pres): return pres.get('revisionId')

READ_ELEMENTS_MASK = ['revisionId', 'slides.objectId', 'slides.pageElements(objectId,title,description)']

def ids_by_tag(pres):
    """tag (slide.n.assetkey, written by the build into each picture's title; older builds used the description) -> picture objectId."""
    out = {}
    for _, _, e in _elements(pres):
        for f in ('description', 'title'):        # title wins: the description now holds the picture's alt text
            if e.get(f) and re.match(r'^[\w-]+\.\d+\.im[0-9a-z]+$', e[f]): out[e[f]] = e['objectId']
    return out

def bundle_urls(pres):
    """asset key -> temporary image URL (about 30 minutes), read from an uploaded bundle presentation."""
    return {e['description']: e['image']['contentUrl'] for _, _, e in _elements(pres) if e.get('description') and e.get('image', {}).get('contentUrl')}

def replace_image_requests(elements, tag_to_id, key_to_url):
    """mask mode: one replaceImage per picture element (opacity is NOT sent: the API refuses to update image transparency; it has to be in the uploaded placeholder). Elements whose
    bundle URL is not in key_to_url are skipped, so a bundle can be finished before the next starts."""
    reqs = []; missing = []
    for el in elements:
        oid = tag_to_id.get(el['tag']); url = key_to_url.get(el['key'])
        if not oid: missing.append(el['tag']); continue
        if not url: continue
        reqs.append({'replaceImage': {'imageObjectId': oid, 'url': url, 'imageReplaceMethod': el['method']}})
    return reqs, missing

def replace_shape_requests(keys, key_to_url):
    """shape mode: replace every tagged placeholder shape holding {{key}} with the picture."""
    return [{'replaceAllShapesWithImage': {'imageUrl': key_to_url[k], 'imageReplaceMethod': 'CENTER_INSIDE', 'containsText': {'text': '{{%s}}' % k, 'matchCase': True}}} for k in keys if k in key_to_url]

def drive_link_url(file_id): return 'https://drive.google.com/uc?export=download&id=' + file_id

def parse_folder_listing(html):
    """Public Drive folder (https://drive.google.com/embeddedfolderview?id=<id>#list) -> {file name: file id}."""
    import re
    out = {}
    for m in re.finditer(r'id="entry-([\w-]+)".*?class="flip-entry-title">([^<]+)<', html, re.S): out[m.group(2).strip()] = m.group(1)
    return out

def unwrap(obj):
    """A read as the connector returns it ({"content": {...}}), or the presentation itself."""
    return obj.get('content', obj) if isinstance(obj, dict) else obj

def swap_plan(manifest, deck_read, bundle_reads):
    """Every placeholder picture in the converted deck -> the bundle picture with the same asset key, matched by tag (never by position).
    Returns (requests, report, problems). problems is non-empty when a placeholder has no object in the deck, a key has no bundle picture,
    or a bundle picture is not wanted by any placeholder: then the plan is incomplete and should not be sent as is."""
    deck = unwrap(deck_read); tag_to_id = ids_by_tag(deck); key_to_url = {}
    for b in bundle_reads: key_to_url.update(bundle_urls(unwrap(b)))
    reqs, report, problems, used = [], [], [], set()
    for el in manifest['elements']:
        oid = tag_to_id.get(el['tag']); url = key_to_url.get(el['key'])
        if not oid: problems.append('no object in the deck for placeholder ' + el['tag']); continue
        if not url: problems.append('no bundle picture for key %s (placeholder %s)' % (el['key'], el['tag'])); continue
        used.add(el['key'])
        reqs.append({'replaceImage': {'imageObjectId': oid, 'url': url, 'imageReplaceMethod': el['method']}})
        report.append('%-34s -> %-8s %s%s' % (el['tag'], oid, el['method'], '  (GIF)' if el.get('gif') else ''))
    for k in key_to_url:
        if k not in used: problems.append('bundle picture %s is not used by any placeholder' % k)
    return reqs, report, problems

def dump(reqs): return json.dumps(reqs, separators=(',', ':'))
