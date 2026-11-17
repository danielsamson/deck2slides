"""Builders for the Google Slides batchUpdate requests and parsers for the (masked) presentation reads. Pure functions: the
agent passes JSON saved from `read_presentation` in, and pastes the returned request list into `update_presentation`."""
import json

READ_ELEMENTS_MASK = ['revisionId', 'slides.objectId', 'slides.pageElements(objectId,description)']
READ_IMAGES_MASK = ['revisionId', 'slides.objectId', 'slides.pageElements(objectId,description,image.contentUrl)']

def _elements(pres):
    for si, s in enumerate(pres.get('slides', [])):
        for e in s.get('pageElements', []): yield si, s['objectId'], e

def page_ids(pres): return [s['objectId'] for s in pres.get('slides', [])]
def revision(pres): return pres.get('revisionId')

def ids_by_tag(pres):
    """description (the tag build wrote into each picture) -> picture objectId, for the converted deck."""
    return {e['description']: e['objectId'] for _, _, e in _elements(pres) if e.get('description')}

def bundle_urls(pres):
    """asset key -> temporary image URL (about 30 minutes), read from an uploaded bundle presentation."""
    return {e['description']: e['image']['contentUrl'] for _, _, e in _elements(pres) if e.get('description') and e.get('image', {}).get('contentUrl')}

def replace_image_requests(elements, tag_to_id, key_to_url):
    """mask mode: one replaceImage per picture element (+ transparency when the CSS opacity was < 1). Elements whose
    bundle URL is not in key_to_url are skipped, so a bundle can be finished before the next starts."""
    reqs = []; missing = []
    for el in elements:
        oid = tag_to_id.get(el['tag']); url = key_to_url.get(el['key'])
        if not oid: missing.append(el['tag']); continue
        if not url: continue
        reqs.append({'replaceImage': {'imageObjectId': oid, 'url': url, 'imageReplaceMethod': el['method']}})
        if el.get('transparency', 0) > 0.001:
            reqs.append({'updateImageProperties': {'objectId': oid, 'imageProperties': {'transparency': el['transparency']}, 'fields': 'transparency'}})
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

def dump(reqs): return json.dumps(reqs, separators=(',', ':'))
