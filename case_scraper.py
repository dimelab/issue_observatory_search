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

def load_data(main_path,keyword):

	file_path = main_path+"/"+keyword+".csv"
	if os.path.isfile(file_path):
		df = pd.read_csv(file_path)
	else:
		df = pd.DataFrame(columns=['keyword', 'search_keywords', 'url',"scrape_date","texts"])

	return df

def dynamic_save(main_path,keyword,df):

	file_path = main_path+"/"+keyword+".csv"
	df.to_csv(file_path,index=False)

def scrape_single_url(url, search_list, tags):
	# Send a request to the URL
	response = try_call(url)
	if response is not None and response.status_code != 200:
		return f"Failed to retrieve content from {url}, status code: {response.status_code}"

		# Parse the HTML content
		soup = BeautifulSoup(response.content, 'html.parser')
		
		# Find all specified tags
		elements = soup.find_all(tags)
		
		# Filter elements that contain any of the search strings
		matching_elements = [str(element.text) for element in elements if any(s in element.text for s in search_list)]
	else:
		matching_elements = "None"

	return matching_elements

def scrape(main_path,save=True,verbose=False):

	tokens = {"tokens":[{"key":"AIzaSyCgDpys0CFao3C3SyMNz6PBXs5-lxZWgf8","cx":"013924965797933482638:elqtd-rolhw"}]}
	tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']
	
	# REMEBER TO CHANGE SEARCH KEYS
	search_keys = ["CO2 afgift","CO2-afgift","co2 afgift","co2-afgift"]

	main_search_key = "CO2 afgift"
	df = load_data(main_path,main_search_key)
	search_results = [doc["link"] for doc in Google(tokens).query_content(main_search_key,page_views=100)["output"]]
	print (search_results)
	print (len(search_results))
	sys.exit()
	founds = {}
	raw_data = []
	already_found = set(list(df["url"]))
	new_found_count = 0
	for scrape_url in search_results:
		if not scrape_url in already_found:
			founds[scrape_url]=set(scrape_single_url(scrape_url,search_keys,tags))
			doc={	"keyword":main_search_key,
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
				dynamic_save(main_path,main_search_key,df)

	if verbose:
		for k,v in founds.items():
			for tv in v:
				print (tv)
				print ()
				print ("---------------------------------------------")
				print ()

def create_net_from_tokens(main_path,keyword,docs):

	g = nx.Graph()
	for dom,tokens in docs.items():
		g.add_node(dom,nodetype="actor")
		for t in tokens:
			if not g.has_node(t):
				g.add_node(t,nodetype="token")
			g.add_edge(dom,t)
	file_path = main_path+"/"+keyword+".gexf"
	nx.write_gexf(g,file_path)

def get_nouns(main_path,keyword):

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

	file_path = main_path+"/"+keyword+".csv"
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
		print (sorted(scores.items(), key=lambda item: item[1],reverse=True)[:10])
		print ()

	create_net_from_tokens(main_path,keyword,new_docs)

def get_match_list(lst,match_with):

	matched = []

	def _get_page_username(url):

		_val = ""
		if "?php" in url:
			return _val
		if "/public/" in url:
			return _val

		if ".facebook.com/p/" in url:
			temp_val = url.split(".facebook.com/p/")[-1].split("/")[0]
		else:
			temp_val = url.split(".facebook.com/")[-1].split("/")[0]

		if "-" in temp_val:
			for s in temp_val.split("-"):
				if s.isnumeric():
					temp_val = s
		temp_val = temp_val.replace("@","")
		_val = temp_val

		return _val

	def _get_yt_channel(urls,max_try=1):

		for url in urls:
			url = url["link"]
			#print (url)
			_val = ""
			if "@" in url:
				_val = url.split("@")[-1].split("/")[0]
			elif "channel" in url:
				_val = url.split("channel/")[-1].split("/")[0]
			elif "user" in url:
				_val = url.split("user/")[-1].split("/")[0]
			if _val != "":
				break
		return _val

	def _get_insta(urls,max_try=1):

		for url in urls:
			url = url["link"]
			_val = ""
			if "instagram.com/" in url:
				_val = url.split("instagram.com/")[-1].split("/")[0]
			if _val != "":
				break
		return _val

	def _get_linkedin(urls,max_try=1):

		for url in urls:
			url = url["link"]
			_val = ""
			if "dk.linkedin.com/in/" in url:
				_val = url.split("dk.linkedin.com/in/")[-1].split("/")[0]
			if "dk.linkedin.com/company/" in url:
				_val = url.split("dk.linkedin.com/company/")[-1].split("/")[0]
			if _val != "":
				break
		return _val

	def _get_twitter(urls,max_try=1):

		for url in urls:
			url = url["link"]
			_val = ""
			if "x.com/" in url:
				_val = url.split("x.com/")[-1].split("/")[0]
			if "twitter.com/" in url:
				_val = url.split("twitter.com/")[-1].split("/")[0].split("?")[0]
			if _val != "":
				break
		return _val

	def _get_tiktok(urls,max_try=1):

		for url in urls:
			url = url["link"]
			_val = ""
			if "tiktok.com/" in url and "@" in url:
				_val = url.split("@")[-1].split("/")[0]
			if _val != "":
				break
		return _val

	#tokens = {"tokens":[{"key":"AIzaSyCgDpys0CFao3C3SyMNz6PBXs5-lxZWgf8","cx":"013924965797933482638:elqtd-rolhw"}]}
	tokens = {"tokens":[{"key":"AIzaSyAdfI0AaKRFS8EbPXBQJtbWln7Ixre7G98","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyChuQPz_SytL01wp3nrTsU5UR7VONVzrh8","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyBc_4YdswjsH9V96FFIwydwh3CM_ROoJVk","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyC2ALJ71_YwNGlKe-A_VIadfRZdmND-cag","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyCwoUEsTm7ADGLP6VVqNuVUPxKd66m50Kg","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyD5ZjyxMS5_B9yXRQki7CxCjOzkz1rQ7b4","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyB-oek4a76zPQdff1yyOibiJElroxoshZU","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyDNNbdpF9SAaii6v6JnA7pAFFjCihFI5As","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyBNgQfuwQL6cf-nZlmBBcvoT9mhwlzhRM0","cx":"e2cfb1a5cd5d14592"},
						{"key":"AIzaSyDhYK9ZdJZbqLOr12zxG0tKXU4mpCRSAcU","cx":"e2cfb1a5cd5d14592"},
						]}
	googl = Google(tokens)
	for n in list(lst)[:500]:
		try:
			data = googl.query_content(n+" "+match_with)
			if "Facebook" in match_with:
				f_username = _get_page_username(data["output"][0]["link"])
			elif "Youtube" in match_with:
				f_username = _get_yt_channel(data["output"],max_try=8)
			elif "Instagram" in match_with:
				f_username = _get_insta(data["output"],max_try=8)
			elif "LinkedIn" in match_with:
				f_username = _get_linkedin(data["output"],max_try=1)
			elif "Twitter" in match_with:
				f_username = _get_twitter(data["output"],max_try=1)
			elif "TikTok" in match_with:
				f_username = _get_tiktok(data["output"],max_try=4)
			print (n + " " + f_username + "    " + data["output"][0]["link"])

		except Exception as e:
			print (e)
			f_username = ""
		matched.append(f_username)

	return matched


main_path = "/Users/jakobbk/Documents/postdoc/Digital Media Lab/Sagsobservatoriet"
keyword = "CO2 afgift"
#fdf = set(list(pd.read_excel(main_path+"/folketingsmedlemmer.xlsx")["name"]))
df = pd.read_excel(main_path+"/nyhedsmedier.xlsx",nrows=500)
fdf = list(df["name"])
#match_with = "Facebook page"
#match_with = "Youtube channel"
#match_with = "Instagram"
#match_with = "LinkedIn"
#match_with = "Twitter"
#match_with = "TikTok"

#scrape(main_path)
#get_nouns(main_path,keyword)
for match_with in ["Facebook page","Youtube channel","Instagram","LinkedIn","Twitter","TikTok"]:
	match_list = get_match_list(fdf,match_with)
	df["Facebook page"]=match_list
	df.to_csv(main_path+f"/nyhedsmedier_w_{match_with}.csv")





