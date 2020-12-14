# -*- coding: utf-8 -*-
"""
Created on Wed Dec  9 17:50:54 2020

@author: ecidi
"""

import numpy as np
import math

def generate_grids(start_long,end_long,start_lat,end_lat,resolution):
    """
    根据起始的经纬度和分辨率，生成需要需要的网格.
    方向为左上，右下，所以resolution应为 负数->0.1，否则为空
    :param start_long:
    :param start_lat:
    :param end_long:
    :param end_lat:
    :param resolution:
    :return:
    """
    # assert start_long < end_long,'需要从左上到右下设置经度，start的经度应小于end的经度'
    # assert start_lat > end_lat,'需要从左上到右下设置纬度，start的纬度应大于end的纬度'
    if start_long > end_long:
        start_long, end_long = end_long, start_long
    if start_lat < end_lat:
        start_lat, end_lat = end_lat, start_lat
    assert resolution > 0, 'resolution应大于0'


    grids_lib=[]
    longs = np.arange(start_long,end_long,resolution)
    if longs[-1] != end_long:
        longs = np.append(longs,end_long)

    lats = np.arange(start_lat,end_lat,-resolution)
    if lats[-1] != end_lat:
        lats = np.append(lats,end_lat)
    for i in range(len(longs)-1):
        for j in range(len(lats)-1):
            grids_lib.append([round(float(longs[i]),6),round(float(lats[j]),6),round(float(longs[i+1]),6),round(float(lats[j+1]),6)])
            #yield [round(float(longs[i]),6),round(float(lats[j]),6),round(float(longs[i+1]),6),round(float(lats[j+1]),6)]
    return grids_lib


def distance_spatial(s_lon, s_lat, e_lon, e_lat):
    """
    http://www.movable-type.co.uk/scripts/latlong.html
    根据经纬度计算两点之间距离
    """
    s_rad_lat = s_lat * math.pi / 180.0
    e_rad_lat = e_lat * math.pi / 180.0
    a = (s_lat - e_lat) * math.pi / 180.0
    b = (s_lon - e_lon) * math.pi / 180.0
    # c = math.pow(math.sin(a / 2), 2) + math.cos(s_rad_lat) * math.cos(e_rad_lat) * math.pow(math.sin(b / 2), 2)
    # s = 2 * math.atan2(math.sqrt(c), math.sqrt(1-c))
    s = 2 * math.asin(math.sqrt(math.pow(math.sin(a / 2), 2) 
                                + math.cos(s_rad_lat) * math.cos(e_rad_lat) 
                                * math.pow(math.sin(b / 2), 2)))    
    s = s * 6378137
    s = math.floor(s * 10000) / 10000.0
    return s


def boundary_to_center_points(boundary, interval_distance):
    """
    将整个研究区域按指定分辨率->米划分，取每个格网中心点，便于后续以圆心-周围方式爬取
    :return
    """
    point_list = list()
    # 计算横纵向的距离
    distance_x = distance_spatial(boundary[0], 0.5 * (boundary[2] + boundary[3]), boundary[1], 0.5 * (boundary[2] + boundary[3]))
    distance_y = distance_spatial(0.5 * (boundary[0] + boundary[1]), boundary[2], 0.5 * (boundary[0] + boundary[1]), boundary[3])

    # 计算横纵向的网格个数，
    x_count = math.floor(distance_x / interval_distance) + 1
    y_count = math.floor(distance_y / interval_distance) + 1

    d_x = (boundary[1] - boundary[0]) / x_count
    d_y = (boundary[3] - boundary[2]) / y_count

    # 构造中心点
    for i in range(x_count + 1):
        for j in range(y_count + 1):
            point_list.append([boundary[0] + i * d_x, boundary[2] + j * d_y])

    return point_list


def boundary_to_grid_points(boundary, interval_distance):
    """
    将整个研究区域按指定分辨率->米划分，便于后续以多边形方式爬取
    :boundary: start_lon, < end_lon, start_lat, < end_lat 左下右上
    :return:  左上右下
    """
    rectangle_list = list()

    # 计算横纵向的距离
    distance_x = distance_spatial(boundary[0], 0.5 * (boundary[2] + boundary[3]), boundary[1], 0.5 * (boundary[2] + boundary[3]))
    distance_y = distance_spatial(0.5 * (boundary[0] + boundary[1]), boundary[2], 0.5 * (boundary[0] + boundary[1]), boundary[3])

    # 计算横纵向的网格个数，
    x_count = math.floor(distance_x / interval_distance) + 1
    y_count = math.floor(distance_y / interval_distance) + 1

    d_x = (boundary[1] - boundary[0]) / x_count
    d_y = (boundary[3] - boundary[2]) / y_count

    for i in range(x_count):
        for j in range(y_count):
            top_left_x = boundary[0] + i * d_x - 0.00001
            top_left_y = boundary[3] - j * d_y + 0.00001
            bottom_right_x = boundary[0] + (i + 1) * d_x + 0.00001
            bottom_right_y = boundary[3] - (j + 1) * d_y - 0.00001
            rectangle_list.append([top_left_x, top_left_y, bottom_right_x, bottom_right_y])

    return rectangle_list

def cut_polygon(polygon):
    """
    将过大的区域分成四个区域
    """
    top_left, bottom_right = polygon.split('|')
    top_left_x, top_left_y = top_left.split(',')
    bottom_right_x, bottom_right_y = bottom_right.split(',')
    half_x = float(top_left_x) + (float(bottom_right_x) - float(top_left_x)) / 2.0
    half_y = float(bottom_right_y) + (float(top_left_y) - float(bottom_right_y)) / 2.0
    new_polygon_1 = "{0},{1}|{2},{3}".format(float(top_left_x), float(top_left_y), float(half_x), float(half_y))
    new_polygon_2 = "{0},{1}|{2},{3}".format(float(half_x), float(top_left_y), float(bottom_right_x), float(half_y))
    new_polygon_3 = "{0},{1}|{2},{3}".format(float(top_left_x), float(half_y), float(half_x), float(bottom_right_y))
    new_polygon_4 = "{0},{1}|{2},{3}".format(float(half_x) - 0.00001, float(half_y) + 0.00001, float(bottom_right_x) + 0.00001, float(bottom_right_y) - 0.00001)
    
    return [new_polygon_1,new_polygon_2,new_polygon_3,new_polygon_4]

# generate_grids(118.344,  120.722, 30.567, 29.188,0.1)
# boundary_to_grid_points([118.344,  120.722, 30.567, 29.188],10000)