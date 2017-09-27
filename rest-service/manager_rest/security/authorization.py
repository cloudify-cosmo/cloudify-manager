
from functools import wraps

from flask_security import current_user

from manager_rest import config, manager_exceptions


def authorize(action):
    def authorize_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_roles = [current_user.role]
            action_roles = config.instance.authorization_permissions[action]
            for user_role in user_roles:
                if user_role in action_roles:
                    return func(*args, **kwargs)
            raise manager_exceptions.IllegalActionError(
                'User {0} is not permitted to perform the action {1}'.format(
                    current_user.username, action)
            )
        return wrapper
    return authorize_dec
