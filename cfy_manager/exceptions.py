class BootstrapError(StandardError):
    pass


class FileError(BootstrapError):
    pass


class NetworkError(BootstrapError):
    pass


class ValidationError(BootstrapError):
    pass


class InputError(BootstrapError):
    pass
