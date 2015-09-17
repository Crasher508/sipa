#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Blueprint for Usersuite components
"""

from flask import Blueprint, render_template, url_for, redirect, flash
from flask.ext.babel import gettext
from flask.ext.login import current_user, login_required

from model import current_user_supported, current_datasource
from model.constants import unsupported_property, ACTIONS
from sipa import feature_required
from sipa.forms import ContactForm, ChangeMACForm, ChangeMailForm, \
    ChangePasswordForm, flash_formerrors, HostingForm, DeleteMailForm
from sipa.utils.mail_utils import send_mail
from sipa.utils.exceptions import DBQueryEmpty, LDAPConnectionError, \
    PasswordInvalid, UserNotFound

from collections import OrderedDict

import logging
logger = logging.getLogger(__name__)

bp_usersuite = Blueprint('usersuite', __name__, url_prefix='/usersuite')


@bp_usersuite.route("/")
@login_required
def usersuite():
    """Usersuite landing page with user account information
    and traffic overview.
    """
    try:
        user_info = dict(current_user.get_information())
        traffic_data = current_user.get_traffic_data()
    except DBQueryEmpty as e:
        logger.error('Userinfo DB query could not be finished',
                     extra={'data': {'exception_args': e.args}, 'stack': True})
        flash(gettext("Es gab einen Fehler bei der Datenbankanfrage!"),
              "error")
        return redirect(url_for('generic.index'))

    user_info.update({prop: unsupported_property()
                      for prop in current_user.unsupported(display=True)})

    descriptions = OrderedDict([
        ('id', gettext("Nutzer-ID")),
        ('uid', gettext("Accountname")),
        ('status', gettext("Accountstatus")),
        ('address', gettext("Aktuelles Zimmer")),
        ('ip', gettext("Aktuelle IP-Adresse")),
        ('mac', gettext("Aktuelle MAC-Adresse")),
        ('mail', gettext("E-Mail-Weiterleitung")),
        ('hostname', gettext("Hostname")),
        ('hostalias', gettext("Hostalias")),
        ('userdb', gettext("MySQL Datenbank")),
    ])

    ordered_user_info = OrderedDict()
    for key, description in descriptions.items():
        if key in user_info:
            ordered_user_info[key] = user_info[key]
            ordered_user_info[key]['description'] = descriptions[key]

    # set {mail,mac,userdb}_{change,delete} urls
    if 'mail_change' in current_user.supported():
        ordered_user_info['mail']['action_links'] = {
            ACTIONS.EDIT: url_for('.usersuite_change_mail'),
            ACTIONS.DELETE: url_for('.usersuite_delete_mail')
        }
    if 'mac_change' in current_user.supported():
        ordered_user_info['mac']['action_links'] = {
            ACTIONS.EDIT: url_for('.usersuite_change_mac')
        }
    if 'userdb_change' in current_user.supported():
        ordered_user_info['userdb']['action_links'] = {
            ACTIONS.EDIT: url_for('.usersuite_hosting')
        }

    return render_template("usersuite/index.html",
                           userinfo=ordered_user_info,
                           usertraffic=traffic_data)


@bp_usersuite.route("/contact", methods=['GET', 'POST'])
@login_required
def usersuite_contact():
    """Contact form for logged in users.
    Currently sends an e-mail to the support mailing list as
    '[Usersuite] Category: Subject' with userid and message.
    """
    form = ContactForm()

    support_mail = current_datasource().support_mail
    from_mail = "{}@{}".format(current_user.uid,
                               current_datasource().mail_server)

    if form.validate_on_submit():
        types = {
            'stoerung': "Störung",
            'finanzen': "Finanzen",
            'eigene-technik': "Eigene Technik"
        }

        cat = types.get(form.type.data, "Allgemein")

        subject = "[Usersuite] {0}: {1}".format(cat, form.subject.data)

        message_text = "Nutzerlogin: {0}\n\n".format(current_user.uid) \
                       + form.message.data

        if send_mail(from_mail, support_mail, subject, message_text):
            flash(gettext("Nachricht wurde versandt."), "success")
        else:
            flash(gettext("Es gab einen Fehler beim Versenden der Nachricht. "
                          "Bitte schicke uns direkt eine E-Mail an {}".format(
                              support_mail)),
                  'error')
        return redirect(url_for(".usersuite"))
    elif form.is_submitted():
        flash_formerrors(form)

    form.email.default = from_mail

    return render_template("usersuite/contact.html", form=form)


@bp_usersuite.route("/change-password", methods=['GET', 'POST'])
@login_required
@feature_required('password_change', current_user_supported)
def usersuite_change_password():
    """Lets the user change his password.
    Requests the old password once (in case someone forgot to logout for
    example) and the new password two times.

    If the new password was entered correctly twice, LDAP performs a bind
    with the old credentials at the users DN and submits the passwords to
    modify_password(). This way each user can edit only his own data.

    Error code "-1" is an incorrect old or empty password.

    TODO: set a minimum character limit for new passwords.
    """
    form = ChangePasswordForm()

    if form.validate_on_submit():
        old = form.old.data
        new = form.new.data

        try:
            current_user.re_authenticate(old)
            current_user.change_password(old, new)
        except PasswordInvalid:
            flash(gettext("Altes Passwort war inkorrekt!"), "error")
        else:
            flash(gettext("Passwort wurde geändert"), "success")
            return redirect(url_for(".usersuite"))
    elif form.is_submitted():
        flash_formerrors(form)

    return render_template("usersuite/change_password.html", form=form)


@bp_usersuite.route("/change-mail", methods=['GET', 'POST'])
@login_required
@feature_required('mail_change', current_user_supported)
def usersuite_change_mail():
    """Changes the users forwarding mail attribute
    in his LDAP entry.

    TODO: LDAP schema forbids add/replace 'mail' attribute
    """
    form = ChangeMailForm()

    if form.validate_on_submit():
        password = form.password.data
        email = form.email.data

        try:
            current_user.re_authenticate(password)
            current_user.change_mail(password, email)
        except UserNotFound:
            flash(gettext("Nutzer nicht gefunden!"), "error")
        except PasswordInvalid:
            flash(gettext("Passwort war inkorrekt!"), "error")
        except LDAPConnectionError:
            flash(gettext("Nicht genügend LDAP-Rechte!"), "error")
        else:
            flash(gettext("E-Mail-Adresse wurde geändert"), "success")
            return redirect(url_for('.usersuite'))
    elif form.is_submitted():
        flash_formerrors(form)

    return render_template('usersuite/change_mail.html', form=form)


@bp_usersuite.route("/delete-mail", methods=['GET', 'POST'])
@login_required
@feature_required('mail_change', current_user_supported)
def usersuite_delete_mail():
    """Resets the users forwarding mail attribute
    in his LDAP entry.
    """
    form = DeleteMailForm()

    if form.validate_on_submit():
        password = form.password.data

        try:
            current_user.re_authenticate(password)
            # password is needed for the ldap bind
            current_user.change_mail(password, "")
        except UserNotFound:
            flash(gettext("Nutzer nicht gefunden!"), "error")
        except PasswordInvalid:
            flash(gettext("Passwort war inkorrekt!"), "error")
        except LDAPConnectionError:
            flash(gettext("Nicht genügend LDAP-Rechte!"), "error")
        else:
            flash(gettext("E-Mail-Adresse wurde zurückgesetzt"), "success")
            return redirect(url_for('.usersuite'))
    elif form.is_submitted():
        flash_formerrors(form)

    return render_template('usersuite/delete_mail.html', form=form)


@bp_usersuite.route("/change-mac", methods=['GET', 'POST'])
@login_required
@feature_required('mac_change', current_user_supported)
def usersuite_change_mac():
    """As user, change the MAC address of your device.
    """
    form = ChangeMACForm()
    userinfo = current_user.get_information()

    if form.validate_on_submit():
        password = form.password.data
        mac = form.mac.data

        try:
            current_user.re_authenticate(password)

        except PasswordInvalid:
            flash(gettext("Passwort war inkorrekt!"), "error")
        else:
            current_user.change_mac_address(userinfo['ip'],
                                            userinfo['mac'],
                                            mac)
            logger.info('Successfully changed MAC address to %s', mac)

            from_mail = "{}@{}".format(current_user.uid,
                                       current_datasource().mail_server)
            support_mail = current_datasource().support_mail

            subject = ("[Usersuite] {} hat seine/ihre MAC-Adresse "
                       "geändert".format(current_user.uid))
            message = (
                "Nutzer {name} ({uid}) hat seine/ihre MAC-Adresse geändert."
                "\nAlte MAC: {old_mac}\nNeue MAC: {new_mac}".format(
                    name=current_user.name,
                    uid=current_user.uid,
                    old_mac=userinfo['mac'],
                    new_mac=mac
                )
            )

            if send_mail(from_mail, support_mail, subject, message):
                flash(gettext("MAC-Adresse wurde geändert!"), "success")
                return redirect(url_for('.usersuite'))
            else:
                flash(gettext(
                    "Es gab einen Fehler beim Versenden der Nachricht. "
                    "Bitte schicke uns direkt eine E-Mail "
                    "an support@wh2.tu-dresden.de"),
                    'error'
                )
                return redirect(url_for('.usersuite'))
    elif form.is_submitted():
        flash_formerrors(form)

    form.mac.default = userinfo['mac']['value']

    return render_template('usersuite/change_mac.html', form=form)


@bp_usersuite.route("/hosting", methods=['GET', 'POST'])
@bp_usersuite.route("/hosting/<string:action>", methods=['GET', 'POST'])
@login_required
@feature_required('userdb_change', current_user_supported)
def usersuite_hosting(action=None):
    """Change various settings for Helios.
    """
    if action == "confirm":
        current_user.user_db_drop()
        flash(gettext("Deine Datenbank wurde gelöscht."), 'success')
        return redirect(url_for('.usersuite_hosting'))

    form = HostingForm()

    if form.validate_on_submit():
        if form.action.data == "create":
            current_user.user_db_create(form.password.data)
            flash(gettext("Deine Datenbank wurde erstellt."), 'success')
        else:
            current_user.user_db_password_change(form.password.data)
    elif form.is_submitted():
        flash_formerrors(form)

    user_has_db = current_user.has_user_db()

    return render_template('usersuite/hosting.html',
                           form=form, user_has_db=user_has_db, action=action)
