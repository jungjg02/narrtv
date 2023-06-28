from collections import OrderedDict
from bs4 import BeautifulSoup
import requests, json, re
from flask import Response
from support import d, default_headers, logger
from tool import ToolUtil

from .setup import P


class Narrtv:
    _url = "https://tv.nextcast00.com"

    @classmethod
    def ch_list(cls):
        channels = []
        sport_categories = {
            '1': '',
            '2': '축구',
            '3': '야구',
            '4': '농구',
            '5': '배구',
            '6': '하키',
            '7': '테니스',
            '8': '럭비',
            '9': 'UFC',
            '10': 'E스포츠'
        }

        data = requests.get(f"{cls._url}/BR/nene03/schedule5.asp?version=1",
                             headers={"referer":f"{cls._url}/BR/nene03/default.asp?v=3&client=nenetv"}).text
        soup = BeautifulSoup(data, 'html.parser')
        game_items = soup.find_all('div', class_=re.compile("card game-itme border-0 items_4 list-level-[12]"))

        for x in game_items:
            live_status = x.find(class_="badge badge-secondary video-s")
            if live_status:
                image_src = x.select_one('div.col-3 img')['src']
                logo = image_src.replace("./img/", f"{cls._url}/img/")
                category=image_src.replace("./img/", '').replace(".png", '')
                league = x.select_one('div.col-3').text.strip()
                home_team, time, away_team = [x.select_one('div.col.text-center p:nth-of-type(2)').text.strip() for x in x.select('div.col.text-center')[:3]]
                broadcast_id = re.search(r"play_video\('(\d+)'", live_status.find_parent('div', class_="col text-center").get("onclick")).group(1) if live_status else None
                
                channels.append({
                    "type": "sports",
                    'id': broadcast_id,
                    'name': home_team if home_team == away_team else f"{home_team} vs {away_team}",
                    'time': time,
                    "category": sport_categories.get(category, None),
                    'league': league,
                    'logo': logo,
                    
                })
        return channels
        
    
    @classmethod
    def get_m3u8(cls, ch_id):
        response = requests.post(f"{cls._url}/cast/get_broadcast.php", 
                                 data={"idx": {ch_id}, "source":"", "ref":"<%=refUrl%>P"}, 
                                 headers={"referer":f"{cls._url}/BR/nene03/default.asp?v=3&client=nenetv",'Content': 'text'}
                                 ).text.split('|')[0]
        
        return 'redirect', response
    

    @classmethod
    def make_m3u(cls):
        M3U_FORMAT = '#EXTINF:-1 tvg-id=\"{id}\" tvg-name=\"{title}\" tvg-logo=\"{logo}\" group-title=\"{group}\" tvg-chno=\"{ch_no}\" tvh-chnum=\"{ch_no}\",{title}\n{url}\n' 
        m3u = '#EXTM3U\n'
        for idx, item in enumerate(cls.ch_list()):
            m3u += M3U_FORMAT.format(
                id=item['id'],
                title=item['name'],
                group=item['type'],
                ch_no=str(idx+1),
                url=ToolUtil.make_apikey_url(f"/{P.package_name}/api/url.m3u8?ch_id={item['id']}"),
                logo= item['logo'],
            )
        return m3u