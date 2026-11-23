from d2s import gslides

MAN = {'elements': [
    {'tag': 'cover.0.ima', 'key': 'ima', 'method': 'CENTER_INSIDE'},
    {'tag': 'nightIdeaB.0.imvid', 'key': 'imvid', 'method': 'CENTER_CROP', 'gif': True}]}

def deck(extra=()):
    els = [{'objectId': 'p1_i2', 'description': 'cover.0.ima'}, {'objectId': 'p9_i9', 'description': 'nightIdeaB.1.imother'},
           {'objectId': 'p9_i3', 'description': 'nightIdeaB.0.imvid'}] + list(extra)
    return {'content': {'revisionId': 'r1', 'slides': [{'objectId': 'p1', 'pageElements': els}]}}

def bundle(*keys):
    return {'content': {'slides': [{'objectId': 's%d' % i, 'pageElements': [{'description': k, 'image': {'contentUrl': 'https://x/' + k}}]} for i, k in enumerate(keys)]}}

def test_matches_by_tag_not_position():
    reqs, report, problems = gslides.swap_plan(MAN, deck(), [bundle('ima'), bundle('imvid')])
    assert not problems
    by_id = {r['replaceImage']['imageObjectId']: r['replaceImage'] for r in reqs}
    assert by_id['p9_i3']['url'] == 'https://x/imvid'          # the video goes on its own placeholder, not the neighbour p9_i9
    assert 'p9_i9' not in by_id and by_id['p9_i3']['imageReplaceMethod'] == 'CENTER_CROP'

def test_reports_missing_and_unused():
    _, _, problems = gslides.swap_plan(MAN, deck(), [bundle('ima', 'imstray')])
    assert any('imvid' in p for p in problems) and any('imstray' in p for p in problems)

def test_unwrap_plain_presentation():
    reqs, _, problems = gslides.swap_plan(MAN, deck()['content'], [bundle('ima')['content'], bundle('imvid')])
    assert len(reqs) == 2 and not problems
