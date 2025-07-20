import cv2
import time
import threading
from queue import Queue, Empty
import tempfile
import os
from config import Config

class CameraManager:
    def __init__(self):
        self.config = Config()
        self.camera = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=30)
        self.is_recording = False
        self.capture_thread = None
        
    def initialize_camera(self):
        """Initialize camera for macOS"""
        try:
            print("📷 Initializing camera for macOS...")
            
            # Release any existing camera
            if self.camera:
                self.camera.release()
            
            # Try to open camera
            self.camera = cv2.VideoCapture(0)
            
            if not self.camera.isOpened():
                print("❌ Camera 0 failed, trying other indices...")
                for i in range(1, 5):
                    self.camera = cv2.VideoCapture(i)
                    if self.camera.isOpened():
                        print(f"✅ Found camera at index {i}")
                        break
                else:
                    raise Exception("No camera found")
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Lower resolution for stability
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 10)
            
            # Test immediate capture
            ret, test_frame = self.camera.read()
            if not ret:
                raise Exception("Camera opened but cannot capture frames")
            
            print(f"✅ Camera initialized successfully - Test frame: {test_frame.shape}")
            return True
            
        except Exception as e:
            print(f"❌ Camera initialization failed: {e}")
            return False
    
    def start_camera(self):
        """Start camera capture"""
        print("🎥 Starting camera system...")
        
        if not self.initialize_camera():
            return False
        
        self.is_running = True
        
        # Start frame capture thread
        self.capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        self.capture_thread.start()
        
        # Wait a moment and check if frames are being captured
        time.sleep(2)
        
        if self.frame_queue.qsize() > 0:
            print(f"✅ Camera started successfully - {self.frame_queue.qsize()} frames captured")
            return True
        else:
            print("⚠️  Camera started but no frames captured yet")
            return True  # Still return True to continue
    
    def _capture_frames(self):
        """Capture frames continuously - simplified version"""
        print("🎥 Frame capture thread started")
        frame_count = 0
        
        while self.is_running:
            try:
                if not self.camera or not self.camera.isOpened():
                    print("❌ Camera not available in capture thread")
                    time.sleep(1)
                    continue
                
                ret, frame = self.camera.read()
                if not ret:
                    print("⚠️  Failed to read frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Clear queue if it's getting full
                while self.frame_queue.qsize() >= 25:
                    try:
                        self.frame_queue.get_nowait()
                    except Empty:
                        break
                
                # Add new frame
                self.frame_queue.put({
                    'frame': frame.copy(),  # Make a copy to avoid issues
                    'timestamp': time.time()
                })
                
                # Debug output every 50 frames
                if frame_count % 50 == 0:
                    print(f"📷 Captured {frame_count} frames, queue: {self.frame_queue.qsize()}")
                
                time.sleep(0.1)  # 10 FPS
                
            except Exception as e:
                print(f"❌ Frame capture error: {e}")
                time.sleep(1)
        
        print(f"🛑 Frame capture stopped - Total frames: {frame_count}")
    
    def record_video_segment(self, duration=None):
        """Record video segment - simplified approach"""
        if duration is None:
            duration = self.config.VIDEO_RECORDING_DURATION
        
        print(f"🎬 Recording {duration}s video...")
        print(f"📊 Current queue size: {self.frame_queue.qsize()}")
        
        if self.is_recording:
            print("⚠️  Already recording")
            return None
        
        # Check if we have frames available
        if self.frame_queue.qsize() == 0:
            print("❌ No frames available - trying direct capture")
            # Try direct capture as fallback
            return self._direct_record_video(duration)
        
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp4',
                delete=False,
                dir=self.config.TEMP_VIDEO_DIR,
                prefix=f'body_scan_{int(time.time())}_'
            )
            video_path = temp_file.name
            temp_file.close()
            
            self.is_recording = True
            
            # Get a frame to determine video properties
            frame_data = self.get_latest_frame()
            if not frame_data:
                print("❌ No frame data available")
                self.is_recording = False
                return None
            
            frame = frame_data['frame']
            height, width = frame.shape[:2]
            
            # Setup video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 10
            out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                print("❌ Failed to create video writer")
                self.is_recording = False
                return None
            
            # Record frames
            start_time = time.time()
            frames_written = 0
            
            while time.time() - start_time < duration:
                frame_data = self.get_latest_frame()
                if frame_data:
                    out.write(frame_data['frame'])
                    frames_written += 1
                
                time.sleep(1/fps)
            
            out.release()
            self.is_recording = False
            
            if frames_written > 0:
                file_size = os.path.getsize(video_path)
                print(f"✅ Video recorded: {frames_written} frames, {file_size} bytes")
                return video_path
            else:
                print("❌ No frames written")
                os.remove(video_path)
                return None
                
        except Exception as e:
            print(f"❌ Recording error: {e}")
            self.is_recording = False
            return None
    
    def _direct_record_video(self, duration):
        """Direct recording fallback method"""
        print("🎬 Using direct recording method...")
        
        try:
            if not self.camera or not self.camera.isOpened():
                print("❌ Camera not available for direct recording")
                return None
            
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.mp4',
                delete=False,
                dir=self.config.TEMP_VIDEO_DIR,
                prefix=f'direct_scan_{int(time.time())}_'
            )
            video_path = temp_file.name
            temp_file.close()
            
            # Get first frame for properties
            ret, first_frame = self.camera.read()
            if not ret:
                print("❌ Cannot capture frame for direct recording")
                return None
            
            height, width = first_frame.shape[:2]
            
            # Setup video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 10
            out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                print("❌ Direct recording: Failed to create video writer")
                return None
            
            # Write first frame
            out.write(first_frame)
            frames_written = 1
            
            # Record remaining frames
            start_time = time.time()
            
            while time.time() - start_time < duration:
                ret, frame = self.camera.read()
                if ret:
                    out.write(frame)
                    frames_written += 1
                
                time.sleep(1/fps)
            
            out.release()
            
            if frames_written > 0:
                file_size = os.path.getsize(video_path)
                print(f"✅ Direct recording successful: {frames_written} frames, {file_size} bytes")
                return video_path
            else:
                os.remove(video_path)
                return None
                
        except Exception as e:
            print(f"❌ Direct recording error: {e}")
            return None
    
    def get_latest_frame(self):
        """Get latest frame from queue"""
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None
    
    def stop_camera(self):
        """Stop camera"""
        print("🛑 Stopping camera...")
        self.is_running = False
        self.is_recording = False
        
        # Wait for capture thread to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2)
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        print("✅ Camera stopped")
    
    def get_camera_status(self):
        """Get camera status"""
        return {
            'is_running': self.is_running,
            'is_recording': self.is_recording,
            'queue_size': self.frame_queue.qsize(),
            'camera_type': 'opencv',
            'camera_available': self.camera is not None and self.camera.isOpened() if self.camera else False
        }