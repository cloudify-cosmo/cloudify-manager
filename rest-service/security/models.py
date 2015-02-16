# TODO decide on an abstract class, either this or use abc


class RoleModel():

    def __init__(self):
        pass

    def get_name(self):
        raise NotImplementedError


class UserModel():

    def __init__(self):
        pass

    def is_active(self):
        raise NotImplementedError

    def is_anonymous(self):
        raise NotImplementedError

    def get_roles(self):
        raise NotImplementedError