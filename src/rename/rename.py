#!/usr/bin/python3
# -*- coding:utf-8 -*-

# 导入os库
import os
# 导入shutil库
import shutil
import subprocess

import re
import argparse
import glob
import hashlib
from decimal import Decimal
from tqdm import tqdm
import hashlib
# 导入logging库
import logging

from src.common.tool import *

# 设置日志格式和级别
# logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logging.basicConfig(filename='rename.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_md5(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

# 获取视频的元数据
def get_metadata_ff(file_path):
    try:
        cmd = ["ffprobe", "-loglevel", "quiet", "-show_format", "-show_streams", "-print_format", "json", file_path]
        output = subprocess.check_output(cmd)
        str = output.decode("utf-8")
        metadata_ff = json.loads(str)

    except Exception as e:
        metadata_ff = None
        logging.error(f'{file_path} {e}')
    return metadata_ff

def get_video_metadate_ff(metadata):
    streams = metadata.get("streams", None)
    v_ss = list(filter(lambda map: map['codec_type'] == 'video', streams))
    if len(v_ss) == 0:
        return None
    v_s = v_ss[0]
    return v_s

def is_valid_date(text):
    pattern = r"\b\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2})?\b"
    match = re.fullmatch(pattern, text)
    return bool(match)

def is_formatted_file_name(filename):
    if filename is None:
        return False
    # 判断是否已经是格式化过的文件名 如: 20230226-090511_2348.HEIC 20230226-090611_Mih-LF-CS_0226.HEIC
    return True if(re.match("^\d{8}-\d{6}_([a-zA-Z0-9.-]+_)?\d{4}.[a-zA-Z0-9]+$", filename)) is not None else False

def contains_keywords(s, keywords):
    if s is None:
        return False
    return any(keyword.lower() in s.lower() for keyword in keywords)

def live_photo_match_image(folder_path, filter_num):
    patter_str = rf'{filter_num}\.(' + '|'.join(IMAGE_EXT_LIST) + ')$'
    # print(patter_str)
    pattern = re.compile(patter_str, re.IGNORECASE)
    image_files = [file for file in glob.glob(folder_path + '/*') if pattern.search(file)]
    return image_files[0] if image_files else None

def exist_filter_file(folder_path, filter_file):
    file_list = glob.glob(os.path.join(folder_path, filter_file))
    return True if len(file_list) > 0 else False

def file_number(file_name, try_hash=False):
    """
    获取文件四位编号：
    - 排除日期之外的连续后四位数字作为编号 
    - 获取文件hash后转十进制取后四位作为编号
    """
    filename_nopath = os.path.basename(file_name)
    rm = re.search(r'\d{8}[-_]\d{6}', filename_nopath)
    file_name_rm = filename_nopath
    if rm:
        file_name_rm = filename_nopath.replace(rm.group(), "").strip()
    match = re.search(r'\d{4}(?=\D*$)', file_name_rm)
    if match:
        num_str = match.group()
        return num_str if len(num_str) == 4 else None
    elif try_hash is False:
        return None
    else:
        hex_dig = get_md5(file_name)
        decimal_dig = int(hex_dig, 16)
        str_digits = f'{decimal_dig}'
        last_four_digits_str = str_digits[-4:]
        return last_four_digits_str if len(last_four_digits_str) == 4 else None

def tag_m(metadata):
    # Make 拍摄的设备
    m = metadata.get("Make", None)
    if m is None:
        return None
    if contains_keywords(m, ["Apple", "iPhone"]):
        m = "iPh"
    elif contains_keywords(m, ["xiaomi", "mi"]):
        m = "MI"
    elif contains_keywords(m, ["SONY"]):
        m = "SON"
    elif contains_keywords(m, ["CANON"]):
        m = "CAN"
    elif contains_keywords(m, ["NIKON"]):
        m = "NIK"
    elif contains_keywords(m, ["casio"]):
        m = "CAS"
    elif contains_keywords(m, ["GoPro"]):
        m = "GoP"
    elif contains_keywords(m, ['ZTE']):
        m = 'ZTE'
    elif contains_keywords(m, ['FUJIFILM']):
        m = 'FUJ'
    elif contains_keywords(m, ['Nokia']):
        m = 'Nokia'
    elif contains_keywords(m, ['HUAWEI']):
        m = 'HUAWEI'
    elif contains_keywords(m, ['Smartisan']):
        m = 'Smartisan'
    elif contains_keywords(m, ['Yiruikecorp']):
        m = 'Yiruikecorp'
    elif contains_keywords(m, ['OnePlus']):
        m = 'OnePlus'
    elif contains_keywords(m, ['vivo']):
        m = 'vivo'
    elif contains_keywords(m, ['DJI']):
        m =  'DJI'
    else:
        raise ValueError(f'convert failure: {m}')
        # return None
    return "M" + m

def tag_c(metadata):
    c = ""
    ss = metadata.get("UserComment", None)
    if contains_keywords(ss, ["Screenshot"]):
        c = c + "S"
    if len(c) > 0:
        return "C" + c
    else:
        return None
        
def tag_l(metadata):
    l = metadata.get("LensID", None)
    if l is None:
        return None
    if contains_keywords(l, ["front"]):
        l = "F"
    else:
        return None
    return "L" + l

def calculate_resolution(width, height):
    resolutions = {
        (720, 480): 'SD',
        (1280, 720): 'HD',
        (1920, 1080): 'FHD',
        (2048, 1080): '2K',
        (3840, 2160): '4K',
        (7680, 4320): '8K'
    }
    return resolutions.get((width, height), f"{width}x{height}")
    # return resolutions.get((width, height), None)

def tag_ff_resolutation(metadata):
    v_s = get_video_metadate_ff(metadata)
    if v_s is None:
        return None
    resolution = calculate_resolution(v_s.get('width', None), v_s.get('height', None))
    return resolution

def remove_exponent(num):
    return num.to_integral()if num == num.to_integral() else num.normalize()

def tag_ff_frame_rate(metadata):
    v_s = get_video_metadate_ff(metadata)
    if v_s is None:
        return None
    fps = v_s.get('avg_frame_rate', None)
    if fps is None:
        return None
    fps = fps.split("/")
    if fps and len(fps) == 2:
        denominator = int(fps[0])
        numerator = int(fps[1])
        result = denominator / numerator
        result = Decimal(f'{result}').quantize(Decimal('0.00'))
        result = remove_exponent(result)
        return f'{result}FPS'
    return None

def tag_ff_log(metadata):
    v_s = get_video_metadate_ff(metadata)
    if v_s is None:
        return None
    side_list = v_s.get('side_data_list', None)
    if side_list is None:
        return None
    side_data = side_list[0] if len(side_list) > 0 else None
    if side_data is None:
        return None
    data_type = side_data.get('side_data_type', None)
    if contains_keywords(data_type, ['DOVI']):
        return 'DOVI'
    return None

def tag_ff_encoder(metadata):
    v_s = get_video_metadate_ff(metadata)
    if v_s is None:
        return None
    tags = v_s.get('tags', None)
    if tags is None:
        return None
    encoder = tags.get('encoder', None)
    if encoder is None:
        return None
    elif contains_keywords(encoder, ['h.264', 'h264', 'hevc']):
        f_encoder = 'HEVC'
    elif contains_keywords(encoder, ['h.265', 'h265', 'avc']):
        f_encoder = 'AVC'
    else:
        f_encoder = encoder.strip()
        if len(f_encoder) > 0:
            raise ValueError(f'encoder convert failure: {encoder}')
    return f_encoder if len(f_encoder) > 0 else None


def formatted_tags(filename):
    if is_live_photo_VID(filename):
        raise ValueError(f'livephoto rename failure: {filename}')
    if is_IMG(filename):
        return formated_tags_IMG(filename)
    elif is_VID(filename):
        return formated_tags_VID(filename)
    return None

def formated_tags_VID(filename):
    metadata_ff = get_metadata_ff(filename)
    if metadata_ff is None:
        return None
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    tags = list()
    m = tag_m(metadata)
    if m is None:
        if args.loose is False:
            logging.error(f'[exiftool] make is invalid: {filename}')
            return None
    else:
        tags.append(m)
    resolution = tag_ff_resolutation(metadata_ff)
    if resolution is None:
        logging.error(f'[ffmpeg] resolution is invalid: {filename}')
        return None
    else:
        tags.append(resolution)
    fps = tag_ff_frame_rate(metadata_ff)
    if fps is None:
        logging.error(f'[ffmpeg] fps is invalid: {filename}')
        return None
    else:
        tags.append(fps)
    log = tag_ff_log(metadata_ff)
    if log is None:
        logging.warning(f'[ffmpeg] log/raw is invalid: {filename}')
    else:
        tags.append(log)
    encoder = tag_ff_encoder(metadata_ff)
    if encoder is None:
        if args.loose is False:
            logging.error(f'[ffmpeg] encoder is invalid: {filename}')
            return None
    else:
        tags.append(encoder)
    if len(tags) > 0:
       return "-".join(tags)
    return None

def formated_tags_IMG(filename):
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    m = tag_m(metadata)
    tags = list()
    if m is not None:
        tags.append(m)
    else:
        logging.warning(f'[exiftool] make is invalid: {filename}')
    l = tag_l(metadata)
    if l is not None:
        tags.append(l)
    c = tag_c(metadata)
    if c is not None:
        tags.append(c)
    if len(tags) > 0:
       return "-".join(tags)
    return None    

# 定义一个函数，根据文件名获取文件的创建日期
def get_date(filename):
    # 以二进制模式打开文件
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    date = metadata.get("DateTimeOriginal", metadata.get("CreateDate", metadata.get("CreationDate", metadata.get("MediaCreateDate", metadata.get("DateCreated", metadata.get("FileInodeChangeDate", None))))))
    return date if is_valid_date(date) else None

def formatted_date(date):
    # eg "2023:05:12 11:42:11+08:00" => "20230512-114211"
    pattern = r"\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}"
    mats = re.search(pattern, date)
    return str(mats.group()).replace(":", "").replace(" ", "-") if mats else None
    
def need_ignore_file(folder_path, obj):
    # 获取文件的完整路径
    file_path = os.path.join(folder_path, obj)
    # 如果文件是一个目录，跳过不处理
    if os.path.isdir(file_path):
        return True
    # 获取文件的扩展名（不包含点）
    f, e = os.path.splitext(obj)
    ext = e[1:]
    if ext.lower() not in FILE_EXT_LIST:
        return True
    if args.ignore_formatted is False:
        if is_formatted_file_name(obj):
            return True
    return False

def generate_new_filename_prefix(folder_path, obj):
    # 获取文件的完整路径
    file_path = os.path.join(folder_path, obj)

    # 获取文件的创建日期
    date = get_date(file_path)
    if date is None:
        logging.error(f'date is invalid: {obj}')
        return None
    items = list()
    f_date = formatted_date(date)
    if f_date is None:
        return None
    else:
        items.append(f_date)

    f_tags = formatted_tags(file_path)
    if f_tags is None:
        if args.loose is False:
            logging.error(f'tags is invalid: {obj}')
            return None
    else:
        items.append(f_tags)

    f_num = file_number(file_path, True)
    if f_num is None:
        logging.error(f'number is invalid: {obj}')
        return None
    else:
        items.append(f_num)
    new_file_name_prefix = '_'.join(items)
    return new_file_name_prefix

def generate_new_filename(folder_path, obj):
    # 获取文件的完整路径
    file_path = os.path.join(folder_path, obj)

    _, e = os.path.splitext(obj)

    # 1、是否为 livephoto
    if is_live_photo_VID(file_path):
        live_photo_num = file_number(file_path)
        if live_photo_num is None:
            logging.error(f'livephoto number is error, file: {obj}')
            return None
        t_file = live_photo_match_image(os.path.dirname(file_path), live_photo_num)
        if t_file is None:
            logging.error(f'livephoto not found match image, file: {obj}')
            return None
        t_prefix = generate_new_filename_prefix(folder_path, t_file)
        if t_prefix is not None:
            return t_prefix + e
        else:
            return None
    prefix = generate_new_filename_prefix(folder_path, obj)
    if prefix is None:
        return None
    else:
        return prefix + e

def list_md5(file):
    md5s = set()
    with open(file, 'r') as f:
        line = f.readline()
        while line:
            items = line.split('<=', -1)
            md5s.add(items[0].strip())
            line = f.readline()
    return md5s

def scan_dir(source):
    info_file = os.path.join(source, 'rename_info.txt')
    file_txt = open(info_file, 'a')

    md5s = list_md5(info_file)

    # 遍历文件夹内的所有文件
    objs = os.listdir(source)
    process_objs = tqdm(objs)
    for obj in process_objs:
        process_objs.set_description('Processing '+ obj)
        if need_ignore_file(source, obj):
            continue
        g_new_file_name = generate_new_filename(source, obj)
        if is_formatted_file_name(g_new_file_name) is False:
            logging.error(f'formated file name is error: {obj} => {g_new_file_name}')
            continue
        g_file = os.path.join(source, obj)
        g_new_file = os.path.join(source, g_new_file_name)
        if os.path.exists(g_new_file):
            logging.warning(f'File already exists, can not rename {obj} => {g_new_file_name}')
            continue
        md5 = get_md5(g_file)
        if args.ignore_formatted is False:
            if md5 in md5s:
                logging.warning(f'md5 already exists, can not rename {obj} => {g_new_file_name} => {md5}')
                continue
        if args.rename is False:
            logging.info(f'preview rename: {md5} <= {g_new_file_name} <= {obj}')
            continue
        logging.info("rename: " + g_file + " => " + g_new_file)
        file_txt.write(f'{md5} <= {g_new_file_name} <= {obj}\n')
        md5s.add(md5)
        os.rename(g_file, g_new_file)
    process_objs.close()

    file_txt.close()


parser = argparse.ArgumentParser(description='rename material')
parser.add_argument('source', type=str,
                    help='source file path')
parser.add_argument('--loose', dest='loose', action='store_true', default=False,
                    help='loose exif or ffmpeg tags')
parser.add_argument('--rename', dest='rename', action='store_true', default=False,
                    help='rename file')
parser.add_argument('--ignore_formatted', dest='ignore_formatted', action='store_true', default=False,
                    help='ignore formated file')

args = parser.parse_args()
print(f'source: {args.source}')
print(f'--loose: {args.loose}')
print(f'--rename: {args.rename}')
print(f'--ignore_formatted: {args.ignore_formatted}')

if __name__ == "__main__":
    # 调用函数，将源文件夹内的文件按照指定格式进行重新命名
    scan_dir(args.source)
    # scan_dir("/Users/heminwon/Documents/HeminWon/learn/python/IMG_TEST")
