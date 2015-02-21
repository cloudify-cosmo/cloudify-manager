import argparse
from os import path
from ConfigParser import ConfigParser

from nose.loader import TestLoader
from nose.suite import ContextSuite
from nose.case import Test


def extract_tests(tests_dir):
    def _extract(suite):
        result = []
        for item in suite:
            if isinstance(item, ContextSuite):
                result += _extract(item)
            elif isinstance(item, Test):
                result.append(item)
            else:
                raise RuntimeError('Unhandled type: {0}'.format(item))
        return result
    tests = _extract(TestLoader().loadTestsFromDir(tests_dir))
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
    return suites


def write_config(suite, config_path):
    config = ConfigParser()
    section = 'nosetests'
    config.add_section(section)
    config.set(section, 'tests', ','.join(suite))
    with open(path.expanduser(config_path), 'w') as f:
        config.write(f)


def create_test_config(number_of_suites,
                       suite_number,
                       tests_dir,
                       config_path):
    tests = extract_tests(tests_dir)
    suites = build_suites(tests, number_of_suites)
    assert tests == [test for suite in suites for test in suite]
    write_config(suites[suite_number], config_path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--number-of-suites', default=1, type=int)
    parser.add_argument('--suite-number',     default=0, type=int)
    parser.add_argument('--config-path',      default='nose.config')
    parser.add_argument('--tests-dir',        default='workflow_tests')
    return parser.parse_args()


def main():
    create_test_config(**vars(parse_args()))

if __name__ == '__main__':
    main()
