from app import create_app, db
from app.models import User, Scrape, ScrapedPage, SearchTerms

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Scrape': Scrape,
        'ScrapedPage': ScrapedPage,
        'SearchTerms': SearchTerms
    }

@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)