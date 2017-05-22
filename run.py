# -*- coding: utf-8 -*-

import sys
import os
import json
import re
import time
import logging
import logging.handlers
import requests
import base64
import urllib
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from config import settings


class WikipediaBot(object):
	# Initial Properties
	todays_dir_dt_fmt = str(datetime.utcnow().strftime("%Y-%m-%d"))
	todays_dir = 'scraped_data/%s'%(todays_dir_dt_fmt)
	today_img_dir = ('%s/images')%(todays_dir)
	current_day = str(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S (UTC)"))
	article_day = str(datetime.utcnow().strftime("%d %B %Y"))
	scrape_set = {}
	temp_link = []
	r_session = requests.Session()
	url_max_retry = 6
	http = requests.adapters.HTTPAdapter(max_retries=url_max_retry)
	https = requests.adapters.HTTPAdapter(max_retries=url_max_retry)
	r_session.mount('http://', http)
	r_session.mount('https://', https)


	def __init__(self,host,crawl_host,save_dir,img_dir,log_dir,log_file,img_size_approx,browser_headers):
		if not os.path.exists('scraped_data'):
			os.makedirs('scraped_data')
		if not os.path.exists('logs'):
			os.makedirs('logs')
		if not os.path.exists(self.todays_dir):
			os.makedirs(self.todays_dir)
		if not os.path.exists(self.today_img_dir):
			os.makedirs(self.today_img_dir)

		self.host = host
		self.crawl_host =  crawl_host
		self.save_dir = save_dir
		self.img_size_approx = img_size_approx
		self.browser_headers = browser_headers
		self.img_url = 'https://en.wikipedia.org/w/api.php?action=query&titles=%s&prop=pageimages&format=json&pithumbsize=%s'
		self.LOG_FILENAME = '%s/%s'%(log_dir,log_file)
		self.log = logging.getLogger(__name__)
		self.log.setLevel(logging.DEBUG)
		self.formatter = logging.Formatter(fmt='%(asctime)s | Line No : %(lineno)d | Level : %(levelname)s | File : %(filename)s | Caller : %(funcName)s | Message : %(message)s')
		self.handler = logging.handlers.RotatingFileHandler(self.LOG_FILENAME, maxBytes=10**6, backupCount=5)
		self.handler.setFormatter(self.formatter)
		self.log.addHandler(self.handler)


	# Console Text Format Color
	# Param : Color,String
	# Return : - | Prints : String 
	def text(self,color,_str):
		print "\033[%sm \r%s \033[0m"%(color,_str)


	# Save IMG
	# Param : URL,TITLE,SAVE_TYPE
	# Return : [temp_img,img_size,ext]
	def save_img(self,url,title,save_type='disk'):
		# SAVE IN JSON OR DISK
		r = self.r_session.get(url,headers=self.browser_headers)
		r.raise_for_status()
		if r.headers['content-length']:
			img_size = str(r.headers['content-length'])
		
		if r.headers['content-type']=='image/jpeg':
			ext ='jpg'
		elif r.headers['content-type']=='image/png':
			ext ='png'
		elif r.headers['content-type']=='image/gif':
			ext ='gif'
		
		if save_type=='json':
			# Save Base64 Img To JSON Data File Inline
			temp_img = base64.b64encode(r.content)
		elif save_type=='disk':
			# Save To Folder And Generate URL
			temp_img = '%s/%s.%s'%(self.today_img_dir,re.sub('[ \.,()#\d{0,20}]','',title),ext)
			with open(temp_img,'wb+') as img:
				img.write(r.content)
				img.close()
		else:
			raise Exception("Image Could Not Be Saved")

		return [temp_img,img_size,ext]


	# Scraper | (WIKIPEDIA ON THIS DAY DIV ON MAIN PAGE STORIES)
	def scraper(self):
		try:
			self.text(92,"\n\n   BOT : Starting Wikipedia Crawl...\n")
			self.text(92,"\n   BOT : Crawling...\n")
			self.log.info("BOT : Scraper Function Started")
			r = requests.get(self.host,headers=self.browser_headers)
			data = r.content
			# LXML ERROR MAY RISE UNCAUGHT CHECK WHEN OS CHANGE
			parse = BeautifulSoup(str(data),'lxml',from_encoding="utf-8")
			div = parse.find("div", {"id": "mp-otd"})
			hot_link = div.findAll('li')
			for elem,links in enumerate(hot_link):

				if elem==0 or elem==1 or elem==2 or elem==3 or elem==4:
					year = re.findall(r'[0-9]{3,4}',links.text)					
					# Without Year Content
					# content = re.sub(r'[0-9]{4}','',links.text)
					# With Year Content
					content = str(links.text.encode('ascii', 'ignore'))
					# BULK LINK EMPTY ARRAY INITIALISED ONLY
					bulk_link = []
					inner_link = links.findAll('a')
					inner_link.pop(0)
					for links in inner_link:
						temp = BeautifulSoup(str(links),'lxml')
						title =  temp.a['title']
						link  = temp.a['href']
						bulk_link.append({'title':title,'url':link,'img_w':False,'img_h':False,'img_size':False,'ext_type':False,'img':False})

					self.scrape_set.update({elem: {'year':year[0],'content':str(content),'links':bulk_link}})

					with open('scraped_data/temp_scraped_data.json','wb+') as content:
						content.write(json.dumps(self.scrape_set))
						content.close()

			data = open('scraped_data/temp_scraped_data.json','r')
			content = json.loads(data.read())
			data.close()

			for key,val in sorted(content.iteritems()):

				for link in val['links']:
				
					url = link['url']
					title = str(link['title'].encode('ascii', 'ignore'))
					# Fail Safe Encodes '#' => %23 As Requests Library Does Not Do That Automatically
					encoded_url = re.sub('#','%23',url.replace("/wiki/",''))
					r = requests.get(self.img_url%(encoded_url,self.img_size_approx),headers=self.browser_headers)
					data = json.loads(r.content)
					# FAIL SAFE PAGE KEY ERROR WIKI API
					# Break The Loop And Move Forward
					if 'pages' not in data['query']:
						self.text(93,"\n   BOT : Page Key Error For - %s\n")%(title)
						self.log.error("BOT : Page Key Error For - %s")%(title)
						break

					for k,v in data['query']['pages'].iteritems():
						if 'thumbnail' in v:
							thumb_url = str(v['thumbnail']['source'].encode('ascii', 'ignore'))
							img_w = v['thumbnail']['width']
							img_h = v['thumbnail']['height']
							img_data = self.save_img(thumb_url,title)
							self.temp_link.append({'content_key':key,'url':url,'title':title,'img_w':img_w,'img_h':img_h,'img_size':img_data[1],'ext_type':img_data[2],'img':img_data[0]})

						else:
							self.text(93,"\n   BOT : Image Not Available For - %s (Skipping)\n"%(title))
							self.log.warn("BOT : Image Not Available For - %s (Skipping)"%(title))
		
			temp_link_list = open('scraped_data/temp_link.json','wb+')
			temp_link_list.write(json.dumps({'links':self.temp_link}))
			temp_link_list.close()

			# Read Saved JSON FOR FURTHER PROCESS
			save_json = open('scraped_data/temp_scraped_data.json','r')
			json_content_main = json.loads(save_json.read())
			save_json.close()

			for key,val in sorted(json_content_main.iteritems()):
				temp = open('scraped_data/temp_link.json','r')
				content_link = json.loads(temp.read())
				temp.close()
				for link in val['links']:
					for link_img in content_link['links']:
						if link_img['title']==link['title']:

							# Replace And Re-Prepare Json With Fetched Img
							link['img']=link_img['img']
							link['img_w']=link_img['img_w']
							link['img_h']=link_img['img_h']
							link['ext_type']=link_img['ext_type']
							link['img_size']=link_img['img_size']

			#Write JSON (Base)
			save_json_clean = open('scraped_data/temp_scraped_data.json','wb')
			save_json_clean.write(json.dumps(json_content_main))
			save_json_clean.close()
			os.remove('scraped_data/temp_link.json')

			# /////////////////////////////////////////////////////////////////////////////////
			# Highlighted On This Day
			# ////////////////////////////////////////////////////////////////////////////////

			temp_highlight_json={} 
			r = requests.get(self.host,headers=self.browser_headers)
			data = r.content
			parse = BeautifulSoup(str(data),'lxml',from_encoding='utf-8')
			div = parse.find("div", {"id": "mp-otd"})
			hot_link = BeautifulSoup(str(div.find('p')),'lxml',from_encoding='utf-8')

			# Highlight Day And Contents Of It Grab Here
			highlight_day = str(hot_link.getText()).split(':')[0]
			highlight_content = str(hot_link.getText())
		
			# ---------------------
			# MAIN SEPERATOR
			# (CHANGE HERE IF U REQUIRE ONLY ONE ANCHOR TAG FROM FIRST <P> HIGHLIGHT ELEM)
			# ----------------------
			# ->Fetch Only 1st Elem ->># str(hot_link.html.body.p.b.a.contents[0])
			# ---------------------
			# HIGHLIGHT DIV <P> ELEM FILTER LOGIC
			# ---------------------
			# GRAB ALL ANCHOR IN HIGHLIGHT DIV <P> FIRST HIGHLIGHT TAG
			# POP 0 ELEM AS IT'S YEAR AND ALSO IGNORE YEAR LINKS
			# ---------------------

			highlight_data = list(hot_link.html.body.p.findAll('a',href=True))
			highlight_data.pop(0)
			
			# print highlight_data

			# TEMP Highlight Holder
			temp_highlight_link = []
			# Cleaned Highlight HOLDER 
			highlight_link = []

			for link in highlight_data:
				temp = BeautifulSoup(str(link),'lxml',from_encoding='utf-8')
				title =  temp.a['title']
				link  = temp.a['href']
				year = re.search(r"/wiki/[0-9]{3,4}",str(link))

				# IMP ----------
				# Ignoring Year Links In Highlight Todays Div <P> FIRST TAG
				if not year:
					temp_highlight_link.append({'title':title,'url':link})
			
			for link in temp_highlight_link:
				# Link
				title = link['title']
				url  = link['url']
				# Fail Safe Encodes '#' => %23 As Requests Library Does Not Do That Automatically
				encoded_url = re.sub('#','%23',url.replace("/wiki/",''))
				r = requests.get(self.img_url%(encoded_url,self.img_size_approx),headers=self.browser_headers)
				data = json.loads(r.content)
			
				# print str(data)+str('\n')

				# FAIL SAFE PAGE KEY ERROR WIKI API
				# Break The Loop And Move Forward 
				if 'pages' not in data['query']:
					self.text(93,"\n   BOT : Page Key Error For - %s\n")%(title)
					self.log.error("BOT : Page Key Error For - %s")%(title)
					break

				for k,v in data['query']['pages'].iteritems():
					if 'thumbnail' in v:
						thumb_url = str(v['thumbnail']['source'].encode('ascii', 'ignore'))
						img_w = v['thumbnail']['width']
						img_h = v['thumbnail']['height']
						img_data = self.save_img(thumb_url,title)
						highlight_link.append({'url':url,'title':title,'img_w':img_w,'img_h':img_h,'img_size':img_data[1],'ext_type':img_data[2],'img':img_data[0]})

					else:
						self.text(93,"\n   BOT : Image Not Available For - %s (Skipping)\n"%(title))
						self.log.warn("BOT : Image Not Available For - %s (Skipping)"%(title))
		
			# print temp_highlight_link
			# print highlight_link

			self.text(92,"\n   BOT : Scraping Data And Preparing Cleaned JSON...\n")

			# ----------------------------
			# Prepare Final Cleaned JSON
			# ----------------------------
			json_open_clean = open('scraped_data/temp_scraped_data.json','r')
			temp_link_clean_hold = json.loads(json_open_clean.read())
			json_open_clean.close()

			save_json = open('%s/%s.json'%(self.todays_dir,self.todays_dir_dt_fmt),'wb')
			temp_l = []
			for k,link in sorted(temp_link_clean_hold.iteritems()):
				temp_l.append(link)
			clean_data = {'timestamp':self.current_day,'article_day':self.article_day,'todays_highlight':{'highlight_day':highlight_day,'highlight_content':highlight_content,'links':highlight_link},'year_highlight':temp_l}
			save_json.write(json.dumps(clean_data))
			os.remove('scraped_data/temp_scraped_data.json')

			self.log.info(str(time.strftime("BOT : Scraper Function Completed")))
			self.text(92,"\n   BOT : Completed...\n\n")
			
			return None
			
		except Exception,e:
			self.log.exception(e)
			self.text(91,"\nError : %s\n\n"%(e))
			print '-'*60
			traceback.print_exc()
			print '-'*60
			sys.exit(1)
	# ////////////////////////////////////////////////////////////////////


if __name__ == "__main__":
	wiki_bot = WikipediaBot(settings['scraper']['host'],settings['scraper']['crawl_host'],settings['scraper']['save_dir'],settings['scraper']['img_dir'],settings['scraper']['log_dir'],settings['scraper']['log_file'],str(settings['scraper']['img_size_approx']),settings['scraper']['browser_headers'])
	wiki_bot.scraper()