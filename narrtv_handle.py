from collections import OrderedDict
import requests, json, re
from flask import Response
from bs4 import BeautifulSoup
from datetime import datetime
import os
import yaml
from support import d, default_headers, logger
from tool import ToolUtil


from .setup import P


class Narrtv:

    _url = "https://tv.nextcast00.com"
    sport_categories = {
            '2': 'soccer',
            '3': 'baseball',
            '4': 'basketball',
            '5': 'volleyball',
            '6': 'hockey',
            '7': 'tennis',
            '8': 'football',
            '9': 'ufc',
            '10': 'egame'
        }
    
    @classmethod
    def ch_list(cls):
        channels = []

        html_code = requests.get(f"{cls._url}/BR/nene03/schedule5.asp?version=1",
                             headers={"referer":f"{cls._url}/BR/nene03/default.asp?v=3&client=nenetv"}).text
        soup = BeautifulSoup(html_code, 'html.parser')
        game_items = soup.find_all('div', class_=re.compile("card game-itme border-0 items_4 list-level-[12]"))

        for x in game_items:
            live_status = x.find(class_="badge badge-secondary video-s")
            if live_status:
                image_src = x.select_one('div.col-3 img')['src']
                logo = image_src.replace("./img/", f"{cls._url}/BR/nene03/img/")
                category=image_src.replace("./img/", '').replace(".png", '')
                league = x.select_one('div.col-3').text.strip()
                home_team, time, away_team = [x.select_one('div.col.text-center p:nth-of-type(2)').text.strip() for x in x.select('div.col.text-center')[:3]]
                broadcast_id = re.search(r"play_video\('(\d+)'", live_status.find_parent('div', class_="col text-center").get("onclick")).group(1) if live_status else None
                
                channels.append({
                    "source": "NARRTV",
                    "source_name":"나르TV",
                    "type": "SPORTS",
                    'category': cls.sport_categories.get(category, None),
                    'time': time,
                    "channel_id": broadcast_id,
                    'name': home_team if home_team == away_team else f"{home_team} vs {away_team}",
                    "current": None,
                    "url": None,
                    "icon": logo,
                    'leauge': league,
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
            if item['type'] in ['SPORTS']:
                m3u += M3U_FORMAT.format(
                    id=item['channel_id'],
                    title=f"{item['name']}",
                    group=item['type'],
                    ch_no=str(idx+1),
                    url=ToolUtil.make_apikey_url(f"/{P.package_name}/api/url.m3u8?ch_id={item['channel_id']}"),
                    logo=item['icon'],
                )
        return m3u
    
    @classmethod
    def make_yaml(cls):
        
        data = {
            'primary': True,
            'code': "narrtv",
            'title': "[NARRTV]",
            'year': 2023,
            'genres': "Live",
            'posters': 'https://cdn.discordapp.com/attachments/877784202651787316/1124900470088020029/narrtv.png',
            'summary': "",
            'extras':[]
        }
        for idx, item in enumerate(cls.ch_list()):
            if item['type'] in ['SPORTS']:
                data['extras'].append({
                'mode': "m3u8",
                'type': 'featurette',
                'param': ToolUtil.make_apikey_url(f"/{P.package_name}/api/url.m3u8?ch_id={item['channel_id']}"),
                'title': item['name'],
                'thumb': item['icon']
                })
            

        yaml_data = yaml.dump(data, allow_unicode=True, sort_keys=False, encoding='utf-8')
        return yaml_data
    
    @classmethod
    def plex_refresh_by_item(cls, item_id):
        try:
            plex_server_url = P.ModelSetting.get('main_plex_server_url')
            plex_token = P.ModelSetting.get('main_plex_token')

            url = f"{plex_server_url}/library/metadata/{item_id}/refresh?X-Plex-Token={plex_token}"
            ret = requests.put(url)
            ret.raise_for_status()

            P.logger.debug('Plex 메타 데이터 새로고침이 성공적으로 시작되었습니다.')
        except requests.exceptions.RequestException as e:
            P.logger.error(f'requests.exceptions.RequestException:{str(e)}')
        except Exception as e:
            P.logger.error(f'Exception:{str(e)}')

    
    @classmethod
    def sync_yaml_data(cls):
        try:
            yaml_url = ToolUtil.make_apikey_url(f"/{P.package_name}/api/yaml")
            local_path = P.ModelSetting.get('main_yaml_path')
            meta_item = P.ModelSetting.get('main_plex_meta_item')

            # YAML 파일을 가져와 이전 데이터를 로드합니다.
            response = requests.get(yaml_url)
            new_data = yaml.safe_load(response.content)
            previous_data = yaml.safe_load(open(local_path, encoding='utf-8')) if os.path.exists(local_path) else None

            # extras 만 가져와서 비교합니다.
            new_data_extras_data = new_data['extras']
            previous_extras_data = previous_data['extras']

            # 이전 데이터와 새 데이터를 비교합니다.
            if previous_extras_data is not None and previous_extras_data != new_data_extras_data:
                # 데이터가 변경된 경우, 로컬에 저장합니다.
                updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_data['summary'] = f"마지막 업데이트 시간 : {updated_at}"

                with open(local_path, 'w', encoding='utf-8') as file:
                    yaml.dump(new_data, file, allow_unicode=True, sort_keys=False, encoding='utf-8')
                    P.logger.debug('데이터가 변경되어 로컬에 저장되었습니다.')

                # Plex 메타 데이터를 새로고침합니다.
                cls.plex_refresh_by_item(meta_item)

        except requests.exceptions.RequestException as e:
            P.logger.error(f'requests.exceptions.RequestException:{str(e)}')
        except yaml.YAMLError as e:
            P.logger.error(f'yaml.YAMLError:{str(e)}')
        except Exception as e:
            P.logger.error(f'Exception:{str(e)}')


    
