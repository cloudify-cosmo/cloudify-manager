import argparse
from os import path
from ConfigParser import ConfigParser

from nose.loader import TestLoader
from nose.suite import ContextSuite
from nose.case import Test


def extract_tests(tests_dir):
    tests = []

    def _extract(suite):
        for item in suite:
            if isinstance(item, ContextSuite):
                _extract(item)
            elif isinstance(item, Test):
                tests.append(item)
            else:
                raise RuntimeError('Unhandled type: {0}'.format(item))
    _extract(TestLoader().loadTestsFromDir(tests_dir))
    return ['{0}:{1}.{2}'.format(test.test.__module__,
                                 type(test.test).__name__,
                                 test.test._testMethodName) for test in tests]


def build_suites(tests, number_of_suites):
    number_of_tests = len(tests)
    number_of_suite_tests, remainder = divmod(number_of_tests,
                                              number_of_suites)
    offset = 0
    suites = []
    for i in range(number_of_suites):
        start = offset + i * number_of_suite_tests
        end = offset + i * number_of_suite_tests + number_of_suite_tests
        if remainder:
            offset += 1
            end += 1
            remainder -= 1
        suites.append(tests[start:end])
    # sanity
    assert [t for s in suites for t in s] == tests
    return suites


def write_config(suite, config_path):
    config = ConfigParser()
    config.add_section('nosetests')
    config.set('nosetests', 'tests', ','.join(suite))
    with open(path.expanduser(config_path), 'w') as f:
        config.write(f)


def create_test_config(tests_dir,
                       number_of_suites,
                       suite_number,
                       config_path):
    tests = extract_tests(tests_dir)
    suites = build_suites(tests, number_of_suites)
    write_config(suites[suite_number], config_path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-path', default='nose.config')
    parser.add_argument('--suite-number', default=0, type=int)
    parser.add_argument('--tests-dir', default='workflow_tests')
    parser.add_argument('--number-of-suites', default=1, type=int)
    return parser.parse_args()


def main():
    args = parse_args()
    create_test_config(
        tests_dir=args.tests_dir,
        number_of_suites=args.number_of_suites,
        suite_number=args.suite_number,
        config_path=args.config_path)

if __name__ == '__main__':
    main()
