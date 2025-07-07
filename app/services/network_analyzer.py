import networkx as nx
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import defaultdict
import spacy
import re
from urllib.parse import urlparse
import os

class NetworkAnalyzer:
    def __init__(self, language='da_core_news_md'):
        self.language = language
        self.nlp = None
        self._load_nlp_model()
    
    def _load_nlp_model(self):
        """Load the spaCy language model"""
        try:
            self.nlp = spacy.load(self.language)
        except OSError:
            print(f"Language model {self.language} not found. Using English model.")
            self.nlp = spacy.load('en_core_web_sm')
    
    def create_bipartite_network(self, scraped_pages, top_n_nouns=10):
        """
        Create a bipartite network with websites and nouns as nodes
        
        Args:
            scraped_pages: List of scraped page data
            top_n_nouns: Number of top nouns to include per website (int or float < 1)
        """
        if not scraped_pages:
            return None
        
        # Extract nouns from each page
        website_nouns = self._extract_nouns_from_pages(scraped_pages)
        
        # Calculate TF-IDF scores
        tfidf_scores = self._calculate_tfidf_scores(website_nouns)
        
        # Create network
        G = nx.Graph()
        
        for i, (domain, nouns) in enumerate(website_nouns.items()):
            # Add website node
            G.add_node(domain, node_type='website', bipartite=0)
            
            # Get top nouns for this website
            if i < len(tfidf_scores):
                scores = tfidf_scores[i]
                top_nouns = self._get_top_nouns(scores, top_n_nouns)
                
                for noun, score in top_nouns:
                    # Add noun node if it doesn't exist
                    if not G.has_node(noun):
                        G.add_node(noun, node_type='noun', bipartite=1)
                    
                    # Add edge with TF-IDF score as weight
                    G.add_edge(domain, noun, weight=score)
        
        return G
    
    def _extract_nouns_from_pages(self, scraped_pages):
        """Extract nouns from scraped pages grouped by domain"""
        website_nouns = defaultdict(list)
        
        for page in scraped_pages:
            domain = self._clean_domain(page.get('domain', ''))
            content = page.get('content', '')
            
            if content and domain:
                nouns = self._extract_nouns_from_text(content)
                website_nouns[domain].extend(nouns)
        
        return dict(website_nouns)
    
    def _extract_nouns_from_text(self, text):
        """Extract nouns from text using spaCy"""
        if not self.nlp:
            return []
        
        # Clean text
        text = self._clean_text(text)
        
        # Process with spaCy
        doc = self.nlp(text)
        
        # Extract nouns (lemmatized)
        nouns = []
        for token in doc:
            if (token.pos_ == "NOUN" and 
                len(token.lemma_) > 2 and 
                token.lemma_.isalpha() and
                not token.is_stop):
                nouns.append(token.lemma_.lower())
        
        return nouns
    
    def _clean_text(self, text):
        """Clean text for processing"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _clean_domain(self, domain):
        """Clean domain name"""
        if not domain:
            return ""
        
        # Remove www. prefix
        domain = domain.replace('www.', '')
        return domain
    
    def _calculate_tfidf_scores(self, website_nouns):
        """Calculate TF-IDF scores for nouns across websites"""
        if not website_nouns:
            return []
        
        # Create documents (one per website)
        documents = []
        for domain, nouns in website_nouns.items():
            documents.append(' '.join(nouns))
        
        # Calculate TF-IDF
        vectorizer = TfidfVectorizer(max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(documents)
        feature_names = vectorizer.get_feature_names_out()
        
        # Convert to scores per document
        tfidf_scores = []
        for i in range(tfidf_matrix.shape[0]):
            doc_scores = {}
            feature_index = tfidf_matrix[i, :].nonzero()[1]
            for j in feature_index:
                doc_scores[feature_names[j]] = tfidf_matrix[i, j]
            tfidf_scores.append(doc_scores)
        
        return tfidf_scores
    
    def _get_top_nouns(self, scores, top_n):
        """Get top N nouns based on TF-IDF scores"""
        if not scores:
            return []
        
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        if isinstance(top_n, float) and top_n < 1:
            # Get top proportion
            n = max(1, int(len(sorted_scores) * top_n))
        else:
            # Get top N
            n = min(top_n, len(sorted_scores))
        
        return sorted_scores[:n]
    
    def export_network_to_gexf(self, network, filepath):
        """Export network to GEXF format"""
        if not network:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Write GEXF file
            nx.write_gexf(network, filepath)
            return True
        except Exception as e:
            print(f"Error exporting network: {e}")
            return False
    
    def get_network_stats(self, network):
        """Get basic network statistics"""
        if not network:
            return {}
        
        stats = {
            'nodes': network.number_of_nodes(),
            'edges': network.number_of_edges(),
            'website_nodes': len([n for n, d in network.nodes(data=True) if d.get('node_type') == 'website']),
            'noun_nodes': len([n for n, d in network.nodes(data=True) if d.get('node_type') == 'noun']),
            'density': nx.density(network),
            'is_bipartite': nx.is_bipartite(network)
        }
        
        return stats