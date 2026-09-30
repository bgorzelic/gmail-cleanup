"""A growing sender list replaces its older filter instead of stacking a new one."""

import gmail_cleanup as gmail_cli

ACTION = {'addLabelIds': ['Label_82'], 'removeLabelIds': ['INBOX', 'UNREAD']}


def _filter(fid, senders, action=ACTION, **extra):
    return {'id': fid, 'criteria': {'from': ' OR '.join(senders), **extra}, 'action': action}


NEW = {'name': 'unsubbed', 'criteria': {'from': 'a@x.com OR b@x.com OR c@x.com'}, 'action': ACTION}


def test_strict_subset_with_same_action_is_superseded():
    old = _filter('old', ['a@x.com', 'B@x.com'])
    assert gmail_cli._superseded_filters(NEW, [old]) == [old]


def test_filter_with_a_sender_not_in_new_is_kept():
    # Deleting it would drop coverage for d@x.com.
    assert gmail_cli._superseded_filters(NEW, [_filter('f', ['a@x.com', 'd@x.com'])]) == []


def test_different_action_is_kept():
    other = {'addLabelIds': ['STARRED'], 'removeLabelIds': []}
    assert gmail_cli._superseded_filters(NEW, [_filter('f', ['a@x.com'], action=other)]) == []


def test_filter_with_extra_criteria_is_kept():
    assert gmail_cli._superseded_filters(NEW, [_filter('f', ['a@x.com'], subject='sale')]) == []


def test_identical_filter_is_not_superseded():
    # Identical criteria are handled as "already exists", never deleted.
    assert gmail_cli._superseded_filters(NEW, [_filter('f', ['a@x.com', 'b@x.com', 'c@x.com'])]) == []
