# -*- coding: utf-8 -*-
# __Author__ __Lencof__
# test_pytest_trello.py

import pytest
import inspect
import re
import os
import sys

from _pytest.main import EXIT_OK, EXIT_NOTESTSCOLLECTED


pytest_plugins = 'pytester',

OPEN_CARDS = ['https://trello.com/c/open1234', 'https://trello.com/c/open4321']
CLOSED_CARDS = ['https://trello.com/c/closed12', 'https://trello.com/c/closed21']
ALL_CARDS = OPEN_CARDS + CLOSED_CARDS


def assert_outcome(result, passed=0, failed=0, skipped=0, xpassed=0, xfailed=0):
    '''This method works around a limitation where pytester assertoutcome()
    doesn't support xpassed and xfailed.
    '''

    actual_count = dict(passed=0, failed=0, skipped=0, xpassed=0, xfailed=0)

    reports = filter(lambda x: hasattr(x, 'when'), result.getreports())
    for report in reports:
        if report.when == 'setup':
            if report.skipped:
                actual_count['skipped'] += 1
        elif report.when == 'call':
            if hasattr(report, 'wasxfail'):
                if report.failed:
                    actual_count['xpassed'] += 1
                elif report.skipped:
                    actual_count['xfailed'] += 1
            else:
                actual_count[report.outcome] += 1
        else:
            continue

    assert passed == actual_count['passed']
    assert failed == actual_count['failed']
    assert skipped == actual_count['skipped']
    assert xfailed == actual_count['xfailed']
    assert xpassed == actual_count['xpassed']


class PyTestOption(object):

    def __init__(self, config=None):
        self.config = config

    @property
    def args(self):
        args = list()
        if self.config.getoption('trello_api_key') is not None:
            args.append('--trello-api-key')
            args.append(self.config.getoption('trello_api_key'))
        if self.config.getoption('trello_api_token') is not None:
            args.append('--trello-api-token')
            args.append(self.config.getoption('trello_api_token'))
        for completed in self.config.getoption('trello_completed'):
            args.append('--trello-completed')
            args.append('"%s"' % completed)
        return args


def mock_trello_card_get(self, card_id, **kwargs):
    '''Returns JSON representation of an trello card.'''
    if card_id.startswith("closed"):
        is_closed = True
    else:
        is_closed = False

    return {
        "labels": [],
        "pos": 33054719,
        "manualCoverAttachment": False,
        "badges": {},
        "id": "550c37c5226dd7241a61372f",
        "idBoard": "54aeece5d8b09a1947f34050",
        "idShort": 334,
        "shortUrl": "https://trello.com/c/%s" % card_id,
        "closed": False,
        "email": "nospam@boards.trello.com",
        "dateLastActivity": "2015-03-20T15:12:29.735Z",
        "idList": "%s53f20bbd90cfc68effae9544" % (is_closed and 'closed' or 'open'),
        "idLabels": [],
        "idMembers": [],
        "checkItemStates": [],
        "name": "mock trello card - %s" % (is_closed and 'closed' or 'open'),
        "desc": "mock trello card - %s" % (is_closed and 'closed' or 'open'),
        "descData": {},
        "url": "https://trello.com/c/%s" % card_id,
        "idAttachmentCover": None,
        "idChecklists": []
    }


def mock_trello_list_get(self, list_id, **kwargs):
    '''Returns JSON representation of a trello list containing open cards.'''
    if list_id.startswith("closed"):
        is_closed = True
    else:
        is_closed = False

    return {
        "pos": 124927.75,
        "idBoard": "54aeece5d8b09a1947f34050",
        "id": list_id,
        "closed": False,
        "name": is_closed and "Done" or "Not Done"
    }


@pytest.fixture()
def option(request):
    return PyTestOption(request.config)


@pytest.fixture()
def monkeypatch_trello(request, monkeypatch):
    monkeypatch.delattr("requests.get")
    monkeypatch.delattr("requests.sessions.Session.request")
    monkeypatch.setattr('trello.cards.Cards.get', mock_trello_card_get)
    monkeypatch.setattr('trello.lists.Lists.get', mock_trello_list_get)


def test_plugin_markers(testdir):
    '''Verifies expected output from of py.test --markers'''

    result = testdir.runpytest('--markers')
    result.stdout.fnmatch_lines([
        '@pytest.mark.trello(*cards): Trello card integration',
    ])


def test_plugin_help(testdir):
    '''Verifies expected output from of py.test --help'''

    result = testdir.runpytest('--help')
    result.stdout.fnmatch_lines([
        'pytest-trello:',
        '* --trello-cfg=TRELLO_CFG',
        '* --trello-api-key=TRELLO_API_KEY',
        '* --trello-api-token=TRELLO_API_TOKEN',
        '* --trello-completed=TRELLO_COMPLETED',
        '* --show-trello-cards *',
    ])


def test_param_trello_cfg_without_value(testdir, option, monkeypatch_trello):
    '''Verifies failure when not providing a value to the --trello-cfg parameter'''

    result = testdir.runpytest(*['--trello-cfg'])
    assert result.ret == 2
    result.stderr.fnmatch_lines([
        '*: error: argument --trello-cfg: expected one argument',
    ])


def test_param_trello_cfg_with_no_such_file(testdir, option, monkeypatch_trello, capsys):
    '''Verifies pytest-trello ignores any bogus files passed to --trello-cfg'''

    result = testdir.runpytest(*['--trello-cfg', 'asdfasdf'])
    assert result.ret == EXIT_NOTESTSCOLLECTED

    # FIXME - assert actual log.warning message
    # No trello configuration file found matching:


def test_param_trello_cfg_containing_no_data(testdir, option, monkeypatch_trello, capsys):
    '''Verifies pytest-trello ignores --trello-cfg files that contain bogus data'''

    # Create bogus config file for testing
    cfg_file = testdir.makefile('.txt', '')

    # Run with parameter (expect pass)
    result = testdir.runpytest(*['--trello-cfg', str(cfg_file)])
    assert result.ret == EXIT_OK

    # FIXME - assert actual log.warning message
    # No trello configuration file found matching:


def test_param_trello_cfg(testdir, option, monkeypatch_trello, capsys):
    '''Verifies pytest-trello loads completed info from provided --trello-cfg parameter'''

    # Create trello.yml config for testing
    contents = '''
    trello:
        key: ''
        token: ''
        completed:
            - 'Not Done'
    '''
    cfg_file = testdir.makefile('.yml', contents)

    # The following would normally xpass, but when completed=['Not Done'], it
    # will just pass
    src = """
        import pytest
        @pytest.mark.trello('%s')
        def test_func():
            assert True
        """ % OPEN_CARDS[0]
    result = testdir.inline_runsource(src, *['--trello-cfg', str(cfg_file)])
    assert result.ret == EXIT_OK
    assert_outcome(result, passed=1)


def test_param_trello_api_key_without_value(testdir, option, monkeypatch_trello, capsys):
    '''Verifies failure when not passing --trello-api-key an option'''

    # Run without parameter (expect fail)
    result = testdir.runpytest(*['--trello-api-key'])
    assert result.ret == 2
    result.stderr.fnmatch_lines([
        '*: error: argument --trello-api-key: expected one argument',
    ])


def test_param_trello_api_key_with_value(testdir, option, monkeypatch_trello, capsys):
    '''Verifies success when passing --trello-api-key an option'''

    result = testdir.runpytest(*['--trello-api-key', 'asdf'])
    assert result.ret == EXIT_NOTESTSCOLLECTED

    # TODO - would be good to assert some output

def test_param_trello_api_token_without_value(testdir, option, monkeypatch_trello, capsys):
    '''Verifies failure when not passing --trello-api-token an option'''

    result = testdir.runpytest(*['--trello-api-token'])
    assert result.ret == 2
    result.stderr.fnmatch_lines([
        '*: error: argument --trello-api-token: expected one argument',
    ])


def test_param_trello_api_token_with_value(testdir, option, monkeypatch_trello, capsys):
    '''Verifies success when passing --trello-api-token an option'''

    result = testdir.runpytest(*['--trello-api-token', 'asdf'])
    assert result.ret == EXIT_NOTESTSCOLLECTED

    # TODO - would be good to assert some output


def test_pass_without_trello_card(testdir, option):
    '''Verifies test success when no trello card is supplied'''

    testdir.makepyfile("""
        import pytest
        def test_func():
            assert True
        """)
    result = testdir.runpytest(*option.args)
    assert result.ret == EXIT_OK
    assert result.parseoutcomes()['passed'] == 1


def test_fail_without_trello_card(testdir, option):
    '''Verifies test failure when no trello card is supplied'''

    testdir.makepyfile("""
        import pytest
        def test_func():
            assert False
        """)
    result = testdir.runpytest(*option.args)
    assert result.ret == 1
    assert result.parseoutcomes()['failed'] == 1


def test_success_with_open_card(testdir, option, monkeypatch_trello):
    '''Verifies when a test succeeds with an open trello card'''

    src = """
        import pytest
        @pytest.mark.trello('%s')
        def test_func():
            assert True
        """ % OPEN_CARDS[0]
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['xpassed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, xpassed=1)


def test_success_with_open_cards(testdir, option, monkeypatch_trello):
    '''Verifies when a test succeeds with open trello cards'''

    src = """
        import pytest
        @pytest.mark.trello(*%s)
        def test_func():
            assert True
        """ % OPEN_CARDS
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['xpassed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, xpassed=1)


def test_failure_with_open_card(testdir, option, monkeypatch_trello):
    '''Verifies when a test fails with an open trello card'''

    src = """
        import pytest
        @pytest.mark.trello('%s')
        def test_func():
            assert False
        """ % OPEN_CARDS[0]
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['xfailed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, xfailed=1)


def test_failure_with_open_cards(testdir, option, monkeypatch_trello):
    '''Verifies when a test fails with open trello cards'''

    src = """
        import pytest
        @pytest.mark.trello(*%s)
        def test_func():
            assert False
        """ % OPEN_CARDS
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['xfailed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, xfailed=1)


def test_failure_with_closed_card(testdir, option, monkeypatch_trello):
    '''Verifies when a test fails with a closed trello card'''

    src = """
        import pytest
        @pytest.mark.trello('%s')
        def test_func():
            assert False
        """ % CLOSED_CARDS[0]
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == 1
    # assert result.parseoutcomes()['failed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, failed=1)


def test_failure_with_closed_cards(testdir, option, monkeypatch_trello):
    '''Verifies when a test fails with closed trello cards'''

    src = """
        import pytest
        @pytest.mark.trello(*%s)
        def test_func():
            assert False
        """ % CLOSED_CARDS
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == 1
    # assert result.parseoutcomes()['failed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, failed=1)


def test_failure_with_open_and_closed_cards(testdir, option, monkeypatch_trello):
    '''Verifies test failure with open and closed trello cards'''

    src = """
        import pytest
        @pytest.mark.trello(*%s)
        def test_func():
            assert False
        """ % ALL_CARDS
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['xfailed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, xfailed=1)


def test_skip_with_open_card(testdir, option, monkeypatch_trello):
    '''Verifies skipping with an open trello card'''

    src = """
        import pytest
        @pytest.mark.trello('%s', skip=True)
        def test_func():
            assert False
        """ % OPEN_CARDS[0]
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == EXIT_OK
    # assert result.parseoutcomes()['skipped'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, skipped=1)


def test_skip_with_closed_card(testdir, option, monkeypatch_trello):
    '''Verifies test failure (skip=True) with a closed trello card'''

    src = """
        import pytest
        @pytest.mark.trello('%s', skip=True)
        def test_func():
            assert False
        """ % CLOSED_CARDS[0]
    # testdir.makepyfile(src)
    # result = testdir.runpytest(*option.args)
    # assert result.ret == 1
    # assert result.parseoutcomes()['failed'] == 1
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, failed=1)


def test_collection_reporter(testdir, option, monkeypatch_trello, capsys):
    '''Verifies trello marker collection'''

    src = """
        import pytest
        @pytest.mark.trello(*%s)
        def test_foo():
            assert True

        @pytest.mark.trello(*%s)
        def test_bar():
            assert False
        """ % (CLOSED_CARDS, OPEN_CARDS)
    # (items, result) = testdir.inline_genitems(src, *option.args)
    result = testdir.inline_runsource(src, *option.args)
    assert_outcome(result, passed=1, xfailed=1)

    stdout, stderr = capsys.readouterr()
    assert 'collected %s trello markers' % (len(CLOSED_CARDS) + len(OPEN_CARDS)) in stdout


def test_show_trello_report_with_no_cards(testdir, option, monkeypatch_trello, capsys):
    '''Verifies when a test succeeds with an open trello card'''

    src = """
        import pytest
        def test_func():
            assert True
        """

    # Run pytest
    args = option.args + ['--show-trello-cards',]
    result = testdir.inline_runsource(src, *args)

    # Assert exit code
    assert result.ret == EXIT_OK

    # Assert no tests ran
    assert_outcome(result)

    # Assert expected trello card report output
    stdout, stderr = capsys.readouterr()
    assert '= trello card report =' in stdout
    assert 'No trello cards collected' in stdout


def test_show_trello_report_with_cards(testdir, option, monkeypatch_trello, capsys):
    '''Verifies when a test succeeds with an open trello card'''

    # Used for later introspection
    cls = 'Test_Foo'
    module = inspect.stack()[0][3]
    method = 'test_func'

    src = """
        import pytest
        class Test_Class():
            @pytest.mark.trello(*%s)
            def test_method():
                assert True

        @pytest.mark.trello(*%s)
        def test_func():
            assert True
        """ % (CLOSED_CARDS, OPEN_CARDS)

    # Run pytest
    args = option.args + ['--show-trello-cards',]
    result = testdir.inline_runsource(src, *args)

    # Assert exit code
    assert result.ret == EXIT_OK

    # Assert no tests ran
    assert_outcome(result)

    # Assert expected trello card report output
    stdout, stderr = capsys.readouterr()

    # Assert expected banner
    assert re.search(r'^={1,} trello card report ={1,}', stdout, re.MULTILINE)

    # Assert expected cards in output
    for card in CLOSED_CARDS:
        assert re.search(r'^%s \[Done\]' % card, stdout, re.MULTILINE)
    for card in OPEN_CARDS:
        assert re.search(r'^%s \[Not Done\]' % card, stdout, re.MULTILINE)

    # this is weird, oh well
    assert ' * {0}0/{0}.py:Test_Class().test_method'.format(module) in stdout
    assert ' * {0}0/{0}.py:test_func'.format(module) in stdout
