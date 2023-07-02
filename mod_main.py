from datetime import datetime
from tool import ToolUtil
from flask import Response
from .setup import *
from .narrtv_handle import Narrtv



class ModuleMain(PluginModuleBase):

    def __init__(self, P):
        super(ModuleMain, self).__init__(P, name='main', first_menu='setting', scheduler_desc="NARRTV Plex Yaml 생성 및 Plex Meta Update")
        self.db_default = {
            f'{self.name}_db_version' : '1',
            f'{self.name}_auto_start' : 'False',
            f'{self.name}_interval' : '5',
            f'{self.name}_yaml_path' : '',
            f'{self.name}_plex_server_url' : 'http://localhost:32400',
            f'{self.name}_plex_token' : '',
            f'{self.name}_plex_meta_item' : ''
        }


    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['api_m3u'] = ToolUtil.make_apikey_url(f"/{P.package_name}/api/m3u")
        arg['api_yaml'] = ToolUtil.make_apikey_url(f"/{P.package_name}/api/yaml")
        if sub == 'setting':
            arg['is_include'] = F.scheduler.is_include(self.get_scheduler_name())
            arg['is_running'] = F.scheduler.is_running(self.get_scheduler_name())
        return render_template(f'{P.package_name}_{self.name}_{sub}.html', arg=arg)
    
    

    def process_command(self, command, arg1, arg2, arg3, req):
        if command == 'broad_list':
            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return jsonify({"list": Narrtv.ch_list(), "updated_at": updated_at})
        elif command == 'play_url':
            url = arg3 if arg3 else ToolUtil.make_apikey_url(f"/{P.package_name}/api/url.m3u8?ch_id={arg1}")
            ret = {'ret':'success', 'data':url, 'title': arg2}
        return jsonify(ret)


    def process_api(self, sub, req):
        try:
            if sub == 'm3u':
                data = Narrtv.make_m3u()
                return Response(data, headers={'Content-Type': 'text/plain; charset=utf-8'})
            elif sub == 'yaml':
                data = Narrtv.make_yaml()
                return Response(data, headers={'Content-Type': 'text/yaml; charset=utf-8'})
            elif sub == 'url.m3u8':
                mode, data = Narrtv.get_m3u8(req.args.get('ch_id'))
                if mode == 'text':
                    return data
                else:
                    return redirect(data)  
            
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())


    def scheduler_function(self):
        try:
            Narrtv.sync_yaml_data()
        except Exception as e:
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())