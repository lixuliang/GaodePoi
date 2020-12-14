# -*- coding: utf-8 -*-
"""
Created on Wed Dec  9 09:55:22 2020
@author: ecidi

以多边形方式爬取
不考虑多线程
key消耗完无法自动结束程序
需要进一步预处理（拼接、去重）
"""

import requests
import math
import json
from multiprocessing import Process
from multiprocessing import Manager
import time
import hashlib
import random as rm
from transCoordinateSystem import gcj02_to_wgs84
import area_boundary as a_b
import area_grid as a_g

#################################################需要修改###########################################################

## TODO 1.初始划分的网格距离，2km-5km最佳，建议如果是数量比较多的用1km或2km，如餐厅，企业。数据量少的用5km或者更大，如大学
initial_window_size = 10000

## TODO 2. 城市编码，参见高德城市编码表，注意需要用adcode列的编码
# 也可以直接用坐标来表示范围
initial_city_code = '150100'
initial_city = '杭州'   # a_b.getlnglat('杭州', 'key')
initial_city_boundary = [118.344,  120.722, 29.188, 30.567]   

## TODO 3. POI类型编码，类型名或者编码都行，具体参见《高德地图POI分类编码表.xlsx》
# types_string = '010000|020000|030000|040000|050000|060000|070000|080000|090000|100000|110000|120000|130000|140000|150000|160000|170000|180000|190000|200000|210000|220000|970000|990000'
types_string = '190000'
types_list = types_string.split('|')

## TODO 4. 高德开放平台密钥
gaode_key_list = ['']

############################################以下#######################################################################
Prefix_url = 'https://restapi.amap.com/v3/place/polygon?parameters'
today_count = 0

# True时更换key
def getKey(use_key, invalidate=False):
    if invalidate:
        print(f'AK:{use_key}失效。剩余{len(gaode_key_list) - 1}个key')
        gaode_key_list.remove(use_key)
    if len(gaode_key_list) == 0:
        with open('data/error.csv', 'a+', encoding="utf-8") as f:
            f.write("key耗尽\n")
        raise Exception("key耗尽")
    else:
        use_key = gaode_key_list[0]
        return use_key

# 请求数据
def request_url(url, parameters):
    '''
    Returns
    0,0:  异常
    1,{}: 正常结果   
    '''    
    parameters['key'] = gaode_key_list[0]
    while True:
        try:
            time.sleep(0.1)
            response = requests.get(url, params=parameters, timeout=5) 
        except Exception as e:
            print('获取数据出现异常 --->>> ',parameters)
            return 0,0
        try:
            data_object = json.loads(response.text)
        except Exception as e:
            print('json文本解析数量出现异常 --->>> ', response.text)
            return 0,0
        if data_object['infocode'] != "10000":
            if data_object['infocode'] == "10001" or data_object['infocode'] != "10003":
                print('配额超限，更换KEY重试')
                with open('data/error.csv', 'a+', encoding="utf-8") as f:
                        f.write('key {0} 已失效\n'.format(parameters['key']))
                use_key = getKey(parameters['key'], True)
                parameters['key'] = use_key
                continue
            else:
                print('返回结果出现未知错误')
                return 0,0
        return 1,data_object

# 
def get_pois(params):
    global today_count
    flag, res_data = request_url(Prefix_url, params)
    # 请求语句有问题跳过
    if flag == 0:
        with open('data/error.csv', 'a+', encoding="utf-8") as f:
            f.write("{0} 在计数时出错跳出\n".format(params['polygon']))
        return 
    else:
        poi_number = eval(res_data['count'])
        print('找到要素{}个'.format(poi_number))
        if poi_number == 0:
            # 如果此区域不存在点                
            return
        # 如果翻页后，此页没有
        elif len(res_data['pois']) == 0:
            return
        # 超过了850个，需要划分小格子。把当前区域划分成4个小格子
        elif poi_number >= 850:
            with open('data/error.csv', 'a+', encoding="utf-8") as f:
                f.write('{0} 需要划分更小单元\n'.format(params['polygon']))
            print ('{0} 需要划分更小单元'.format(params['polygon']))
            new_params = a_g.cut_polygon(params['polygon'])
            for i in range(4):                    
                new_params_temp = {
                    'polygon': new_params[i],
                    'types': params['types'],
                    'offset': 20,
                    'output': 'JSON' 
                    }
                params_list.append(new_params_temp)
            return
        else:                
            request_count = math.floor(int(poi_number) / 20 + 1)
            all_poi = list()
            for page in range(request_count):
                print ('{0} 分页开始爬取'.format(page + 1))
                params['page'] = page + 1
                flag, res_data = request_url(Prefix_url, params)
                if flag == 0:
                    with open('data/error.csv', 'a+', encoding="utf-8") as f:
                        f.write('{0} 单页爬取出现异常 page {1}\n'.format(params['polygon'], page + 1))
                    return
                records_list = call_back_fun(res_data)
                if records_list == False:
                    with open('data/error.csv', 'a+', encoding="utf-8") as f:
                        f.write('{0} 单页json文本解析出现异常 page {1}\n'.format(params['polygon'], page + 1))
                    return
                for record in records_list:
                    all_poi.append(record)
                    
            with open('data/types{0}.csv'.format(params['types']), 'a+', encoding="utf-8") as f:
                for record in all_poi:
                    output_str = ''
                    for item in record:
                        output_str += str(item)
                        output_str += ','
                    output_str = output_str[:-1] + '\n'
                    f.write(output_str)          
            with open('data/log{0}.csv'.format(params['types']), 'a+', encoding="utf-8") as f:
                f.write('now {0} has poi {1} is over\n'.format(params['polygon'],len(all_poi)))
            today_count += len(all_poi)
            # all_poi.clear()

# 解析记录内容
def call_back_fun(data_object):
    data_list = list()
    try:
        # 解析为Json字符串
        poi_number = data_object['count']
        poi_list = data_object['pois']
        for one_poi in poi_list:
            poi_name = ""
            if "name" in one_poi.keys():
                poi_name = one_poi['name']
            poi_type = ""
            if "type" in one_poi.keys():
                poi_type = one_poi['type']
            address = ""
            if "address" in one_poi.keys():
                address = one_poi['address']
            longitude = 0
            latitude = 0
            if "location" in one_poi.keys():
                longitude_t, latitude_t = one_poi['location'].split(',')
                longitude, latitude = gcj02_to_wgs84(eval(longitude_t), eval(latitude_t))
            province_name = ""
            if "pname" in one_poi.keys():
                province_name = one_poi['pname']
            city_name = ""
            if "cityname" in one_poi.keys():
                city_name = one_poi['cityname']
            address_name = ""
            if "adname" in one_poi.keys():
                address_name = one_poi['adname']
            type_code = ""
            if "typecode" in one_poi.keys():
                type_code = one_poi['typecode']
            data_list.append([province_name, city_name, address_name, poi_name, poi_type, type_code, longitude, latitude, address])
        # print(len(data_list))
    except Exception as e:
        print('json文本解析出现异常  --->>> {0}'.format(data_object))
        return False
    return data_list
  

if __name__ == '__main__':   
    rectangle_list = a_g.boundary_to_grid_points(initial_city_boundary, initial_window_size)
    params_list = list()
    with open('data/error.csv', 'a+', encoding="utf-8") as f:
        f.write('start on {0}\n'.format(time.strftime('%Y%m%d%H%M%S', time.localtime())))
    
    # 处理得到多条参数记录用于循环请求
    for one_type in types_list:
        with open('data/types{0}.csv'.format(one_type), 'w', encoding="utf-8") as f:
            f.write('\n')
        with open('data/log{0}.csv'.format(one_type), 'w', encoding="utf-8") as f:
            f.write('\n')        
        for one_rect in rectangle_list:
            polygon = "{0},{1}|{2},{3}".format(one_rect[0], one_rect[1], one_rect[2], one_rect[3])
            parameters = {
                'polygon': polygon,
                'types': one_type,
                'offset': 20,
                'output': 'JSON' 
                }
            params_list.append(parameters)
    print('now initial params_list is end')    
    
    while len(params_list) != 0:
        params = params_list.pop(0) 
        print('now {0} is on processes'.format(params['polygon']))
        get_pois(params) 
        time.sleep(3)
    
    # 等待所有进程结束    
    print('today count {0} finish'.format(today_count))
    with open('data/error.csv', 'a+', encoding="utf-8") as f:
         f.write('today count {0} finish\n'.format(today_count))        