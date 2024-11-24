# Import các thư viện cần thiết
import sys
from PySide6 import QtCore, QtWidgets, QtGui  # Thư viện PySide6 dùng để tạo GUI
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
import cv2  # OpenCV dùng để xử lý hình ảnh
import numpy as np  # Thư viện hỗ trợ thao tác với mảng
import serial.tools.list_ports  # Thư viện hỗ trợ thao tác với cổng Serial
import dlib  # Thư viện dlib dùng để phát hiện khuôn mặt
from imutils import face_utils  # Thư viện hỗ trợ các tiện ích liên quan đến khuôn mặt
from scipy.spatial import distance  # Tính khoảng cách Euclidean giữa các điểm
from pygame import mixer  # Thư viện dùng để phát âm thanh
import rpc  # Thư viện hỗ trợ giao tiếp RPC
from datetime import datetime
import requests
import paho.mqtt.client as mqtt
# Khởi tạo thư viện âm thanh và tải nhạc
mixer.init()
mixer.music.load("music.wav")


## Define ##
MQTT_BROKER_URL ="b8fe3c14237c4aefb0823289870c4d8b.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_CLIENT_ID = "COMPUTER"
MQTT_USER = "VuUwU2"
MQTT_PW = "VuUwU@123"
MQTT_CLEAN_SESSION = True
MQTT_KEEP_ALIVE = 360
MQTT_VER = 3

buzzer_flags = 0

## MQTT ##
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,MQTT_CLIENT_ID, clean_session=MQTT_CLEAN_SESSION, protocol=MQTT_VER)
client.username_pw_set(MQTT_USER, MQTT_PW)
client.tls_set()  # Uses default SSL/TLS settings 

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connected successfully")
    else:
        print(f"Failed to connect, reason code {reason_code}")

def on_subscribe(mqttc, obj, mid, reason_code_list, properties):
    print("Subscribed: " + str(mid) + " " + str(reason_code_list))

def on_message(client, userdata, message):
	global buzzer_flags
	print(f"Messgae: Topic'{message.topic}' and msg:'{str(message.payload.decode().strip().lower())}'")
	if message.topic == "buzzer" and message.payload.decode().strip().lower() == "pressed":
		buzzer_flags = 0
	# if message.topic == "date":
	# 	print(f"GPS date: {message.payload.decode()}")
	# if message.topic == "Latitude":
	# 	print(f"Latitude: {message.payload.decode()}")
	# if message.topic == "Longitude":
	# 	print(f"Longitude: {message.payload.decode()}")
client.on_connect = on_connect
client.on_message = on_message
client.on_subscribe = on_subscribe
client.connect(MQTT_BROKER_URL, MQTT_PORT, keepalive=MQTT_KEEP_ALIVE)
client.subscribe("#",0)
client.loop_start()

def send_msg(topic, msg):
    client.publish(topic,msg)
    print(f"Have published {topic}: {msg}")

# Hằng số cho việc phát hiện buồn ngủ
thresh = 0.25  # Ngưỡng cho tỷ lệ mắt mở
frame_check = 60  # Số khung hình kiểm tra drowsiness

# Tải mô hình phát hiện khuôn mặt của dlib
detector = dlib.get_frontal_face_detector()
predict = dlib.shape_predictor("models/shape_predictor_68_face_landmarks.dat")  # Đường dẫn đến file model của dlib

# Định nghĩa lớp ImgLabel kế thừa QLabel để nhận sự kiện nhấn chuột
class ImgLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()  # Tín hiệu được phát khi nhấn chuột

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        self.status = 'CLICKED'  # Đánh dấu trạng thái khi nhấn chuột
        self.pos_1st = ev.position()  # Ghi lại vị trí nhấn chuột
        self.clicked.emit()  # Phát tín hiệu nhấn chuột
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        self.status = 'RELEASED'  # Đánh dấu trạng thái khi thả chuột
        self.pos_2nd = ev.position()  # Ghi lại vị trí thả chuột
        self.clicked.emit()  # Phát tín hiệu thả chuột
        return super().mouseReleaseEvent(ev)

# Định nghĩa lớp EspCamWidget kế thừa QWidget để xây dựng giao diện chính
class EspCamWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        # Khởi tạo các biến
        self.rpc_master = None
        self.capture_timer = None
        self.drowsy_counter = 0  # Biến đếm số lần phát hiện buồn ngủ liên tiếp
        self.music_playing = False  # Biến trạng thái của nhạc
        self.drowsy_count = 0  # Biến đếm tổng số lần phát hiện buồn ngủ
        self.yawn_count = 0  # Biến đếm số lần ngáp
        self.yawning = False  # Biến trạng thái ngáp
        
        
        # Cập nhật thời gian mỗi giây
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 1000ms = 1 giây
        
        
         # Tạo bảng với hai cột có độ rộng bằng nhau
        self.drowsy_log_table = QtWidgets.QTableWidget(0, 2)
        self.drowsy_log_table.setHorizontalHeaderLabels(["Thời gian", "Trạng thái"])
        header = self.drowsy_log_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)  # Đặt độ rộng cột bằng nhau
        self.drowsy_log_table.setFixedHeight(200)
        
        
        
        self.populate_ui()  # Tạo giao diện người dùng
    # Hàm cập nhật bảng khi phát hiện ngủ gật
    # Hàm cập nhật bảng khi phát hiện ngủ gật
    def log_drowsy_event(self):
        # Lấy thời gian hiện tại
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        # Tạo hàng mới với thời gian và thông báo
        row_position = self.drowsy_log_table.rowCount()
        self.drowsy_log_table.insertRow(row_position)
        self.drowsy_log_table.setItem(row_position, 0, QTableWidgetItem(current_time))
        self.drowsy_log_table.setItem(row_position, 1, QTableWidgetItem("Tài xế ngủ gật"))
        
    def update_time(self):
        """Hàm cập nhật thời gian hiện tại lên nhãn thời gian"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(f"Time: {current_time}")

        
    def populate_ui(self):
        # Tạo layout chính cho ứng dụng
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.populate_ui_image()  # Tạo giao diện cho phần hiển thị hình ảnh
        self.populate_ui_ctrl()  # Tạo giao diện cho phần điều khiển
        self.main_layout.addLayout(self.image_layout)
        self.main_layout.addLayout(self.ctrl_layout)
        
        # Thêm nhãn hiển thị số lần buồn ngủ
        self.drowsy_count_label = QtWidgets.QLabel("Drowsy Count: 0")
        self.drowsy_count_label.setFixedHeight(40)  # Đặt chiều rộng cố định
        # Thiết lập CSS cho nhãn
        self.drowsy_alert_label = QtWidgets.QLabel("")
        self.drowsy_count_label.setStyleSheet("""
            QLabel {
                background-color: #FFDEAD;      /* Màu nền cam */
                color: black;                  /* Màu chữ đen */
                border: 2px solid black;       /* Đường viền đen */
                border-radius: 5px;            /* Góc bo tròn */
                padding: 5px;                  /* Khoảng cách giữa nội dung và viền */
                font-size: 14px;               /* Kích thước chữ */
                font-weight: bold;             /* Chữ đậm */
            }
        """)
        self.ctrl_layout.addRow(self.drowsy_count_label)
        
         # Thêm nhãn hiển thị số lần ngáp
        self.yawn_count_label = QtWidgets.QLabel("Yawn Count: 0")
        self.yawn_count_label.setFixedHeight(40)  # Đặt chiều rộng cố định
        self.yawn_alert_label = QtWidgets.QLabel("")
        self.yawn_count_label.setStyleSheet("""
            QLabel {
                background-color: #FFDEAD;      /* Màu nền cam */
                color: black;                  /* Màu chữ đen */
                border: 2px solid black;       /* Đường viền đen */
                border-radius: 5px;            /* Góc bo tròn */
                padding: 5px;                  /* Khoảng cách giữa nội dung và viền */
                font-size: 14px;               /* Kích thước chữ */
                font-weight: bold;             /* Chữ đậm */
            }
        """)
        self.ctrl_layout.addRow(self.yawn_count_label)
        
        # Nhãn hiển thị thời gian hiện tại
        self.time_label = QtWidgets.QLabel("Time: --:--:--")
        self.time_label.setFixedHeight(40)  # Đặt chiều rộng cố định
        self.time_label.setStyleSheet("""
            QLabel {
                background-color: white;      /* Màu nền cam */
                color: black;                  /* Màu chữ đen */
                border: 2px solid black;       /* Đường viền đen */
                border-radius: 5px;            /* Góc bo tròn */
                padding: 5px;                  /* Khoảng cách giữa nội dung và viền */
                font-size: 14px;               /* Kích thước chữ */
                font-weight: bold;             /* Chữ đậm */
            }
        """)
        self.ctrl_layout.addRow(self.time_label)
        
        # Định dạng bảng cho đẹp
        self.drowsy_log_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: orange;
                font-weight: bold;
            }
        """)
        # Thêm bảng vào layout điều khiển (hoặc vị trí khác tùy thuộc vào bố cục của bạn)
        self.ctrl_layout.addRow(self.drowsy_log_table)
    
    def update_drowsy_alert(self):
        # Lấy thời gian hiện tại và hiển thị thông báo
        current_time = datetime.now().strftime("%H:%M:%S")
        self.drowsy_alert_label.setText(f"Tài xế ngủ gật lúc {current_time}")
        self.drowsy_alert_label.update()  # Cập nhật giao diện ngay lập tức
    
    def update_drowsy_count(self):
        self.drowsy_count += 1  # Tăng số lần phát hiện buồn ngủ
        self.drowsy_count_label.setText(f"Drowsy Count: {self.drowsy_count}")  # Cập nhật giao diện
    
    def update_yawn_alert(self):
        # Lấy thời gian hiện tại và hiển thị thông báo
        current_time = datetime.now().strftime("%H:%M:%S")
        self.yawn_alert_label.setText(f"Tài xế buồn ngủ lúc {current_time}")
        self.yawn_alert_label.update()  # Cập nhật giao diện ngay lập tức
    
    def update_yawn_count(self):
        # Cập nhật số lần ngáp trên giao diện
        self.yawn_count += 1
        self.yawn_count_label.setText(f"Yawn Count: {self.yawn_count}")
       
    def populate_ui_image(self):
        # Tạo giao diện cho phần hình ảnh
        self.image_layout = QtWidgets.QVBoxLayout()
        self.image_layout.setAlignment(QtCore.Qt.AlignTop)
        self.preview_img = QtWidgets.QLabel("Preview Image")
        self.preview_img.resize(320, 240)
        self.image_layout.addWidget(self.preview_img)
        

    def populate_ui_ctrl(self):
        # Tạo giao diện cho phần điều khiển
        self.ctrl_layout = QtWidgets.QFormLayout() 
        self.ctrl_layout.setAlignment(QtCore.Qt.AlignTop)

        # Tạo danh sách các cổng ESP32 có sẵn
        self.esp32_port = QtWidgets.QComboBox()
        self.esp32_port.addItems([port for (port, desc, hwid) in serial.tools.list_ports.comports()])
        self.ctrl_layout.addRow("ESP32 Port", self.esp32_port)

        # Nút kết nối ESP32
        self.esp32_button = QtWidgets.QPushButton("Connect")
        self.esp32_button.clicked.connect(self.connect_esp32)
        self.ctrl_layout.addRow(self.esp32_button)

        # Nút dừng nhạc
        self.stop_music_button = QtWidgets.QPushButton("Stop Music")
        self.stop_music_button.setEnabled(False)
        self.stop_music_button.clicked.connect(self.stop_music)
        self.ctrl_layout.addRow(self.stop_music_button)

    def connect_esp32(self):
        # Kết nối đến ESP32 qua cổng được chọn
        port = self.esp32_port.currentText()
        try:
            self.rpc_master = rpc.rpc_usb_vcp_master(port)
            self.esp32_button.setText("Connected")
            self.esp32_button.setEnabled(False)
            self.start_capture_timer()  # Bắt đầu chụp ảnh sau khi kết nối
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def start_capture_timer(self):
        # Khởi tạo bộ đếm thời gian để chụp ảnh mỗi giây
        self.capture_timer = QtCore.QTimer(self)
        self.capture_timer.timeout.connect(self.capture_photo)
        self.capture_timer.start(1000)

    def capture_photo(self):
        if self.rpc_master is None:
            return

        try:
            result = self.rpc_master.call("jpeg_image_snapshot", recv_timeout=1000)
            if result is not None:
                jpg_sz = int.from_bytes(result.tobytes(), "little")
                buf = bytearray(b'\x00' * jpg_sz)
                result = self.rpc_master.call("jpeg_image_read", recv_timeout=1000)
                self.rpc_master.get_bytes(buf, jpg_sz)
                img = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
                
                # Phát hiện trạng thái buồn ngủ/ngáp
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                subjects = detector(gray, 0)
                for subject in subjects:
                    shape = predict(gray, subject)
                    shape = face_utils.shape_to_np(shape)
                    
                    # Kiểm tra ngáp
                    if self.detect_yawn(shape):
                        print("Yawn detected")

                    
                    # Kiểm tra buồn ngủ
                    drowsy = self.detect_drowsiness(img)
                    if drowsy:
                        self.drowsy_counter += 1
                        if self.drowsy_counter >= 3 and not self.music_playing:
                            mixer.music.play(-1)
                            self.music_playing = True
                            self.stop_music_button.setEnabled(True)
                            self.update_drowsy_alert()
                            self.update_drowsy_count()
                            self.log_drowsy_event()  # Ghi lại sự kiện vào bảng
                            send_msg("buzzer","on")
                            self.buzzer_flags = 1
                            self.drowsy_counter = 0
                    else:
                        self.drowsy_counter = 0

                # Cập nhật hình ảnh hiển thị
                self.update_image(img.copy())
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "Failed to capture photo.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))


    def detect_drowsiness(self, img):
        # Chuyển đổi ảnh sang màu xám và phát hiện khuôn mặt
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        subjects = detector(gray, 0)
        for subject in subjects:
            shape = predict(gray, subject)  # Xác định các điểm trên khuôn mặt
            shape = face_utils.shape_to_np(shape)
            left_eye = shape[42:48]
            right_eye = shape[36:42]
            left_ear = self.eye_aspect_ratio(left_eye)
            right_ear = self.eye_aspect_ratio(right_eye)
            ear = (left_ear + right_ear) / 2.0
            if ear < thresh:
                return True
        return False

    def detect_yawn(self, shape):
        top_lip = shape[50:53]
        top_lip = np.concatenate((top_lip, shape[61:64]))
        low_lip = shape[56:59]
        low_lip = np.concatenate((low_lip, shape[65:68]))
        
        top_mean = np.mean(top_lip, axis=0)
        low_mean = np.mean(low_lip, axis=0)
        
        lip_distance = distance.euclidean(top_mean, low_mean)
        yawn_thresh = 15  # Ngưỡng để phát hiện ngáp, có thể điều chỉnh

        if lip_distance > yawn_thresh:
            # Nếu miệng đang mở và trạng thái hiện tại là không ngáp, đánh dấu là bắt đầu ngáp
            if not self.yawning:
                self.yawning = True
        else:
            # Nếu miệng đóng lại sau khi mở, đếm 1 lần ngáp và đặt trạng thái ngáp lại là False
            if self.yawning:
                self.yawning = False
                self.update_yawn_count()  # Cập nhật số lần ngáp
                return True  # Phát hiện một lần ngáp hoàn chỉnh

        return False  # Không phát hiện ngáp hoặc đang trong quá trình ngáp`


    def eye_aspect_ratio(self, eye):
        # Tính tỷ lệ mắt để xác định trạng thái mở hoặc nhắm mắt
        A = distance.euclidean(eye[1], eye[5])
        B = distance.euclidean(eye[2], eye[4])
        C = distance.euclidean(eye[0], eye[3])
        ear = (A + B) / (2.0 * C)
        return ear

    def update_image(self, img):
        # Cập nhật hình ảnh trên giao diện
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = img.shape
        img = QtGui.QImage(img.data, w, h, QtGui.QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self.preview_img.setPixmap(pixmap.scaled(320, 240, QtCore.Qt.KeepAspectRatio))

    def stop_music(self):
        # Hàm dừng phát nhạc
        if self.music_playing:
            mixer.music.stop()
            self.music_playing = False
            self.stop_music_button.setEnabled(False)

    def closeEvent(self, event):
        # Hàm xử lý sự kiện đóng cửa sổ
        if self.rpc_master is not None:
            self.rpc_master.close()
        if self.music_playing:
            mixer.music.stop()

# Hàm khởi động ứng dụng
if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = EspCamWidget()
    widget.resize(640, 480)
    widget.show()
    sys.exit(app.exec())
