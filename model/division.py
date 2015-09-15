from ipaddress import IPv4Network


def empty_function(app):
    pass


class Division(object):
    """Division object Providing its name and the User object.

    """
    def __init__(self, name, display_name, user_class, mail_server,
                 init_context=empty_function,
                 debug_only=False):
        super(Division, self).__init__()
        self.name = name
        self.display_name = display_name
        self.user_class = user_class
        self.mail_server = mail_server
        self._init_context = init_context
        self.debug_only = debug_only

    def __eq__(self, other):
        return self.name == other.name

    def init_context(self, app):
        return self._init_context(app)


class SubnetCollection(object):
    """A simple class for combining multiple IPv4Networks.

    Provides __contains__ functionality for IPv4Addresses.
    """

    def __init__(self, subnets):
        if type(subnets) == list:
            for subnet in subnets:
                if not isinstance(subnet, IPv4Network):
                    raise TypeError(u"List of IPv4Network objects expected "
                                    "in SubnetCollection.__init__")
        else:
            raise TypeError(u"List expected in SubnetCollection.__init__")

        self.subnets = subnets

    def __contains__(self, address):
        for subnet in self.subnets:
            if address in subnet:
                return True
        return False


class Dormitory:
    """A dormitory as selectable on the login page."""

    def __init__(self, name, display_name, division, subnets=[]):
        self.name = name
        self.display_name = display_name
        self.division = division
        self.subnets = SubnetCollection(subnets)

    def __eq__(self, other):
        return self.name == other.name and self.division == other.division