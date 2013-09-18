__author__ = 'idanmo'


from testenv import TestEnvironment as env


def setUp():
    env.create()


def tearDown():
    env.destroy()