import cv2
import os
import sys
import signal
import time
import random
from EmulatorGUI import GPIO  # Giả lập GPIO

# Giả lập cảm biến cân nặng
class HX711:
    def __init__(self):
        pass
    
    def get_weight(self):
        return random.uniform(0, 500)  # Giả lập cân nặng ngẫu nhiên từ 0 đến 500g

# Biến toàn cục
show_camera = True
flag = 0
id_product = 1
list_label = []
list_weight = []
count = 0
final_weight = 0
taken = 0
c_value = 0  # Dùng trong hàm find_weight
products = {
    'Apple': 10,
    'Banana': 20,
    'Lays': 1,
    'Coke': 2
}

# Thiết lập các chân GPIO cho nút và đèn
BUTTON_WEIGHT_PIN = 15  # Chân 15 để xác nhận cân nặng
BUTTON_VIDEO_PIN = 18   # Chân 18 để xác nhận video
LED_PIN = 14            # Chân 14 để bật đèn khi xác nhận cân nặng

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_WEIGHT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pull-up resistor
GPIO.setup(BUTTON_VIDEO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # Pull-up resistor
GPIO.setup(LED_PIN, GPIO.OUT)

# Hàm lấy thời gian hiện tại
def now():
    return round(time.time() * 1000)

# Hàm xử lý ngắt kết nối
def sigint_handler(sig, frame):
    print('Interrupted')
    GPIO.cleanup()  # Dọn dẹp GPIO
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# Hiển thị hướng dẫn sử dụng
def help():
    print(r'python classify.py <video_path>')

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

        if count > 1 and list_label[-1] != list_label[-2]:
            print("New Item detected")
            print("Final weight is", list_weight[-1])
            rate(list_weight[-2], list_label[-2], taken)

# Hàm tính giá dựa trên nhãn sản phẩm
def rate(final_weight, label, taken):
    print(f"Calculating rate of {label}")
    if label in products:
        final_rate = final_weight * 0.01 * products[label]
        print(f"Product: {label}, Weight: {final_weight} g, Price: {products[label]}, Payable: {final_rate:.2f}")
    else:
        print(f"Unknown product: {label}")

# Hàm mở video từ webcam hoặc file
def get_webcams(video_path):
    print("Opening video from: %s" % video_path)
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print("Cannot open video at:", video_path)
        return []

    backendName = "Video Source"
    w = int(video.get(3))  # width
    h = int(video.get(4))  # height
    port_ids = [0]  # Giả định có 1 video và gán port ID là 0

    print("Video %s (%s x %s) opened successfully." % (backendName, h, w))
    video.release()
    
    return port_ids

# Hàm tìm cân nặng giả lập
def find_weight():
    global c_value
    if c_value == 0:
        print('Calibration starts')
        GPIO.setmode(GPIO.BCM)
        c_value = 1
        print('Calibration ends')
        return None
    else:
        GPIO.setmode(GPIO.BCM)
        time.sleep(1)
        weight = random.randint(1, 1000)
        print(weight, 'g')
        return weight

# Hàm giả lập kết quả phân loại
def fake_classification(img):
    # Tạo ngẫu nhiên nhãn sản phẩm và xác suất (giả lập)
    labels = ['Apple', 'Banana', 'Lays', 'Coke']
    scores = [random.uniform(0.8, 1.0) for _ in labels]  # Điểm số ngẫu nhiên cho mỗi nhãn
    classification_result = {label: score for label, score in zip(labels, scores)}

    # Chọn nhãn có xác suất cao nhất làm kết quả phân loại
    best_label = max(classification_result, key=classification_result.get)
    return best_label, classification_result

# Hàm xác nhận nhấn nút và điều khiển đèn LED
def wait_for_button_press(button_pin):
    while GPIO.input(button_pin) == 1:  # Nút không được nhấn (chân HIGH)
        time.sleep(0.1)  # Đợi một chút
    GPIO.output(LED_PIN, GPIO.HIGH)  # Sáng đèn khi nhấn nút

# Hàm chính để chạy phân loại
def main(argv):
    global final_weight

    if len(argv) < 1:
        help()
        sys.exit(2)

    video_path = argv[0]

    print('VIDEO: ' + video_path)

    # Giả lập phân loại thay vì sử dụng ImageImpulseRunner
    print("Waiting for video confirmation...")
    wait_for_button_press(BUTTON_VIDEO_PIN)  # Chờ nhấn nút video
    print("Video confirmed")
    
    camera = cv2.VideoCapture(video_path)
    if not camera.isOpened():
        print("Couldn't open video file.")
        return

    hx711 = HX711()  # Khởi tạo giả lập cảm biến cân nặng

    # Vòng lặp phân loại
    while True:
        ret, img = camera.read()
        if not ret:
            break

        # Giả lập đầu vào cân nặng
        print("Waiting for weight confirmation...")
        wait_for_button_press(BUTTON_WEIGHT_PIN)  # Chờ nhấn nút cân nặng

        final_weight = hx711.get_weight() if c_value == 0 else find_weight()
        print(f"Weight: {final_weight:.2f} g")

        # Tắt đèn sau khi lấy cân nặng
        GPIO.output(LED_PIN, GPIO.LOW)

        # Giả lập phân loại hình ảnh
        label, result = fake_classification(img)
        print(f"Fake Classification Result: {label} with confidence {result[label]:.2f}")
        
        # Gọi hàm xử lý sau khi có kết quả phân loại
        list_com(label, final_weight)

        # Kết thúc sau khi có kết quả cân nặng và trả về tính toán
        rate(final_weight, label, taken)
        print("Exiting process")
        break  # Thoát khỏi vòng lặp khi hoàn thành

    camera.release()
    GPIO.output(LED_PIN, GPIO.LOW)  # Tắt đèn LED khi kết thúc chương trình
    GPIO.cleanup()  # Dọn dẹp GPIO

if __name__ == "__main__":
    main(sys.argv[1:])
