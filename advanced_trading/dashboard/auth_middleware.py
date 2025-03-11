"""
Authentication Middleware
----------------------
Middleware for securing the Dash dashboard with the authentication system.
"""

import logging
import os
from functools import wraps
from typing import Callable, Dict, Any, Optional
from flask import request, Response, redirect, session, url_for
import dash
from dash import html, dcc
from dash.exceptions import PreventUpdate

from .auth import get_auth_manager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SESSION_TOKEN_KEY = 'auth_token'
SESSION_USERNAME_KEY = 'username'
SESSION_ROLE_KEY = 'role'
SECRET_KEY = os.environ.get('DASH_SECRET_KEY', 'instinct_ai_dashboard_secret')


def create_login_layout():
    """
    Create the login page layout.
    
    Returns:
        Dash layout for login page
    """
    return html.Div([
        html.Div([
            html.H1('Instinct AI Trading Dashboard', className='login-title'),
            html.Div([
                html.Div([
                    html.H2('Login', className='login-subtitle'),
                    html.Div([
                        html.Label('Username', htmlFor='username-input'),
                        dcc.Input(
                            id='username-input',
                            type='text',
                            placeholder='Enter username',
                            className='login-input'
                        ),
                        html.Label('Password', htmlFor='password-input'),
                        dcc.Input(
                            id='password-input',
                            type='password',
                            placeholder='Enter password',
                            className='login-input'
                        ),
                        html.Button('Login', id='login-button', className='login-button'),
                        html.Div(id='login-error', className='login-error')
                    ], className='login-form')
                ], className='login-card')
            ], className='login-container')
        ], className='login-wrapper')
    ], className='login-page')


def protect_dash_views(app: dash.Dash):
    """
    Protect all Dash views with authentication.
    
    Args:
        app: Dash application instance
    """
    # Set Flask server secret key for sessions
    app.server.secret_key = SECRET_KEY
    
    # Add login manager reference to app
    app.auth_manager = get_auth_manager()
    
    # Modify the index function to handle auth
    @app.server.route('/')
    def index():
        # Check for token in session
        if SESSION_TOKEN_KEY not in session:
            return redirect('/login')
        
        # Check if token is valid
        token = session[SESSION_TOKEN_KEY]
        is_valid, username = app.auth_manager.verify_token(token)
        
        if not is_valid:
            # Clear session and redirect to login
            session.pop(SESSION_TOKEN_KEY, None)
            session.pop(SESSION_USERNAME_KEY, None)
            session.pop(SESSION_ROLE_KEY, None)
            return redirect('/login')
        
        # User is authenticated, serve the index page
        return app.index()
    
    # Add login endpoints
    @app.server.route('/login')
    def login():
        # Check if user is already logged in
        if SESSION_TOKEN_KEY in session:
            token = session[SESSION_TOKEN_KEY]
            is_valid, _ = app.auth_manager.verify_token(token)
            
            if is_valid:
                return redirect('/')
        
        # Render login page
        return app.index()
    
    # Add logout endpoint
    @app.server.route('/logout')
    def logout():
        # Invalidate token if username is in session
        if SESSION_USERNAME_KEY in session:
            app.auth_manager.invalidate_token(session[SESSION_USERNAME_KEY])
        
        # Clear session
        session.pop(SESSION_TOKEN_KEY, None)
        session.pop(SESSION_USERNAME_KEY, None)
        session.pop(SESSION_ROLE_KEY, None)
        
        return redirect('/login')
    
    # Override the index page layout
    original_layout = app.layout
    
    def serve_layout():
        # Check if user is authenticated
        if SESSION_TOKEN_KEY not in session:
            return create_login_layout()
        
        # Check if token is valid
        token = session[SESSION_TOKEN_KEY]
        is_valid, _ = app.auth_manager.verify_token(token)
        
        if not is_valid:
            return create_login_layout()
        
        # User is authenticated, serve the original layout
        return original_layout() if callable(original_layout) else original_layout
    
    app.layout = serve_layout
    
    # Add login callbacks
    @app.callback(
        [dash.dependencies.Output('login-error', 'children'),
         dash.dependencies.Output('url', 'pathname')],
        [dash.dependencies.Input('login-button', 'n_clicks')],
        [dash.dependencies.State('username-input', 'value'),
         dash.dependencies.State('password-input', 'value')]
    )
    def login_callback(n_clicks, username, password):
        """Handle login form submission."""
        # Check if callback was triggered
        if n_clicks is None or n_clicks == 0:
            raise PreventUpdate
        
        # Validate input
        if not username or not password:
            return "Please enter both username and password", dash.no_update
        
        # Authenticate user
        auth_manager = get_auth_manager()
        token = auth_manager.authenticate(username, password)
        
        if token is None:
            return "Invalid username or password", dash.no_update
        
        # Store token in session
        session[SESSION_TOKEN_KEY] = token
        session[SESSION_USERNAME_KEY] = username
        
        # Get user info
        user_info = auth_manager.get_user_info(username)
        if user_info:
            session[SESSION_ROLE_KEY] = user_info.get('role', 'user')
        
        # Redirect to index
        return dash.no_update, "/"
    
    # Add periodic token validation
    @app.callback(
        dash.dependencies.Output('auth-check', 'data'),
        [dash.dependencies.Input('interval-auth-check', 'n_intervals')]
    )
    def check_auth(n_intervals):
        """Periodically check authentication status."""
        if n_intervals is None:
            raise PreventUpdate
        
        # Check if token is in session
        if SESSION_TOKEN_KEY not in session:
            return {'authenticated': False}
        
        # Check if token is valid
        token = session[SESSION_TOKEN_KEY]
        is_valid, _ = app.auth_manager.verify_token(token)
        
        return {'authenticated': is_valid}
    
    # Add token expiry handling
    @app.callback(
        dash.dependencies.Output('url', 'refresh'),
        [dash.dependencies.Input('auth-check', 'data')]
    )
    def handle_auth_expiry(auth_data):
        """Handle authentication expiry."""
        if auth_data is None:
            raise PreventUpdate
        
        # Check if authenticated
        if not auth_data.get('authenticated', False):
            # Force page refresh to redirect to login
            return True
        
        return dash.no_update
    
    # Add hidden div for auth checking
    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='auth-check', data={'authenticated': False}),
        dcc.Interval(
            id='interval-auth-check',
            interval=60*1000,  # Check every minute
            n_intervals=0
        ),
        app.layout() if callable(app.layout) else app.layout
    ])
    
    logger.info("Dashboard views protected with authentication")


def require_roles(roles: list):
    """
    Decorator to require specific roles for Dash callbacks.
    
    Args:
        roles: List of required roles
    
    Returns:
        Decorated callback function
    """
    def decorator(callback):
        @wraps(callback)
        def wrapper(*args, **kwargs):
            # Check if user is authenticated
            if SESSION_TOKEN_KEY not in session:
                raise PreventUpdate
            
            # Check if user has required role
            user_role = session.get(SESSION_ROLE_KEY)
            if user_role not in roles:
                raise PreventUpdate
            
            # Call original callback
            return callback(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get the current user's information.
    
    Returns:
        User information dict or None if not authenticated
    """
    # Check if user is authenticated
    if SESSION_USERNAME_KEY not in session:
        return None
    
    # Get user info
    auth_manager = get_auth_manager()
    return auth_manager.get_user_info(session[SESSION_USERNAME_KEY])


def get_current_username() -> Optional[str]:
    """
    Get the current user's username.
    
    Returns:
        Username or None if not authenticated
    """
    return session.get(SESSION_USERNAME_KEY)


def is_admin() -> bool:
    """
    Check if the current user is an admin.
    
    Returns:
        True if user is admin, False otherwise
    """
    return session.get(SESSION_ROLE_KEY) == 'admin' 