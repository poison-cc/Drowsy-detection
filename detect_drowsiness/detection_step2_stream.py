from scipy.spatial import distance as dist
from imutils import face_utils
import imutils
import dlib
import cv2
import numpy as np
import urllib.request
import time

url = 'http://192.168.215.171:81/stream'

def eye_aspect_ratio(eye):
	A = dist.euclidean(eye[1], eye[5])
	B = dist.euclidean(eye[2], eye[4])
	C = dist.euclidean(eye[0], eye[3])
	ear = (A + B) / (2.0 * C)
	return ear

def calculate_ear(shape):   
	(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["left_eye"]
	(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["right_eye"]
	leftEye = shape[lStart: lEnd]
	rightEye = shape[rStart: rEnd]
	leftEAR = eye_aspect_ratio(leftEye)
	rightEAR = eye_aspect_ratio(rightEye)
	ear = (leftEAR + rightEAR)/2
	return (ear, leftEye, rightEye)
 
def lip_distance(shape):
    top_lip = shape[50:53]
    top_lip = np.concatenate((top_lip, shape[61:64]))

    low_lip = shape[56:59]
    low_lip = np.concatenate((low_lip, shape[65:68]))

    top_mean = np.mean(top_lip, axis=0)
    low_mean = np.mean(low_lip, axis=0)

    distance = abs(top_mean[1] - low_mean[1])
    return distance

 
EYE_THRESH = 0.25		# Threshold for blink 
EYE_CONSEC_FRAMES = 50	# Consecutive considered it true

sleep_flag = -1
yawn_flag = 0
eye_flags = 0
SLEEP_COUNTER = 0
YAWN_THRESH = 22
YAWN_COUNTER = 0

detect = dlib.get_frontal_face_detector()
predict = dlib.shape_predictor('models/shape_predictor_68_face_landmarks.dat')# Dat file is the crux of the code

(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
(mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

cap=cv2.VideoCapture(url)
#cap.set(cv2.CAP_PROP_FPS,45)

#### fps ####
prev_frame_time = 0
new_frame_time = 0

while True:
	ret, frame=cap.read()
	frame = imutils.resize(frame, width=450)
	# img = urllib.request.urlopen(url)
	# img_np = np.array(bytearray(img.read()), dtype=np.uint8)
	# frame = cv2.imdecode(img_np, -1)
	gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	subjects = detect(gray, 0) # dlib's built-in face detector
	new_frame_time = time.time() 
	fps = int(1/(new_frame_time-prev_frame_time)) 
	prev_frame_time = new_frame_time

	for subject in subjects:
		shape = predict(gray, subject)
		shape = face_utils.shape_to_np(shape) # Converting to NumPy Array
  
		eye = calculate_ear(shape) 
		ear = eye[0]			# First return of calculate_ear() function: EAR
		leftEye = eye[1]		# Second return of calculate_ear() function: leftEye
		rightEye = eye[2]		# Third return of calculate_ear() function: leftEye
		mouth = shape[mStart: mEnd]
		distance = lip_distance(shape)
		lip = shape[48:60]
		cv2.drawContours(frame, [lip], -1, (0, 255, 0), 1)
  
		leftEyeHull = cv2.convexHull(leftEye)
		rightEyeHull = cv2.convexHull(rightEye)
		mouthHull = cv2.convexHull(mouth)
  
		cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
		cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)
		cv2.drawContours(frame, [mouthHull], -1, (0, 255, 0), 1)

		if distance > 30:
			count_mouth += 1
			if count_mouth >= 10:
				cv2.drawContours(frame, [mouthHull], -1, (0, 0, 255), 1)
				if yawn_flag < 0:
					yawn_flag = 1
					YAWN_COUNTER += 1
				else:
					yawn_flag = 1
			else:
					yawn_flag = -1
		else:
			count_mouth = 0
			yawn_flag = -1

		if ear < EYE_THRESH:
			eye_flags += 1
			if eye_flags >= EYE_CONSEC_FRAMES:
				cv2.drawContours(frame, [leftEyeHull], -1, (0, 0, 255), 1)
				cv2.drawContours(frame, [rightEyeHull], -1, (0, 0, 255), 1)
				if sleep_flag < 0:
					sleep_flag = 1
					SLEEP_COUNTER += 1
		else:
			eye_flags = 0
			sleep_flag = -1
		cv2.putText(frame, "FPS: {:.2f}".format(fps), (250, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
		cv2.putText(frame, "EAR: {:.2f}".format(ear), (250, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
		cv2.putText(frame, "YAWN: {:.2f}".format(distance), (250, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
		# cv2.putText(frame, "BLINK: {:.2f}".format(BLINK_COUNTER), (300, 90),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
		cv2.putText(frame, "SLEEP: {:.2f}".format(SLEEP_COUNTER), (250, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2) 
		cv2.putText(frame, "YAWN: {:.2f}".format(YAWN_COUNTER), (250, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2) 

	cv2.imshow("Frame", frame)
	key = cv2.waitKey(10) & 0xFF
	if key == ord("q"):
		break
cv2.destroyAllWindows()
cap.release()
