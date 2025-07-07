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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)