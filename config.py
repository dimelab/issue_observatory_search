from os import environ, path
from dotenv import load_dotenv
import json

# Load environment variables at module level
basedir = path.abspath(path.dirname(__file__))
de_file_path = path.join(basedir, 'config', '.env')
load_dotenv(de_file_path)

class Config:
    # Flask configuration as class attributes
    SECRET_KEY = environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = environ.get('DATABASE_URL', 'sqlite:///issue_observatory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Custom application configuration
    MAIN_PATH = environ.get('MAIN_PATH')
    CUSTOMSEARCH = environ.get('CUSTOMSEARCH')
    SERP_API_KEY = environ.get('SERP_API_KEY')
    
    @classmethod
    def get_auth(cls):
        auths = {}
        if cls.CUSTOMSEARCH:
            try:
                with open(cls.CUSTOMSEARCH) as jloaded:
                    auths["customsearch"] = json.load(jloaded)
            except FileNotFoundError:
                print(f"Warning: Custom search keys file not found at {cls.CUSTOMSEARCH}")
        return auths
 