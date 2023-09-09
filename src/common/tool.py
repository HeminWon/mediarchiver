#!/usr/bin/python3
# -*- coding:utf-8 -*-

import os
import json
import logging
import subprocess


VIDEO_EXT_LIST = ['mp4', 'm4v', 'avi', 'mov']
IMAGE_EXT_LIST = ['jpg', 'png', 'mpg', 'thm', 'bmp', 'jpeg', 'heic','dng', 'gif']
FILE_EXT_LIST  = VIDEO_EXT_LIST + IMAGE_EXT_LIST

def is_IMG(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in IMAGE_EXT_LIST

def is_VID(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in VIDEO_EXT_LIST

def get_metadata(file_path):
    try:
        cmd = ['exiftool', '-j', file_path]
        output = subprocess.check_output(cmd)
        metadata = json.loads(output)[0]
    except Exception as e:
        metadata = None
        logging.error(f'{file_path} {e}')
    return metadata