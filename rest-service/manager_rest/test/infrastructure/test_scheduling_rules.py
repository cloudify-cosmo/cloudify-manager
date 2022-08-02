from datetime import datetime
from typing import Dict, Any

from manager_rest.utils import get_rrule
from manager_rest.test.base_test import BaseServerTestCase


class SchedulingRulesTest(BaseServerTestCase):
    """ Tests that feeding scheduling rule parameters, together with `since`
        and `until` datetime strings, to utils.get_rrule() - yields us the
        expected scheduled dates.

        Weekdays: 1 Jan 2018 falls on Monday.
    """
    def test_parse_rule_simple(self):
        since = '2018-1-1T00:00:00.000Z'
        until = None
        rule = {
            'recurrence': '2 weeks',
            'count': 5,
            'weekdays': ['MO', 'TU']
        }
        expected_dates = {
            '2018-01-01 00:00:00',
            '2018-01-02 00:00:00',
            '2018-01-15 00:00:00',
            '2018-01-16 00:00:00',
            '2018-01-29 00:00:00',
        }
        self._assert_dates(since, until, rule, 5, expected_dates)

    def test_parse_rule_complex_weekdays(self):
        since = '2018-1-1T00:00:00.000Z'
        until = None
        rule = {
            'recurrence': '2 mo',
            'count': 5,
            'weekdays': ['2MO', '3TU']
        }
        expected_dates = {
            '2018-01-08 00:00:00',
            '2018-01-16 00:00:00',
            '2018-03-12 00:00:00',
            '2018-03-20 00:00:00',
            '2018-05-14 00:00:00',
        }
        self._assert_dates(since, until, rule, 5, expected_dates)

    def test_parse_rule_raw_format(self):
        since = '2018-1-1T00:00:00.000Z'
        until = '2019-1-2T00:00:00.000Z'
        rule = {
            'rrule': 'FREQ=DAILY;INTERVAL=3'
        }
        expected_dates = {
            '2018-01-01 00:00:00',
            '2018-01-04 00:00:00',
            '2018-01-07 00:00:00',
            '2018-12-27 00:00:00',
            '2018-12-30 00:00:00',
            '2019-01-02 00:00:00',
        }
        self._assert_dates(since, until, rule, 123, expected_dates)

    def test_parse_rule_raw_format_overrides_explicit(self):
        since = '2018-1-1T00:00:00.000Z'
        until = '2019-1-2T00:00:00.000Z'
        rule = {
            'recurrence': '1 days',
            'count': 5,
            'rrule': 'FREQ=DAILY;INTERVAL=2;COUNT=6'
        }
        expected_dates = {
            '2018-01-01 00:00:00',
            '2018-01-03 00:00:00',
            '2018-01-05 00:00:00',
        }
        unexpected_dates = {
            '2018-01-02 00:00:00',
            '2018-01-04 00:00:00',
        }
        self._assert_dates(since, until, rule, 6,
                           expected_dates, unexpected_dates)

    def test_parse_rule_no_until_no_count(self):
        since = '2018-1-1T08:00:00.000Z'
        until = None
        rule = {
            'recurrence': '2 months',
            'weekdays': ['MO']      # run on Mondays every other month
        }
        expected_dates = {          # Mondays of odd months
            '2018-01-01 08:00:00',
            '2018-01-08 08:00:00',
            '2018-01-15 08:00:00',
            '2018-03-05 08:00:00',
            '2018-03-12 08:00:00',
            '2035-11-26 08:00:00',
        }
        unexpected_dates = {        # Mondays of even months
            '2018-02-05 08:00:00',
            '2018-02-12 08:00:00',
            '2020-12-07 08:00:00',
        }
        self._assert_dates(since, until, rule, lambda x: x > 10000,
                           expected_dates, unexpected_dates)

    def test_parse_rule_count_trumps_until(self):
        since = '2018-1-1T08:00:00.000Z'
        until = '2018-2-1T08:00:00.000Z'
        rule = {
            'recurrence': '1 days',
            'count': 10
        }
        expected_dates = {
            '2018-01-01 08:00:00',
            '2018-01-02 08:00:00',
            '2018-01-10 08:00:00',
        }
        unexpected_dates = {'2018-01-31 08:00:00'}

        self._assert_dates(since, until, rule, 10, expected_dates,
                           unexpected_dates)

    def test_parse_rule_until_trumps_count(self):
        since = '2018-1-1T08:00:00.000Z'
        until = '2018-2-1T08:00:00.000Z'    # note: `until` is inclusive
        rule = {
            'recurrence': '1 days',
            'count': 1000
        }
        expected_dates = {
            '2018-01-01 08:00:00',
            '2018-01-02 08:00:00',
            '2018-01-10 08:00:00',
        }
        self._assert_dates(since, until, rule, 32, expected_dates)

    def test_parse_rule_no_recurrence_single_run(self):
        since = '2020-3-28T12:30:45.973Z'
        until = '2021-1-1T00:00:00.000Z'
        rule = {
            'count': 1
        }
        expected_dates = {'2020-03-28 12:30:45'}
        self._assert_dates(since, until, rule, 1, expected_dates)

    @staticmethod
    def test_parse_rule_no_recurrence_multiple_runs_invalid():
        since = '2020-3-28T12:30:45.973Z'
        until = '2021-1-1T00:00:00.000Z'
        rule = {
            'count': 2
        }
        assert not get_rrule(rule, since, until)

    @staticmethod
    def test_parse_rule_no_recurrence_weekdays_given_invalid():
        since = '2020-3-28T12:30:45.973Z'
        until = '2021-1-1T00:00:00.000Z'
        rule = {
            'weekdays': ['SU', 'MO']
        }
        assert not get_rrule(rule, since, until)

    def test_parse_rule_ignores_illegal_weekdays(self):
        since = '2018-1-1T08:00:00.000Z'
        until = '2018-2-1T08:00:00.000Z'
        rule = {
            'recurrence': '1 days',
            'weekdays': ['AB', 'PS', 'WE']  # only Wednesdays
        }
        expected_dates = {
            '2018-01-03 08:00:00',
            '2018-01-10 08:00:00',
            '2018-01-17 08:00:00',
            '2018-01-24 08:00:00',
            '2018-01-31 08:00:00',
        }
        self._assert_dates(since, until, rule, 5, expected_dates)

    def test_parse_rule_recurrence_dictates_weekdays(self):
        since = '2018-1-1T08:00:00.000Z'
        until = '2018-2-1T08:00:00.000Z'
        rule = {
            'recurrence': '2 days',      # only odd dates
            'weekdays': ['WE', 'TH']    # only once a week because ^
        }
        expected_dates = {
            '2018-01-03 08:00:00',
            '2018-01-11 08:00:00',
            '2018-01-17 08:00:00',
            '2018-01-25 08:00:00',
            '2018-01-31 08:00:00',
        }
        unexpected_dates = {
            '2018-01-04 08:00:00',
            '2018-01-10 08:00:00',
            '2018-01-18 08:00:00',
            '2018-01-24 08:00:00',
            '2018-02-01 08:00:00',
        }
        self._assert_dates(since, until, rule, 5, expected_dates,
                           unexpected_dates)

    @staticmethod
    def test_parse_rule_empty_invalid():
        since = '2018-1-1T08:00:00.000Z'
        until = '2018-2-1T08:00:00.000Z'
        rule: Dict[str, Any] = {}
        assert not get_rrule(rule, since, until)

    @staticmethod
    def _assert_dates(since, until, rule, expected_num, expected_dates,
                      unexpected_dates=None):
        parsed_rule = get_rrule(rule, since, until)
        parsed_dates = {datetime.strftime(d, '%Y-%m-%d %H:%M:%S') for d
                        in parsed_rule}
        if callable(expected_num):
            assert expected_num(len(parsed_dates))
        else:
            assert expected_num == len(parsed_dates)
        assert expected_dates.issubset(parsed_dates)
        if unexpected_dates:
            assert not unexpected_dates.issubset(parsed_dates)
