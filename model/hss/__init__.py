# -*- coding: utf-8 -*-

from flask.ext.babel import gettext
from ..division import Division
import user

__author__ = 'Jan'


division = Division(
    name='hss',
    display_name=gettext(u"Hochschulstraße"),
    user_class=user.User,
    # TODO: Change after init_context is fixed (#52)
    # init_context=hss.init_context,
    debug_only=True
)
