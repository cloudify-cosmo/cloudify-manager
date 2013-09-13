__author__ = 'elip'

import unittest
from test import update_cosmo_jar
from test import get_remote_runner, REMOTE_WORKING_DIR


class ValidateDSLTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_remote_runner()
        # dont use the retry mechanism for these tests
        cls.RUNNER.max_retries = 0
        # update_cosmo_jar(cls.RUNNER)

    def test_valid(self):

        self.RUNNER.run("{0}/cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml --validate"
                        .format(REMOTE_WORKING_DIR))

    def test_invalid(self):

        try:
            self.RUNNER.run("{0}/cosmo.sh --dsl=/vagrant/test/corrupted_dsl/dsl-with-invalid-plans1.yaml --validate"
                            .format(REMOTE_WORKING_DIR))
            self.fail("Expected validation exception but none occurred")
        except BaseException:
            pass


if __name__ == '__main__':
    unittest.main()