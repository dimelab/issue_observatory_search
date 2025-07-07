from flask import request, jsonify, render_template, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.api import bp
from app.models import Scrape, ScrapedPage
from app.services import NetworkAnalyzer
from app import db
import os
import tempfile
from datetime import datetime

@bp.route('/networks', methods=['GET'])
@login_required
def get_networks():
    scrapes = Scrape.query.filter_by(user_id=current_user.id, status='completed').all()
    if request.is_json:
        return jsonify([{
            'id': s.id,
            'title': s.title,
            'page_count': len(s.pages),
            'created_at': s.created_at.isoformat()
        } for s in scrapes])
    else:
        return render_template('networks.html', scrapes=scrapes)

@bp.route('/networks/create', methods=['POST'])
@login_required
def create_network():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    # Get selected scrapes
    scrape_ids = data.get('scrape_ids', [])
    if isinstance(scrape_ids, str):
        scrape_ids = [int(id.strip()) for id in scrape_ids.split(',')]
    
    # Get scraped pages for selected scrapes
    scraped_pages = []
    for scrape_id in scrape_ids:
        scrape = Scrape.query.filter_by(id=scrape_id, user_id=current_user.id).first()
        if scrape:
            pages_data = [{
                'url': p.url,
                'domain': p.domain,
                'title': p.title,
                'content': p.content,
                'depth_level': p.depth_level
            } for p in scrape.pages]
            scraped_pages.extend(pages_data)
    
    if not scraped_pages:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No valid scrapes found'}), 400
        else:
            flash('No valid scrapes found', 'error')
            return redirect(url_for('api.get_networks'))
    
    # Create network analyzer
    language = data.get('language', 'da_core_news_md')
    analyzer = NetworkAnalyzer(language=language)
    
    # Get network parameters
    top_n_nouns = data.get('top_n_nouns', 10)
    try:
        top_n_nouns = float(top_n_nouns)
        if top_n_nouns > 1:
            top_n_nouns = int(top_n_nouns)
    except ValueError:
        top_n_nouns = 10
    
    # Create bipartite network
    network = analyzer.create_bipartite_network(scraped_pages, top_n_nouns)
    
    if not network:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Failed to create network'}), 500
        else:
            flash('Failed to create network', 'error')
            return redirect(url_for('api.get_networks'))
    
    # Get network statistics
    stats = analyzer.get_network_stats(network)
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"network_{timestamp}.gexf"
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    
    # Export network
    success = analyzer.export_network_to_gexf(network, filepath)
    
    if success:
        if request.is_json:
            return jsonify({
                'success': True,
                'filename': filename,
                'stats': stats,
                'download_url': f'/api/networks/download/{filename}'
            })
        else:
            return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Failed to export network'}), 500
        else:
            flash('Failed to export network', 'error')
            return redirect(url_for('api.get_networks'))

@bp.route('/networks/download/<filename>')
@login_required
def download_network(filename):
    """Download network file"""
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        return jsonify({'error': 'File not found'}), 404

@bp.route('/networks/form')
@login_required
def network_form():
    """Show network creation form"""
    scrapes = Scrape.query.filter_by(user_id=current_user.id, status='completed').all()
    return render_template('network_form.html', scrapes=scrapes)