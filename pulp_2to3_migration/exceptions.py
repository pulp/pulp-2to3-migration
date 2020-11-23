from pulpcore.plugin.exceptions import PulpException


class ConfigurationError(PulpException):
    """
    Missing or wrong configuration exception.

    Exception that is raised when a necessary configuration parameters are not specified,
    of a wrong type, or conflicting.
    """

    def __init__(self, msg):
        """
        :param msg: error message specifying what exactly is out of place
        :type msg: str
        """
        super().__init__("PLP_2TO3_0001")
        self.msg = msg

    def __str__(self):
        return self.msg


class PlanValidationError(Exception):
    """
    Exception to be thrown when validating the MigrationPlan.

    e.g. Repository specified does not exist.
    """
    pass


class ArtifactValidationError(PulpException):
    """
    Exception for the issues with artifact creation during migration.

    """
    def __init__(self, msg):
        """
        :param msg: error message specifying what exactly is out of place
        :type msg: str
        """
        super().__init__("PLP_2TO3_0003")
        self.msg = msg

    def __str__(self):
        return self.msg
