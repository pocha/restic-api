from flask import Flask
from flask_cors import CORS
import os
import sys

def create_app():

    app = Flask(__name__)
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    CORS(app)
    return app

app = create_app()
