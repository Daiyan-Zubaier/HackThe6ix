import cv2
import time
import requests
import numpy as np
import google.generativeai as genai
from io import BytesIO
import base64
from PIL import Image
import threading
import os
from datetime import datetime
from config import Config

class GeminiBmpDetector:
    def __init__(self):
        self.config = Config()
        self.setup_gemini()
        self.setup_directories()
        self.running = False
        self.detection_thread = None
        self.target_locked = False
        
    def setup_gemini(self):
        """Initialize Gemini API"""
        try:
            genai.configure(api_key=self.config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            print("✅ Gemini API initialized successfully")
        except Exception as e:
            print(f"❌ Gemini API setup failed: {e}")
            raise
    
    def setup_directories(self):
        """Create organized directory structure"""
        self.gemini_frames_dir = "gemini_frames"
        self.temp_files_dir = "temp_files"
        
        # Create directories if they don't exist
        os.makedirs(self.gemini_frames_dir, exist_ok=True)
        os.makedirs(self.temp_files_dir, exist_ok=True)
        
        print(f"📁 Gemini frames directory: {self.gemini_frames_dir}/")
        print(f"📁 Temp files directory: {self.temp_files_dir}/")
    
    def cleanup_old_files(self, keep_last=10):
        """Clean up old detection frames, keep only recent ones"""
        try:
            files = []
            for f in os.listdir(self.gemini_frames_dir):
                if f.startswith('detection_frame_') and f.endswith('.bmp'):
                    filepath = os.path.join(self.gemini_frames_dir, f)
                    files.append((filepath, os.path.getctime(filepath)))
            
            # Sort by creation time, newest first
            files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old files, keep only recent ones
            if len(files) > keep_last:
                for filepath, _ in files[keep_last:]:
                    try:
                        os.remove(filepath)
                        print(f"🗑️  Cleaned up old file: {os.path.basename(filepath)}")
                    except Exception as e:
                        print(f"⚠️  Could not remove {filepath}: {e}")
                        
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    def capture_and_save_bmp(self, frame_number):
        """Capture frame from camera and save as organized BMP"""
        try:
            # Use same camera as TwelveLabs system
            cap = cv2.VideoCapture(self.config.BODY_CAMERA_ID)
            
            if not cap.isOpened():
                print(f"❌ Cannot open camera {self.config.BODY_CAMERA_ID}")
                return None
            
            # Set camera properties for consistency with TwelveLabs
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                # Create organized filename with timestamp
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"detection_frame_{frame_number:03d}_{timestamp}.bmp"
                filepath = os.path.join(self.gemini_frames_dir, filename)
                
                # Save as BMP file in organized folder (NOT root)
                cv2.imwrite(filepath, frame)
                print(f"💾 BMP saved: {filename}")
                return filepath
            else:
                print("❌ Failed to capture frame from camera")
                return None
                
        except Exception as e:
            print(f"❌ Error capturing and saving BMP: {e}")
            return None
    
    def save_target_frame(self, frame_number):
        """Save the target acquisition frame with special naming"""
        try:
            cap = cv2.VideoCapture(self.config.BODY_CAMERA_ID)
            if not cap.isOpened():
                return None
            
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"TARGET_LOCKED_{frame_number:03d}_{timestamp}.bmp"
                filepath = os.path.join(self.gemini_frames_dir, filename)
                
                cv2.imwrite(filepath, frame)
                print(f"🎯 Target frame saved: {filename}")
                return filepath
            
        except Exception as e:
            print(f"❌ Error saving target frame: {e}")
        
        return None
    
    def load_bmp_file(self, bmp_path):
        """Load BMP file"""
        try:
            frame = cv2.imread(bmp_path)
            if frame is not None:
                return frame
            else:
                print(f"❌ Could not load BMP: {bmp_path}")
                return None
        except Exception as e:
            print(f"❌ Error loading BMP {bmp_path}: {e}")
            return None
    
    def bmp_to_base64(self, frame):
        """Convert BMP frame to base64 for Gemini"""
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            pil_image = Image.fromarray(rgb_frame)
            
            # Convert to base64 JPEG
            buffer = BytesIO()
            pil_image.save(buffer, format='JPEG', quality=85)
            img_bytes = buffer.getvalue()
            
            return base64.b64encode(img_bytes).decode('utf-8')
            
        except Exception as e:
            print(f"❌ Error converting BMP frame: {e}")
            return None
    
    def analyze_bmp_with_gemini(self, bmp_path):
        """Analyze BMP file with Gemini for survivor detection"""
        try:
            # Load BMP file
            frame = self.load_bmp_file(bmp_path)
            if frame is None:
                return None
            
            # Convert frame for Gemini
            base64_image = self.bmp_to_base64(frame)
            if not base64_image:
                return None
            
            # Create prompt for survivor detection and centering
            prompt = """
            Analyze this camera feed image for SURVIVOR DETECTION and POSITIONING:
            
            Your task:
            1. Look for any PERSON, HUMAN, or SURVIVOR in the image
            2. If a person is detected, determine if they are CENTERED in the frame
            3. A person is considered CENTERED if they are in the middle 40% of the image
            
            Respond with ONLY this JSON format:
            {
                "person_detected": true/false,
                "person_centered": true/false,
                "confidence": 0.0-1.0,
                "position_description": "brief description of where person is located",
                "target_ready": true/false
            }
            
            Set "target_ready" to true ONLY if:
            - A person is clearly detected AND
            - The person is reasonably centered in the frame AND  
            - You have high confidence in the detection
            
            Be precise and conservative - false positives could cause mission failure.
            """
            
            # Send to Gemini
            response = self.model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": base64_image}
            ])
            
            return response.text.strip()
            
        except Exception as e:
            print(f"❌ Gemini analysis error: {e}")
            return None
    
    def parse_gemini_response(self, response_text):
        """Parse Gemini JSON response"""
        try:
            import json
            
            # Clean response (remove markdown if present)
            clean_response = response_text.replace('```json', '').replace('```', '').strip()
            
            # Parse JSON
            result = json.loads(clean_response)
            
            return {
                'person_detected': result.get('person_detected', False),
                'person_centered': result.get('person_centered', False),
                'confidence': result.get('confidence', 0.0),
                'position_description': result.get('position_description', ''),
                'target_ready': result.get('target_ready', False)
            }
            
        except Exception as e:
            print(f"❌ Error parsing Gemini response: {e}")
            print(f"Raw response: {response_text}")
            return None
    
    def send_movement_command(self):
        """Send movement command to Raspberry Pi"""
        try:
            print(f"🤖 Sending movement command to Pi: {self.config.PI_CONTROL_URL}")
            
            payload = {'injury': True}
            
            response = requests.post(
                self.config.PI_CONTROL_URL,
                json=payload,
                timeout=2,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            print(f"✅ Pi responded: {response.text}")
            print(f"🛑 Robot should now STOP spinning")
            print(f"➡️  Robot should now MOVE forward toward target")
            return True
            
        except requests.exceptions.Timeout:
            print(f"⏰ Pi connection timeout")
            return False
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to Pi at {self.config.PI_CONTROL_URL}")
            return False
            
        except Exception as e:
            print(f"❌ Failed to send movement command: {e}")
            return False
    
    def detection_loop(self):
        """Main detection loop using organized BMP files"""
        print("🎯 Starting Gemini BMP-based survivor detection...")
        print(f"📸 Using main camera (ID: {self.config.BODY_CAMERA_ID})")
        print(f"⚡ Frame rate: {self.config.MOVEMENT_FRAME_RATE}s intervals")
        print(f"📁 Saving frames to: {self.gemini_frames_dir}/")
        
        frame_count = 0
        
        # Clean up old files at start
        self.cleanup_old_files(keep_last=5)
        
        while self.running and not self.target_locked:
            try:
                frame_count += 1
                
                print(f"📸 Capturing frame #{frame_count}")
                
                # Capture and save as organized BMP
                bmp_path = self.capture_and_save_bmp(frame_count)
                
                if bmp_path:
                    # Analyze BMP with Gemini
                    analysis = self.analyze_bmp_with_gemini(bmp_path)
                    
                    if analysis:
                        result = self.parse_gemini_response(analysis)
                        
                        if result:
                            print(f"🔍 Detection Result:")
                            print(f"   📄 BMP: {os.path.basename(bmp_path)}")
                            print(f"   👤 Person detected: {result['person_detected']}")
                            print(f"   🎯 Person centered: {result['person_centered']}")
                            print(f"   📈 Confidence: {result['confidence']:.2f}")
                            print(f"   📍 Position: {result['position_description']}")
                            
                            # Check if target is ready
                            if result['target_ready'] and result['confidence'] > 0.7:
                                print(f"\n🎯 TARGET ACQUIRED AND CENTERED!")
                                print(f"🚨 DROPPING KEYWORD: {self.config.TARGET_KEYWORD}")
                                
                                # Save special target frame
                                target_frame = self.save_target_frame(frame_count)
                                if target_frame:
                                    print(f"💾 Target frame: {os.path.basename(target_frame)}")
                                
                                self.target_locked = True
                                self.trigger_movement()
                                break
                            
                            elif result['person_detected']:
                                print(f"👁️  Person detected but not centered - continuing scan...")
                        
                        else:
                            print("⚪ No clear detection - continuing scan...")
                
                else:
                    print("❌ Failed to capture BMP frame")
                
                # Clean up periodically
                if frame_count % 10 == 0:
                    self.cleanup_old_files(keep_last=5)
                
                # Wait before next frame
                time.sleep(self.config.MOVEMENT_FRAME_RATE)
                
            except Exception as e:
                print(f"❌ Detection loop error: {e}")
                time.sleep(1)
        
        if self.target_locked:
            print("✅ Gemini BMP detection phase completed successfully")
            print(f"📁 Detection frames saved in: {self.gemini_frames_dir}/")
            print("🎥 Camera ready for TwelveLabs analysis")
        else:
            print("🛑 Detection stopped without target lock")
    
    def trigger_movement(self):
        """Drop the keyword AND send HTTP request to Pi"""
        print(f"\n{'='*50}")
        print(f"🚨 MOVEMENT TRIGGER ACTIVATED")
        print(f"{'='*50}")
        print(f"📢 KEYWORD: {self.config.TARGET_KEYWORD}")
        
        # Send HTTP request to Raspberry Pi
        print(f"📡 Sending HTTP request to Raspberry Pi...")
        pi_success = self.send_movement_command()
        
        if pi_success:
            print(f"✅ SUCCESS: Pi received movement command!")
            print(f"🤖 Robot control sequence should now begin:")
            print(f"   1️⃣  STOP spinning/scanning")
            print(f"   2️⃣  MOVE forward toward detected person")
            print(f"   3️⃣  STOP when close enough")
        else:
            print(f"⚠️  WARNING: Pi command may have failed")
            print(f"🔄 Robot may continue spinning - check Pi connection")
        
        print(f"🎯 Gemini BMP detection phase COMPLETE")
        print(f"📸 Same camera + BMP format ready for TwelveLabs")
        print(f"{'='*50}")
        
    def start_detection(self):
        """Start the organized BMP-based detection system"""
        if self.running:
            print("⚠️  Detection already running!")
            return
        
        print("🚀 Starting Organized Gemini BMP Detection System")
        print("=" * 60)
        
        # Test camera connection first
        print(f"📸 Testing main camera (ID: {self.config.BODY_CAMERA_ID})...")
        
        # Save test frame in temp directory (NOT root)
        test_path = os.path.join(self.temp_files_dir, "camera_test.bmp")
        cap = cv2.VideoCapture(self.config.BODY_CAMERA_ID)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                cv2.imwrite(test_path, frame)
                print(f"✅ Camera working - Test saved: {test_path}")
            else:
                print("❌ Camera capture failed")
                return False
        else:
            print(f"❌ Cannot access camera {self.config.BODY_CAMERA_ID}!")
            return False
        
        # Start detection thread
        self.running = True
        self.target_locked = False
        self.detection_thread = threading.Thread(target=self.detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        print("✅ Organized BMP detection thread started")
        return True
    
    def stop_detection(self):
        """Stop the detection system"""
        print("🛑 Stopping Gemini BMP detection...")
        self.running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5)
        
        print("✅ Gemini BMP detection stopped")
        print("📸 Camera released for TwelveLabs system")
    
    def get_status(self):
        """Get current detection status"""
        return {
            'running': self.running,
            'target_locked': self.target_locked,
            'camera_id': self.config.BODY_CAMERA_ID,
            'frames_directory': self.gemini_frames_dir
        }

# Test function
def test_organized_detection():
    """Test the organized BMP detection system"""
    try:
        detector = GeminiBmpDetector()
        
        print("🧪 Testing Organized Gemini BMP Detection")
        print("=" * 50)
        
        # Start detection
        if detector.start_detection():
            print("✅ Organized detection started successfully")
            print("🔄 Capturing organized BMPs and scanning...")
            print("   (Move in front of camera and center yourself)")
            print("   (Press Ctrl+C to stop)")
            
            # Keep running until target found or interrupted
            try:
                while detector.running and not detector.target_locked:
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n🛑 Test interrupted by user")
            
            finally:
                detector.stop_detection()
                
                # Show final organization
                print(f"\n📁 Final file organization:")
                if os.path.exists(detector.gemini_frames_dir):
                    files = os.listdir(detector.gemini_frames_dir)
                    print(f"   📸 Detection frames: {len(files)} files in {detector.gemini_frames_dir}/")
                    for f in sorted(files)[-3:]:  # Show last 3 files
                        print(f"      - {f}")
        
        else:
            print("❌ Failed to start organized detection")
    
    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    test_organized_detection()