from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    email = request.data.get('email')
    password = request.data.get('password')
    name = request.data.get('name', '')

    if not email or not password:
        return Response({'error': 'Email and password are required'}, status=400)

    if User.objects.filter(username=email).exists():
        return Response({'error': 'Email already exists'}, status=400)

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
    )

    tokens = get_tokens_for_user(user)

    return Response({
        'message': 'User created successfully',
        'tokens': tokens,
        'user': {'email': email, 'name': name},
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Email and password are required'}, status=400)

    user = authenticate(username=email, password=password)

    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    tokens = get_tokens_for_user(user)

    return Response({
        'message': 'Login successful',
        'tokens': tokens,
        'user': {'email': email, 'name': user.first_name},
    })


class AuthRateThrottle(ScopedRateThrottle):
    scope = 'auth'


@api_view(['GET'])
@permission_classes([AllowAny])
def google_config(request):
    """The public Google client ID, so the login page knows whether to show the Google button."""
    return Response({'client_id': settings.GOOGLE_CLIENT_ID or None})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def google_login(request):
    """Sign in with a Google ID token from the browser. The token is checked with Google's public keys:
    signature, expiry, issuer, that it was issued for this app's client ID, and that the email is verified.
    Then the account with that email is used, or created. No Google password ever reaches this server."""
    if not settings.GOOGLE_CLIENT_ID:
        return Response({'error': 'Google sign-in is not set up on this server.'}, status=503)
    credential = request.data.get('credential')
    if not isinstance(credential, str) or not credential or len(credential) > 4096:
        return Response({'error': 'Google sign-in failed. Please try again.'}, status=400)
    try:
        info = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID,
                                            clock_skew_in_seconds=10)
    except ValueError:
        return Response({'error': 'Google sign-in failed. Please try again.'}, status=401)
    if info.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        return Response({'error': 'Google sign-in failed. Please try again.'}, status=401)
    email = (info.get('email') or '').strip().lower()
    if not email or not info.get('email_verified'):
        return Response({'error': 'Your Google account email is not verified.'}, status=401)

    # The same email signed up with a password opens that same account, whatever its capitalisation.
    user = User.objects.filter(username__iexact=email).first() or User.objects.filter(email__iexact=email).first()
    created = False
    if not user:
        user = User(username=email, email=email, first_name=(info.get('given_name') or info.get('name') or '')[:150])
        user.set_unusable_password()  # Google-only account until a password is set
        user.save()
        created = True
    if not user.is_active:
        return Response({'error': 'This account is disabled.'}, status=403)

    return Response({
        'message': 'Account created with Google' if created else 'Login successful',
        'tokens': get_tokens_for_user(user),
        'user': {'email': user.email, 'name': user.first_name},
    }, status=201 if created else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({
        'email': request.user.email,
        'id': request.user.id,
    })
