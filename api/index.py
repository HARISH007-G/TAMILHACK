import os
import sys

# Ensure project root is in the Python search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app as flask_app


class PathFixerMiddleware:
    """
    WSGI middleware to ensure clean request paths on Vercel Serverless.
    Resolves any /api/index prefixing caused by catch-all rewrites so that
    Flask matches routes like '/', '/atlas', and '/api/atlas/locations' accurately.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Prefer Vercel's original matched path header if provided
        matched_path = environ.get('HTTP_X_MATCHED_PATH') or environ.get('x-matched-path')
        if matched_path:
            environ['PATH_INFO'] = matched_path
        else:
            path = environ.get('PATH_INFO', '')
            if path.startswith('/api/index.py'):
                path = path[len('/api/index.py'):]
            elif path.startswith('/api/index'):
                path = path[len('/api/index'):]

            if not path or path == '':
                path = '/'
            environ['PATH_INFO'] = path

        return self.wsgi_app(environ, start_response)


# Wrap Flask application with path fixer middleware for Vercel deployment
app = PathFixerMiddleware(flask_app)
