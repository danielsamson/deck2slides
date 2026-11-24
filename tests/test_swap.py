from d2s import gslides

MAN = {'elements': [
    {'tag': 'cover.0.ima', 'key': 'ima', 'method': 'CENTER_INSIDE'},
    {'tag': 'nightIdeaB.0.imvid', 'key': 'imvid', 'method': 'CENTER_CROP', 'gif': True}]}

def deck(extra=()):
    els = [{'objectId': 'p1_i2', 'description': 'cover.0.ima'}, {'objectId': 'p9_i9', 'description': 'nightIdeaB.1.imother'},
           {'objectId': 'p9_i3', 'description': 'nightIdeaB.0.imvid'}] + list(extra)
    return {'content': {'revisionId': 'r1', 'slides': [{'objectId': 'p1', 'pageElements': els}]}}

def bundle(*keys):
    return {'content': {'slides': [{'pageElements': [{'description': k, 'image': {'contentUrl': 'https://x/' + k}}]} for k in keys]}}   # as the connector returns it: no slide objectId with this mask

def test_matches_by_tag_not_position():
    reqs, report, problems = gslides.swap_plan(MAN, deck(), [bundle('ima'), bundle('imvid')])
    assert not problems
    by_id = {r['replaceImage']['imageObjectId']: r['replaceImage'] for r in reqs if 'replaceImage' in r}
    alt = [r['updatePageElementAltText'] for r in reqs if 'updatePageElementAltText' in r]
    assert {a['objectId'] for a in alt} == {'p1_i2', 'p9_i3'} and all(a['title'] for a in alt)   # tag and alt text restored after each replace
    assert by_id['p9_i3']['url'] == 'https://x/imvid'          # the video goes on its own placeholder, not the neighbour p9_i9
    assert 'p9_i9' not in by_id and by_id['p9_i3']['imageReplaceMethod'] == 'CENTER_CROP'

def test_reports_missing_and_unused():
    _, _, problems = gslides.swap_plan(MAN, deck(), [bundle('ima', 'imstray')])
    assert any('imvid' in p for p in problems) and any('imstray' in p for p in problems)

def test_unwrap_plain_presentation():
    reqs, _, problems = gslides.swap_plan(MAN, deck()['content'], [bundle('ima')['content'], bundle('imvid')])
    assert len([r for r in reqs if 'replaceImage' in r]) == 2 and not problems

def test_tag_in_title_alt_text_in_description():
    d = {'content': {'revisionId': 'r', 'slides': [{'pageElements': [
        {'objectId': 'p9_i3', 'title': 'nightIdeaB.0.imvid', 'description': 'Story night in the room: friends on the sofa'},
        {'objectId': 'p1_i2', 'title': 'cover.0.ima', 'description': ''}]}]}}
    reqs, _, problems = gslides.swap_plan(MAN, d, [bundle('ima', 'imvid')])
    assert not problems and {r['replaceImage']['imageObjectId'] for r in reqs if 'replaceImage' in r} == {'p9_i3', 'p1_i2'}
