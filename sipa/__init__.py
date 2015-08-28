# -*- coding: utf-8 -*-
from functools import wraps
from logging import getLogger, LoggerAdapter

from flask import Flask, flash, redirect
from flask.globals import request

from sipa.utils import current_user_name, redirect_url


class ReverseProxied(object):
    """Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    """
    def __init__(self, flask_app):
        self.app = flask_app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask('sipa')
app.wsgi_app = ReverseProxied(app.wsgi_app)


class CustomAdapter(LoggerAdapter):
    """
    Custom LoggingAdapter to prepend the current unixlogin and IP to the log
    if possible
    """
    def process(self, msg, kwargs):
        extra = kwargs.pop('extra', {})
        tags = extra.pop('tags', {})
        if request:
            login = current_user_name()
            tags['user'] = login
            tags['ip'] = request.remote_addr
            extra['tags'] = tags
            kwargs['extra'] = extra
            if app.config['GENERIC_LOGGING']:
                return msg, kwargs
            else:
                return '{} - {} - {}'.format(
                    request.remote_addr,
                    login,
                    msg), kwargs
        else:
            return msg, kwargs


logger = CustomAdapter(logger=getLogger(name=__name__), extra={})
http_logger = getLogger(name='{}.http'.format(__name__))    # 'sipa.http'


def feature_required(needed_feature, given_features):
    """A decorator used to disable functions (routes) if a certain feature
    is not provided by the User class.

    given_features has to be a callable to ensure runtime distinction
    between divisions.

    :param needed_feature: The feature needed
    :param given_features: A callable returning the set of supported features
    :return:
    """
    def feature_decorator(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if needed_feature in given_features():
                return func(*args, **kwargs)
            else:
                def not_supported():
                    flash(u"Diese Funktion ist nicht verfügbar.", 'error')
                    return redirect(redirect_url())
                return not_supported()

        return decorated_view
    return feature_decorator
