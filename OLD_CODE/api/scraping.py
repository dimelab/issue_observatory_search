from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.api import bp
from app.models import Scrape, ScrapedPage, SearchTerms
from app.services import SearchEngineFactory, WebScraper
from app import db
from config import Config
import json
import threading
from datetime import datetime

@bp.route('/scrapes', methods=['GET'])
@login_required
def get_scrapes():
    scrapes = Scrape.query.filter_by(user_id=current_user.id).all()
    if request.is_json:
        return jsonify([{
            'id': s.id,
            'title': s.title,
            'status': s.status,
            'created_at': s.created_at.isoformat(),
            'page_count': len(s.pages)
        } for s in scrapes])
    else:
        return render_template('scrapes.html', scrapes=scrapes)

@bp.route('/scrapes', methods=['POST'])
@login_required
def create_scrape():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    # Create scrape record
    scrape = Scrape(
        title=data.get('title'),
        user_id=current_user.id,
        search_engine=data.get('search_engine', 'google_custom'),
        max_results=int(data.get('max_results', 10)),
        allowed_domains=data.get('allowed_domains', ''),
        scrape_depth=int(data.get('scrape_depth', 1)),
        status='pending'
    )
    
    db.session.add(scrape)
    db.session.commit()
    
    # Get search terms
    search_terms_id = data.get('search_terms_id')
    if search_terms_id:
        search_terms = SearchTerms.query.filter_by(
            id=search_terms_id, 
            user_id=current_user.id
        ).first()
        if search_terms:
            terms = search_terms.get_terms_list()
            # Start scraping in background
            thread = threading.Thread(
                target=_perform_scrape,
                args=(scrape.id, terms, data)
            )
            thread.start()
    
    if request.is_json:
        return jsonify({'success': True, 'scrape_id': scrape.id})
    else:
        flash('Scrape started successfully!', 'success')
        return redirect(url_for('api.get_scrapes'))

@bp.route('/scrapes/<int:scrape_id>', methods=['GET'])
@login_required
def get_scrape(scrape_id):
    scrape = Scrape.query.filter_by(id=scrape_id, user_id=current_user.id).first_or_404()
    
    if request.is_json:
        return jsonify({
            'id': scrape.id,
            'title': scrape.title,
            'status': scrape.status,
            'created_at': scrape.created_at.isoformat(),
            'completed_at': scrape.completed_at.isoformat() if scrape.completed_at else None,
            'pages': [{
                'id': p.id,
                'url': p.url,
                'title': p.title,
                'domain': p.domain,
                'depth_level': p.depth_level
            } for p in scrape.pages]
        })
    else:
        return render_template('scrape_detail.html', scrape=scrape)

@bp.route('/search-terms', methods=['GET'])
@login_required
def get_search_terms():
    terms = SearchTerms.query.filter_by(user_id=current_user.id).all()
    if request.is_json:
        return jsonify([{
            'id': t.id,
            'name': t.name,
            'terms_count': len(t.get_terms_list()),
            'created_at': t.created_at.isoformat()
        } for t in terms])
    else:
        return render_template('search_terms.html', terms=terms)

@bp.route('/search-terms/options', methods=['GET'])
@login_required
def get_search_terms_options():
    terms = SearchTerms.query.filter_by(user_id=current_user.id).all()
    options_html = '<option value="">Select search terms...</option>'
    for term in terms:
        options_html += f'<option value="{term.id}">{term.name} ({len(term.get_terms_list())} terms)</option>'
    return options_html

@bp.route('/search-terms', methods=['POST'])
@login_required
def create_search_terms():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    search_terms = SearchTerms(
        name=data.get('name'),
        user_id=current_user.id,
        terms=data.get('terms', '')
    )
    
    db.session.add(search_terms)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'id': search_terms.id})
    else:
        flash('Search terms saved successfully!', 'success')
        return redirect(url_for('api.get_search_terms'))

def _perform_scrape(scrape_id, search_terms, config_data):
    """Background function to perform scraping"""
    try:
        scrape = Scrape.query.get(scrape_id)
        scrape.status = 'running'
        db.session.commit()
        
        # Setup search engine
        auth_data = Config.get_auth()
        
        if config_data.get('search_engine') == 'google_custom':
            if 'customsearch' in auth_data:
                tokens = auth_data['customsearch']['tokens'][0]
                search_engine = SearchEngineFactory.create_search_engine(
                    'google_custom',
                    api_key=tokens['key'],
                    cx=tokens['cx']
                )
            else:
                raise ValueError("Google Custom Search not configured")
        elif config_data.get('search_engine') == 'serp_api':
            if Config.SERP_API_KEY:
                search_engine = SearchEngineFactory.create_search_engine(
                    'serp_api',
                    api_key=Config.SERP_API_KEY
                )
            else:
                raise ValueError("SERP API not configured")
        else:
            raise ValueError("Invalid search engine")
        
        # Collect all URLs from search terms
        all_urls = []
        max_results = int(config_data.get('max_results', 10))
        
        for term in search_terms:
            results = search_engine.search(term, max_results=max_results)
            all_urls.extend([r['url'] for r in results])
        
        # Remove duplicates
        unique_urls = list(set(all_urls))
        
        # Setup scraper
        scraper = WebScraper(headless=True)
        
        # Parse allowed domains
        allowed_domains = None
        if config_data.get('allowed_domains'):
            allowed_domains = [d.strip() for d in config_data['allowed_domains'].split(',')]
        
        # Scrape with depth
        depth = int(config_data.get('scrape_depth', 1))
        scraped_data = scraper.scrape_with_depth(unique_urls, depth, allowed_domains)
        
        # Save scraped data
        for page_data in scraped_data:
            scraped_page = ScrapedPage(
                scrape_id=scrape_id,
                url=page_data['url'],
                domain=page_data['domain'],
                title=page_data['title'],
                content=page_data['content'],
                depth_level=page_data['depth_level']
            )
            db.session.add(scraped_page)
        
        # Update scrape status
        scrape.status = 'completed'
        scrape.completed_at = datetime.utcnow()
        db.session.commit()
        
        scraper.close()
        
    except Exception as e:
        print(f"Error in scraping: {e}")
        scrape = Scrape.query.get(scrape_id)
        scrape.status = 'failed'
        db.session.commit()