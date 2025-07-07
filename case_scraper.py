import sys
import os
from autoscraper import AutoScraper
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import random
import pandas as pd
import networkx as nx
from collections import defaultdict
import re
import spacy
from urllib.parse import urlencode
from urllib.parse import urlparse
from sklearn.feature_extraction.text import TfidfVectorizer
from urllib.parse import urlparse
import config as conf

def try_call(call_url,params={}):

	try:
		res = requests.get(call_url,params=params)
	except Exception as e:
		print (e)
		res = None
	return res

class Google:

	def __init__(self,tokens):

		self.tokens = tokens["tokens"]
		self.base_url = "https://customsearch.googleapis.com/customsearch/v1"
		self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36"

	def _get_next_idx_page(self,res,max_idx=1):

		next_idx = None
		if res is not None:
			res = res.json()
			if "queries" in res and "nextPage" in res["queries"]:
				next_idx = res["queries"]["nextPage"][0]["startIndex"]
				if int(next_idx) > max_idx:
					next_idx = None
		return next_idx

	def _update_output(self,res,output_data):

		if res is not None:
			if "items" in res.json():
				for e in res.json()["items"]:
					output_data["output"].append(e)
		return output_data

	def _get_data(self,data,call_url,params,headers,max_idx=1):

		res = try_call(call_url,params=params)
		data = self._update_output(res,data)
		next_idx = self._get_next_idx_page(res,max_idx=max_idx)
		while next_idx:
			params.update({"start":next_idx})
			res = try_call(call_url,params=params)
			data = self._update_output(res,data)
			next_idx = self._get_next_idx_page(res,max_idx=max_idx)
		return data

	def query_content(self,query,page_views=1):

		data = {"input":query,
				"input_type":"link",
				"output":[],
				"method":"google"}
		headers = {'User-Agent': self.user_agent,
					'Accept': 'application/json'}
		creds = random.choice(self.tokens)
		#creds = self.tokens[-1]
		call_url = self.base_url
		params = {"key":creds["key"],
					"cx":creds["cx"],
					"q":'{0}'.format(query),
					"gl":"dk"}
		data = self._get_data(data,call_url,urlencode(params),headers,max_idx=page_views)

		return data

def load_data(main_path,title):

	file_path = main_path+"/data/"+title+".csv"
	if os.path.isfile(file_path):
		df = pd.read_csv(file_path)
	else:
		df = pd.DataFrame(columns=['title', 'search_keywords', 'url',"scrape_date","texts"])
	return df

def dynamic_save(main_path,keyword,df):

	file_path = main_path+"/data/"+keyword+".csv"
	if not os.path.exists(main_path+"/data"):
		os.makedirs(main_path+"/data")
	df.to_csv(file_path,index=False)

def scrape_single_url(url, search_list, tags):
	# Send a request to the URL
	response = try_call(url)
	if response is not None and response.status_code != 200:
		return f"Failed to retrieve content from {url}, status code: {response.status_code}"
	else:

		# Parse the HTML content
		soup = BeautifulSoup(response.content, 'html.parser')
		
		# Find all specified tags
		elements = soup.find_all(tags)
		
		# Filter elements that contain any of the search strings
		matching_elements = [str(element.text) for element in elements if any(s in element.text for s in search_list) or any(s.lower() in element.text for s in search_list)]

	return matching_elements

def load_issue_dict_file(filepath):

	issue_kws = []
	for kw in open(filepath,"r").readlines():
		issue_kws.append(kw.strip())
	return issue_kws

def scrape(title,issue_dict_file,save=True,verbose=False):

	main_path = conf.Config.MAIN_PATH
	tokens = conf.Config.get_auth()["customsearch"]
	tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']
	
	# REMEBER TO CHANGE SEARCH KEYS
	search_keys = load_issue_dict_file(main_path+"/search_queries/{}".format(issue_dict_file))

	df = load_data(main_path,title)
	search_results = []
	for kw in search_keys:
		search_results.extend([doc["link"] for doc in Google(tokens).query_content(kw,page_views=10)["output"]])
	search_results = list(set(search_results))
	founds = {}
	raw_data = []
	already_found = set(list(df["url"]))
	new_found_count = 0
	for scrape_url in search_results[:3]:
		if not scrape_url in already_found:
			founds[scrape_url]=set(scrape_single_url(scrape_url,search_keys,tags))
			doc={	"title":title,
					"search_keywords":str(search_keys),
					"url":scrape_url,
					"scrape_date":datetime.today(),
					"texts":founds[scrape_url]}
			raw_data.append(doc)
			new_found_count+=1
			if new_found_count % 5 == 0:
				print (f"saving {len(raw_data)} new scrapes")
				temp_df = pd.DataFrame(raw_data)
				df = pd.concat([df,temp_df])
				raw_data = []
				dynamic_save(main_path,title,df)
	print (f"saving {len(raw_data)} new scrapes")
	temp_df = pd.DataFrame(raw_data)
	df = pd.concat([df,temp_df])
	raw_data = []
	dynamic_save(main_path,title,df)

	if verbose:
		for k,v in founds.items():
			for tv in v:
				print (tv)
				print ()
				print ("---------------------------------------------")
				print ()

def create_net_from_tokens(main_path,title,docs):

	g = nx.Graph()
	for dom,tokens in docs.items():
		g.add_node(dom,nodetype="actor")
		for t in tokens:
			if not g.has_node(t):
				g.add_node(t,nodetype="token")
			g.add_edge(dom,t)
	file_path = main_path+"/gexfs/"+title+".gexf"
	if not os.path.exists(main_path+"/gexfs"):
		os.makedirs(main_path+"/gexfs")
	nx.write_gexf(g,file_path)

def get_nouns(title):

	def _get_domain(url):

		parsed_url = urlparse(url)
		domain = parsed_url.netloc
		domain = domain.replace("www.","")

		return domain

	def _get_tfidfs(ds):

		ds = [' '.join(d) for d in ds]
		vectorizer = TfidfVectorizer()
		tfidf_matrix = vectorizer.fit_transform(ds)
		feature_names = vectorizer.get_feature_names_out()
		tfidf_scores = []
		for di, d in enumerate(ds):
			feature_index = tfidf_matrix[di,:].nonzero()[1]
			tfidf_scores_for_doc = {feature_names[i]: tfidf_matrix[di, i] for i in feature_index}
			tfidf_scores.append( tfidf_scores_for_doc )

		# Print the dictionary of TF-IDF scores
		return tfidf_scores

	def _clean_texts(df,text_col="texts"):

		cts = []
		for t in list(df[text_col]):
			ct = re.sub(r'\n+', '\n', t)
			ct = ct.replace("\\n"," ")
			ct = ct.replace("\\t"," ")
			ct = ct.replace("\\r"," ")
			ct = re.sub(r'\s+', ' ', ct).strip()
			cts.append(ct)
		df[text_col]=cts
		return df

	main_path = conf.Config.MAIN_PATH
	file_path = main_path+"/data/"+title+".csv"
	df = pd.read_csv(file_path)
	df = _clean_texts(df)
	da_nlp = spacy.load('da_core_news_md')

	ds = []
	for t in list(df["texts"]):
		nouns = []
		d = da_nlp(t)
		for token in d:
			if token.pos_ == "NOUN":
				nouns.append(token.lemma_)
		ds.append(nouns)
	ds_scores = _get_tfidfs(ds)

	new_docs = defaultdict(set)
	for scores,url in zip(ds_scores,list(df["url"])):
		dom = _get_domain(url)
		new_docs[dom].update(set([k for k,v in sorted(scores.items(), key=lambda item: item[1],reverse=True)[:10]]))
		#print (sorted(scores.items(), key=lambda item: item[1],reverse=True)[:10])
		#print ()

	create_net_from_tokens(main_path,title,new_docs)

if __name__ == "__main__":
	args = sys.argv
	title = args[1]
	issue_file = args[2]
	scrape(title,issue_file,save=True,verbose=False)
	get_nouns(title)

