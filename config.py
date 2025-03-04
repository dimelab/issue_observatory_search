from os import environ, path
from dotenv import load_dotenv
import dotenv
import json

class Config:

    def __init__(self):

        self.load_env()
        self.set_env()
        self.AUTH = self.get_auth()

    def load_env(self):

        basedir = "/".join(str(path.abspath(path.dirname(__file__)))\
            .split("/")[:-1])
        de_file_path = path.join(basedir+"/issue_observatory_search/config/", '.env')
        load_dotenv(de_file_path)

    def set_env(self):

        self.MAIN_PATH = environ.get('MAIN_PATH')
        self.CUSTOMSEARCH = environ.get('CUSTOMSEARCH')

    def get_auth(self):

        auths = {}
        with open(self.CUSTOMSEARCH) as jloaded:
            auths["customsearch"]=json.load(jloaded)

        return auths
 