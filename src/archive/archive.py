#!/usr/bin/python3
# -*- coding:utf-8 -*-

# 导入os库
import os
# 导入shutil库
import shutil
import subprocess
import json
import re
import argparse

from tqdm import tqdm

# 导入logging库
import logging

# 设置日志格式和级别
# logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logging.basicConfig(filename='archived.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_metadata(file_path):
    try:
        cmd = ['exiftool', '-j', file_path]
        output = subprocess.check_output(cmd)
        metadata = json.loads(output)[0]
    except Exception as e:
        metadata = None
        logging.error(f'{file_path} {e}')
    return metadata

def is_valid_date(text):
    pattern = r"\b\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2})?\b"
    match = re.fullmatch(pattern, text)
    return bool(match)

# 定义一个函数，根据文件名获取文件的创建日期
def get_date(filename):
    # 以二进制模式打开文件
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    date = metadata.get("DateTimeOriginal", metadata.get("CreationDate", metadata.get("MediaCreateDate", metadata.get("CreateDate", metadata.get("DateCreated", metadata.get("FileInodeChangeDate", None))))))
    return date if is_valid_date(date) else None

# 定义一个函数，根据日期获取季度
def get_quarter(date):
    # 如果日期为空，返回None
    if date is None:
        return None
    # 否则，根据月份判断季度
    month = int(date[5:7])
    if month in [1, 2, 3]:
        return 'Q1'
    elif month in [4, 5, 6]:
        return 'Q2'
    elif month in [7, 8, 9]:
        return 'Q3'
    elif month in [10, 11, 12]:
        return 'Q4'
    else:
        return None

def archive_obj(folder_path, target_path, obj):
    # 获取文件的完整路径
    file_path = os.path.join(folder_path, obj)
    # 如果文件是一个目录，跳过不处理
    if os.path.isdir(file_path):
        return
    # 获取文件的扩展名（不包含点）
    ext = os.path.splitext(obj)[1][1:]
    if ext.lower() not in ['mov', 'mp4', 'm4v', 'jpg', 'jpeg', 'heic', 'png', 'dng', 'gif']:
        return
    # 获取文件的创建日期
    date = get_date(file_path)
    if date is None:
        logging.info(f'date is invalid: {obj}')
        return
    # 获取文件的年份
    year = date[:4]
    # 获取文件的季度
    quarter = get_quarter(date)
    if quarter is None:
        return
    # 如果季度不为空，创建对应的子文件夹，并将文件复制到子文件夹内
    # 拼接子文件夹的路径
    subfolder_path = os.path.join(target_path, year, quarter)
    # 如果子文件夹不存在，创建子文件夹
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)
    # 如果目标文件不存在，将文件移动到子文件夹内
    target_file_path = os.path.join(subfolder_path, obj)
    if not os.path.exists(target_file_path):
        shutil.move(file_path, subfolder_path)
        logging.debug(f'Moved {obj} from {file_path} to {target_file_path}')
    else:
        logging.warning(f'File already exists, can not move {obj} from {file_path} to {target_file_path}')


# 定义一个函数，根据文件夹路径和目标路径，将文件夹内的文件按照创建日期分到对应年份的对应季度
def sort_files(folder_path, target_path):
    # 遍历文件夹内的所有文件
    objs = os.listdir(folder_path)
    process_objs = tqdm(objs)
    for obj in process_objs:
        process_objs.set_description('Processing '+ obj)
        archive_obj(folder_path, target_path, obj)
    process_objs.close()

parser = argparse.ArgumentParser(description='Process some material')
parser.add_argument('source', type=str,
                    help='source file path')
parser.add_argument('--destination', type=str,
                    help='destination file path (default: source file path)')

args = parser.parse_args()
print('source:' + args.source)
print('destination:' + (args.destination if args.destination else args.source))

# 调用函数，将源文件夹内的文件按照创建日期分到目标路径的对应年份的对应季度
sort_files(args.source, args.destination if args.destination else args.source)