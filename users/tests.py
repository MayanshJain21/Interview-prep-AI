from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

CLIENT_ID = 'test-client.apps.googleusercontent.com'


def google_info(**overrides):
    info = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'email': 'Asha.Rao@gmail.com',
            'email_verified': True, 'given_name': 'Asha', 'name': 'Asha Rao'}
    info.update(overrides)
    return info


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID)
class GoogleLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def post(self, info=None, error=None):
        with patch('users.views.id_token.verify_oauth2_token') as verify:
            if error:
                verify.side_effect = error
            else:
                verify.return_value = info or google_info()
            res = self.api.post('/api/auth/google/', {'credential': 'header.payload.signature'}, format='json')
        return res, verify

    def test_config_exposes_only_the_public_client_id(self):
        self.assertEqual(self.api.get('/api/auth/google/config/').data, {'client_id': CLIENT_ID})
        with override_settings(GOOGLE_CLIENT_ID=''):
            self.assertEqual(self.api.get('/api/auth/google/config/').data, {'client_id': None})

    def test_new_google_user_gets_an_account_and_a_token(self):
        res, verify = self.post()
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data['tokens'])
        user = User.objects.get(username='asha.rao@gmail.com')
        self.assertEqual((user.email, user.first_name), ('asha.rao@gmail.com', 'Asha'))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(verify.call_args[0][2], CLIENT_ID)  # checked against this app's client ID
        # Signing in again opens the same account.
        res, _ = self.post()
        self.assertEqual((res.status_code, User.objects.count()), (200, 1))

    def test_existing_password_account_is_reused_whatever_the_capitalisation(self):
        User.objects.create_user(username='Asha.Rao@gmail.com', email='Asha.Rao@gmail.com', password='pw12345678')
        res, _ = self.post()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        # The password login still works too.
        login = self.api.post('/api/auth/login/', {'email': 'Asha.Rao@gmail.com', 'password': 'pw12345678'}, format='json')
        self.assertEqual(login.status_code, 200)

    def test_rejects_bad_tokens_wrong_issuer_and_unverified_email(self):
        self.assertEqual(self.post(error=ValueError('Token expired'))[0].status_code, 401)
        self.assertEqual(self.post(google_info(iss='https://evil.example'))[0].status_code, 401)
        self.assertEqual(self.post(google_info(email_verified=False))[0].status_code, 401)
        self.assertEqual(self.api.post('/api/auth/google/', {}, format='json').status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_not_configured(self):
        with override_settings(GOOGLE_CLIENT_ID=''):
            self.assertEqual(self.post()[0].status_code, 503)

    def test_google_only_account_cannot_log_in_with_an_empty_password(self):
        self.post()
        res = self.api.post('/api/auth/login/', {'email': 'asha.rao@gmail.com', 'password': ''}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.api.post('/api/auth/login/', {'email': 'asha.rao@gmail.com', 'password': 'guess'}, format='json')
        self.assertEqual(res.status_code, 401)
