from gmplot import GoogleMapPlotter

# Nhập tọa độ vị trí trung tâm (ví dụ: Sài Gòn)
latitude = 10.8231
longitude = 106.6297
zoom = 13

# Tạo bản đồ với tọa độ trung tâm và mức thu phóng
gmap = GoogleMapPlotter(latitude, longitude, zoom)

# Đánh dấu một số điểm trên bản đồ
gmap.marker(latitude, longitude, title="Sài Gòn")  # Marker tại Sài Gòn
gmap.marker(10.762622, 106.660172, title="ĐH Bách Khoa")  # Marker tại ĐH Bách Khoa

# Lưu bản đồ vào tệp HTML
map_file = "map.html"
gmap.draw(map_file)

# Tự động mở tệp HTML trong trình duyệt
import webbrowser
webbrowser.open(map_file)
