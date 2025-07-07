from abc import ABC, abstractmethod
import requests
import json
import serpapi

class SearchEngineBase(ABC):
    @abstractmethod
    def search(self, query, max_results=10, **kwargs):
        pass

class GoogleCustomSearch(SearchEngineBase):
    def __init__(self, api_key, cx):
        self.api_key = api_key
        self.cx = cx
        self.base_url = "https://customsearch.googleapis.com/customsearch/v1"
    
    def search(self, query, max_results=10, **kwargs):
        results = []
        start_index = 1
        
        while len(results) < max_results:
            params = {
                'key': self.api_key,
                'cx': self.cx,
                'q': query,
                'start': start_index,
                'num': min(10, max_results - len(results))
            }
            
            try:
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'items' in data:
                    for item in data['items']:
                        results.append({
                            'title': item.get('title', ''),
                            'url': item.get('link', ''),
                            'snippet': item.get('snippet', '')
                        })
                else:
                    break
                
                start_index += 10
            except requests.RequestException as e:
                print(f"Error in Google Custom Search: {e}")
                break
        
        return results[:max_results]

class SerpAPISearch(SearchEngineBase):
    def __init__(self, api_key):
        self.api_key = api_key
    
    def search(self, query, max_results=10, **kwargs):
        results = []
        
        try:
            client = serpapi.Client(api_key=self.api_key)
            search_results = client.search({
                "q": query,
                "num": min(100, max_results),
                "engine": "google"
            })
            
            if 'organic_results' in search_results:
                for result in search_results['organic_results'][:max_results]:
                    results.append({
                        'title': result.get('title', ''),
                        'url': result.get('link', ''),
                        'snippet': result.get('snippet', '')
                    })
        except Exception as e:
            print(f"Error in SERP API Search: {e}")
        
        return results

class SearchEngineFactory:
    @staticmethod
    def create_search_engine(engine_type, **kwargs):
        if engine_type == 'google_custom':
            return GoogleCustomSearch(kwargs['api_key'], kwargs['cx'])
        elif engine_type == 'serp_api':
            return SerpAPISearch(kwargs['api_key'])
        else:
            raise ValueError(f"Unknown search engine type: {engine_type}")