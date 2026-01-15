import cv2
import numpy as np
w,h=640,480
fourcc=cv2.VideoWriter_fourcc(*'mp4v')
out=cv2.VideoWriter('sample.mp4', fourcc, 15.0, (w,h))
for i in range(60):
    frame = np.zeros((h,w,3), dtype='uint8')
    cv2.putText(frame, f'frame {i}', (50,100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,255,0), 3)
    out.write(frame)
out.release()
print('WROTE sample.mp4')
