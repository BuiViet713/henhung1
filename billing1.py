#!/usr/bin/env python

import cv2
import os
import sys, getopt
import signal
import time
from edge_impulse_linux.image import ImageImpulseRunner

import RPi.GPIO as GPIO 
from hx711 import HX711

import requests
import json
from requests.structures import CaseInsensitiveDict

runner = None
show_camera = True

# Các biến liên quan đến cân và tính toán
c_value = 0
flag = 0
ratio = -1363.992

# Các biến toàn cục
id_product = 1
list_label = []
list_weight = []
count = 0
final_weight = 0
taken = 0

# Tên các sản phẩm
a = 'Apple'
b = 'Banana'
l = 'Lays'
c = 'Coke'

# Lấy thời gian hiện tại
def now():
    return round(time.time() * 1000)

# Tìm kiếm camera kết nối với thiết bị
def get_webcams():
    port_ids = []
    for port in range(5):
        print(f"Looking for a camera in port {port}:")
        camera = cv2.VideoCapture(port)
        if camera.isOpened():
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print(f"Camera {backendName} ({h} x {w}) found in port {port}")
                port_ids.append(port)
            camera.release()
    return port_ids

# Hàm để xử lý ngắt kết nối
def sigint_handler(sig, frame):
    print('Interrupted')
    if runner:
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# Hiển thị hướng dẫn sử dụng
def help():
    print('python classify.py <path_to_model.eim> <Camera port ID, only required when more than 1 camera is present>')

# Hàm tìm trọng lượng thông qua cảm biến
def find_weight():
    global c_value, hx
    if c_value == 0:
        print('Calibration starts')
        try:
            GPIO.setmode(GPIO.BCM)
            hx = HX711(dout_pin=20, pd_sck_pin=21)
            err = hx.zero()
            if err:
                raise ValueError('Tare is unsuccessful.')
            hx.set_scale_ratio(ratio)
            c_value = 1
        except (KeyboardInterrupt, SystemExit):
            print('Bye :)')
        print('Calibration ends')
    else:
        GPIO.setmode(GPIO.BCM)
        time.sleep(1)
        try:
            weight = int(hx.get_weight_mean(20))
            print(weight, 'g')
            return weight
        except (KeyboardInterrupt, SystemExit):
            print('Bye :)')

# Hàm gửi dữ liệu sản phẩm đến API
def post(label, price, final_rate, taken):
    global id_product, list_label, list_weight, count, final_weight, taken
    url = "https://automaticbilling.herokuapp.com/product"
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    data_dict = {
        "id": id_product,
        "name": label,
        "price": price,
        "units": "units",
        "taken": taken,
        "payable": final_rate
    }
    data = json.dumps(data_dict)
    resp = requests.post(url, headers=headers, data=data)
    print(f'Status Code: {resp.status_code}')
    id_product += 1  
    time.sleep(1)

    # Xóa danh sách sản phẩm và số lượng
    list_label.clear()
    list_weight.clear()
    count = 0
    final_weight = 0
    taken = 0

# Hàm so sánh và tính toán sản phẩm
def list_com(label, final_weight):
    global count, taken
    if final_weight > 2:    
        list_weight.append(final_weight)
        if count > 1 and list_weight[-1] > list_weight[-2]:
            taken += 1
    list_label.append(label)
    count += 1
    print('Count is', count)
    time.sleep(1)
    if count > 1 and list_label[-1] != list_label[-2]:
        print("New Item detected")
        print("Final weight is", list_weight[-1])
        rate(list_weight[-2], list_label[-2], taken)

# Hàm tính giá dựa trên nhãn sản phẩm
def rate(final_weight, label, taken):
    print(f"Calculating rate of {label}")
    if label == a:
        final_rate = final_weight * 0.01  
        price = 10
    elif label == b:
        final_rate = final_weight * 0.02
        price = 20
    elif label == l:
        final_rate = 1
        price = 1
    else:
        final_rate = 2
        price = 2
    post(label, price, final_rate, taken)

# Hàm chính để chạy phân loại
def main(argv):
    global flag, final_weight
    if flag == 0:
        find_weight()
        flag = 1

    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) == 0:
        help()
        sys.exit(2)

    model = args[0]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print(f'Loaded runner for "{model_info["project"]["owner"]} / {model_info["project"]["name"]}"')
            labels = model_info['model_parameters']['labels']

            if len(args) >= 2:
                videoCaptureDeviceId = int(args[1])
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    raise Exception('Cannot find any webcams')
                if len(args) <= 1 and len(port_ids) > 1:
                    raise Exception("Multiple cameras found. Add the camera port ID as a second argument.")
                videoCaptureDeviceId = int(port_ids[0])

            camera = cv2.VideoCapture(videoCaptureDeviceId)
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print(f"Camera {backendName} ({h} x {w}) in port {videoCaptureDeviceId} selected.")
                camera.release()
            else:
                raise Exception("Couldn't initialize selected camera.")

            next_frame = 0

            # Vòng lặp phân loại
            for res, img in runner.classifier(videoCaptureDeviceId):
                if next_frame > now():
                    time.sleep((next_frame - now()) / 1000)

                if "classification" in res["result"].keys():
                    print(f'Result ({res["timing"]["dsp"] + res["timing"]["classification"]} ms.)', end='')
                    for label in labels:
                        score = res['result']['classification'][label]
                        if score > 0.9:
                            final_weight = find_weight()
                            list_com(label, final_weight)
                            if label == a:
                                print('Apple detected')
                            elif label == b:
                                print('Banana detected')
                            elif label == l:
                                print('Lays detected')
                            else:
                                print('Coke detected')
                    print('', flush=True)
                next_frame = now() + 100
        finally:
            if runner:
                runner.stop()

if __name__ == "__main__":
    main(sys.argv[1:])
