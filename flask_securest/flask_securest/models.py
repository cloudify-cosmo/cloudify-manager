# TODO decide on an abstract class, either this or use abc

NOT_IMPLEMENTED_MESSAGE = '"{0}" not implemented on {1}'


class RoleModel(object):

    def __init__(self):
        pass

    @property
    def name(self):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE
                                  .format('name', get_runtime_class_fqn(self)))


class Role(RoleModel):

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name


class UserModel(object):

    def __init__(self):
        pass

    def is_active(self):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE
                                  .format('is_active',
                                          get_runtime_class_fqn(self)))

    def is_anonymous(self):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE
                                  .format('is_anonymous',
                                          get_runtime_class_fqn(self)))

    def get_roles(self):
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE
                                  .format('get_roles',
                                          get_runtime_class_fqn(self)))


class User(UserModel):

    def __init__(self, username, password, email=None, roles=[], active=True):
        self._username = username
        self._password = password
        self._email = email
        self._roles = roles
        self._active = active

    # Overriding super abstract methods
    def is_active(self):
        return self._active

    def is_anonymous(self):
        return False

    # def get_roles(self):
    #     return (role.name for role in self._roles)

    # additional properties
    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def email(self):
        return self._email


class AnonymousUser(UserModel):
    def is_active(self):
        return False

    def is_anonymous(self):
        return True

    def get_roles(self):
        return []


def get_runtime_class_fqn(instance):
    return type(instance).__module__ + '.' + type(instance).__name__
