from itertools import permutations
from unittest import TestCase
from unittest.mock import MagicMock, patch

from flask.ext.login import AnonymousUserMixin
from sqlalchemy.orm.exc import NoResultFound

from sipa.model.wu.user import User, UserDB
from sipa.model.wu.ldap_utils import UserNotFound, PasswordInvalid


class UserNoDBTestCase(TestCase):
    userdb_mock = MagicMock()

    def setUp(self):
        self.userdb_mock.reset_mock()

    def assert_userdata_passed(self, user, user_dict):
        self.assertEqual(user.name, user_dict['name'])
        self.assertEqual(user.group, user_dict.get('group', 'passive'))
        self.assertEqual(user.mail.value, user_dict['mail'])

    @staticmethod
    def patch_user_group(user_dict):
        return patch(
            'sipa.model.wu.user.User.define_group',
            MagicMock(return_value=user_dict.get('group', 'passive'))
        )

    @patch('sipa.model.wu.user.UserDB', userdb_mock)
    def test_explicit_init(self):
        sample_user = {
            'uid': 'testnutzer',
            'name': "Test Nutzer",
            'mail': "test@nutzer.de",
            'group': 'passive',
        }

        with self.patch_user_group(sample_user):
            user = User(
                uid=sample_user['uid'],
                name=sample_user['name'],
                mail=sample_user['mail'],
            )

        self.assert_userdata_passed(user, sample_user)
        assert self.userdb_mock.called

    @patch('sipa.model.wu.user.UserDB', userdb_mock)
    def test_define_group(self):
        sample_users = {
            # <uid>: <resulting_group>
            'uid1': 'passive',
            'uid2': 'active',
            'uid3': 'exactive',
        }

        def fake_search_in_group(uid, group_string):
            if group_string == "Aktiv":
                return sample_users[uid] == 'active'
            elif group_string == "Exaktiv":
                return sample_users[uid] == 'exactive'
            else:
                raise NotImplementedError

        for uid, group in sample_users.items():
            with patch('sipa.model.wu.user.search_in_group',
                       fake_search_in_group):
                user = User(uid=uid, name="", mail="")
                self.assertEqual(user.define_group(), group)
        return

    @patch('sipa.model.wu.user.UserDB', userdb_mock)
    def test_get_constructor(self):
        test_users = [
            {'uid': "uid1", 'name': "Name Eins", 'mail': "test@foo.bar"},
            {'uid': "uid2", 'name': "Mareike Musterfrau", 'mail': "test@foo.baz"},
            {'uid': "uid3", 'name': "Deine Mutter", 'mail': "shizzle@damn.onion"},
        ]

        for test_user in test_users:
            with self.patch_user_group(test_user), \
                 patch('sipa.model.wu.user.LdapConnector') as LdapConnectorMock:
                    LdapConnectorMock.fetch_user.return_value = test_user

                    user = User.get(test_user['uid'])
                    assert LdapConnectorMock.fetch_user.called

            self.assertIsInstance(user, User)
            self.assert_userdata_passed(user, test_user)

    def test_get_constructor_returns_anonymous(self):
        with patch('sipa.model.wu.user.LdapConnector') as LdapConnectorMock:
            LdapConnectorMock.fetch_user.return_value = None
            user = User.authenticate("foo", "bar")
        self.assertIsInstance(user, AnonymousUserMixin)

    def test_authentication_passing(self):
        """Test correct instanciation behaviour of `User.authenticate`.

        It is checked whether the ldap is called correctly and
        instanciation is done using `User.get`.
        """
        sample_users = [
            ("uid", "pass"),
            ("foo", "bar"),
            ("baz", None),
        ]
        for uid, password in sample_users:
            with patch('sipa.model.wu.user.LdapConnector') as ldap_mock, \
                 patch('sipa.model.wu.user.User.get') as get_mock:
                User.authenticate(uid, password)

                self.assertEqual(ldap_mock.call_args[0], (uid, password))
                self.assertEqual(get_mock.call_args[0], (uid,))

    def test_authentication_reraise_unknown_user(self):
        """Test that certain exceptions are re-raised by `User.authenticate`.

        Objects of interest are `UserNotFound`, `PasswordInvalid`.
        """
        for exception_class in [UserNotFound, PasswordInvalid]:
            def raise_exception(): raise exception_class()
            with patch('sipa.model.wu.user.LdapConnector') as ldap_mock:
                ldap_mock().__enter__.side_effect = raise_exception
                with self.assertRaises(exception_class):
                    User.authenticate(username=None, password=None)

    def test_from_ip_returns_anonymous(self):
        def raise_noresult(*a, **kw): raise NoResultFound
        with patch('sipa.model.wu.user.db') as db_mock:
            db_mock.session.query.side_effect = raise_noresult
            user = User.from_ip(ip=None)
            self.assertIsInstance(user, AnonymousUserMixin)

    # TODO: Comprehensively test `from_ip` testing with sample database
    # e.g. test that the correct status coder have been used in the filter


class UserDBTestCase(TestCase):
    def test_ipmask_validity_checker(self):
        valid_elements = ['1', '125', '255', '%']
        valid = permutations(valid_elements, 4)

        # probably not the most elegant choices, but that should do the trick
        invalid_elements = ['%%', '%%%', '1%1', '1%%1']
        invalid = []
        for p in valid:
            p = list(p)
            for inv in invalid_elements:
                invalid += [p[:i] + [inv] + p[i+1:] for i in range(4)]

        for ip_tuple in invalid:
            with self.assertRaises(ValueError):
                UserDB.test_ipmask_validity(".".join(ip_tuple))

        for ip_tuple in valid:
            with self.assertNotRaises(ValueError):
                UserDB.test_ipmask_validity(".".join(ip_tuple))