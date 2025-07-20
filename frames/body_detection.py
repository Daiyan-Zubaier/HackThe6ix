import os
import time
import json
import threading
from datetime import datetime
from twelvelabs import TwelveLabs
from config import Config

class BodyDetectionSystem:
    def __init__(self, camera_manager):
        self.config = Config()
        self.camera_manager = camera_manager
        
        # Initialize TwelveLabs client
        self.client = TwelveLabs(api_key=self.config.TWELVELABS_API_KEY)
        
        # Detection state
        self.is_detecting = False
        self.detection_thread = None
        self.index = None
        self.total_scans = 0
        self.survivors_found = 0
        self.last_scan_time = 0
        
        # Rescue detection prompts for Pegasus
        self.rescue_analysis_prompt = """
        Analyze this video footage from a rescue rover searching for survivors. 
        Look carefully for any people who might need rescue assistance, including:
        
        - People lying on the ground (injured, unconscious, or trapped)
        - People showing signs of distress or calling for help
        - People with visible injuries, wounds, or bleeding
        - People trapped under debris or in confined spaces
        - People who appear motionless or in need of medical attention
        - People displaying body language indicating pain or distress
        
        Respond in this JSON format:
        {
            "survivors_detected": true/false,
            "survivor_count": number,
            "detailed_description": "detailed description of what you see",
            "survivor_details": [
                {
                    "position": "description of where person is located",
                    "condition": "description of apparent condition/injuries",
                    "urgency_level": "low/medium/high/critical",
                    "confidence": 0.0-1.0
                }
            ],
            "rescue_priority": "none/low/medium/high/critical",
            "recommended_action": "specific recommended rescue action"
        }
        
        If no people are visible or detected, set survivors_detected to false and survivor_count to 0.
        Be thorough but accurate - only report people you can clearly see in the video.
        """
        
        # Initialize detection index
        self._initialize_detection_index()
    
    def _initialize_detection_index(self):
        """Initialize TwelveLabs index for video analysis"""
        try:
            print("📋 Creating TwelveLabs index...")
            index_name = f"{self.config.ROVER_NAME}_pegasus_rescue_{int(time.time())}"
            
            # Create index with Pegasus model - FIXED OPTIONS
            self.index = self.client.index.create(
                name=index_name,
                models=[{
                    "name": "pegasus1.2",  # Using Pegasus 1.2 model
                    "options": ["visual"]  # Only visual option for Pegasus
                }]
            )
            
            print(f"✅ Detection index created: {self.index.id}")
            print(f"   Index name: {index_name}")
            
        except Exception as e:
            print(f"❌ Failed to create detection index: {e}")
            raise
    
    def start_detection_system(self):
        """Start the body detection system"""
        print("🔍 Starting body detection system...")
        print(f"   Scan interval: {self.config.DETECTION_INTERVAL} seconds")
        print(f"   Video duration: {self.config.VIDEO_RECORDING_DURATION} seconds")
        print(f"   Using: Pegasus 1.2 model")
        
        self.is_detecting = True
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        return self.detection_thread
    
    def _detection_loop(self):
        """Main detection loop"""
        scan_number = 0
        
        while self.is_detecting:
            try:
                scan_number += 1
                print(f"\n🔍 Starting detection scan #{scan_number}")
                
                # Add small delay for camera stability
                time.sleep(1)
                
                # Perform detection scan
                self.perform_detection_scan()
                
                # Wait for next scan
                time.sleep(self.config.DETECTION_INTERVAL)
                
            except Exception as e:
                print(f"❌ Error in detection loop: {e}")
                time.sleep(5)
    
    def perform_detection_scan(self):
        """Perform a single detection scan using Pegasus"""
        try:
            self.total_scans += 1
            self.last_scan_time = time.time()
            
            # Record video segment
            print("📹 Recording video for analysis...")
            video_path = self.camera_manager.record_video_segment()
            
            if not video_path:
                print("❌ Failed to record video segment")
                return
            
            # Upload and analyze with Pegasus
            self._analyze_video_with_pegasus(video_path)
            
        except Exception as e:
            print(f"❌ Error in detection scan: {e}")
    
    def _analyze_video_with_pegasus(self, video_path):
        """Analyze video using Pegasus model"""
        try:
            print("📤 Uploading video to TwelveLabs...")
            
            # Upload video
            task = self.client.task.create(
                index_id=self.index.id,
                file=video_path
            )
            
            print(f"   Task ID: {task.id}")
            print("⏳ Processing video...")
            
            # Wait for processing to complete
            def print_status(task_obj):  # Accept the task object parameter
                status = task_obj.status
                print(f"   Status: {status}")
                return status

            task.wait_for_done(sleep_interval=2, callback=print_status)
            
            if task.status != "ready":
                print(f"❌ Video processing failed: {task.status}")
                return
            
            print("✅ Video processed successfully")
            
            # Analyze with Pegasus
            print("🤖 Analyzing video with Pegasus AI...")
            
            response = self.client.generate.text(
                video_id=task.video_id,
                prompt=self.rescue_analysis_prompt
            )
            
            # Parse the response
            self._process_pegasus_response(response.data, task.video_id)
            
        except Exception as e:
            print(f"❌ Error analyzing video: {e}")
        
        finally:
            # Clean up temporary video file
            try:
                os.remove(video_path)
                print("🗑️  Temporary video file cleaned up")
            except:
                pass
    
    def _process_pegasus_response(self, response_text, video_id):
        """Process Pegasus analysis response"""
        try:
            print("📊 Processing AI analysis...")
            print(f"🤖 Pegasus Analysis:\n{response_text}")
            
            # Try to parse JSON response
            try:
                # Extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # If no JSON found, create a basic analysis
                    analysis = {
                        "survivors_detected": "person" in response_text.lower() or "human" in response_text.lower(),
                        "survivor_count": response_text.lower().count("person"),
                        "detailed_description": response_text,
                        "rescue_priority": "medium" if "person" in response_text.lower() else "none"
                    }
            except json.JSONDecodeError:
                # Fallback analysis based on keywords
                text_lower = response_text.lower()
                person_detected = any(keyword in text_lower for keyword in 
                    ["person", "human", "people", "individual", "body", "someone"])
                
                analysis = {
                    "survivors_detected": person_detected,
                    "survivor_count": 1 if person_detected else 0,
                    "detailed_description": response_text,
                    "rescue_priority": "medium" if person_detected else "none"
                }
            
            # Process detection results
            if analysis.get("survivors_detected", False):
                survivor_count = analysis.get("survivor_count", 1)
                self.survivors_found += survivor_count
                
                print(f"\n🚨 SURVIVORS DETECTED: {survivor_count} found!")
                print(f"📝 Description: {analysis.get('detailed_description', 'No description')}")
                
                if 'survivor_details' in analysis:
                    for i, survivor in enumerate(analysis['survivor_details'], 1):
                        print(f"   Survivor {i}:")
                        print(f"     Position: {survivor.get('position', 'Unknown')}")
                        print(f"     Condition: {survivor.get('condition', 'Unknown')}")
                        print(f"     Urgency: {survivor.get('urgency_level', 'Unknown')}")
                        print(f"     Confidence: {survivor.get('confidence', 0):.2f}")
                
                priority = analysis.get('rescue_priority', 'medium')
                print(f"🚨 Priority Level: {priority.upper()}")
                
                if analysis.get('recommended_action'):
                    print(f"💡 Recommended Action: {analysis['recommended_action']}")
                

                # Trigger rescue protocol
                from rescue_protocol import RescueProtocol
                rescue_protocol = RescueProtocol()
                rescue_protocol.activate_rescue_protocol({  # Changed method name
                    'analysis': analysis,
                    'video_id': video_id,
                    'detection_time': datetime.now().isoformat(),
                    'scan_number': self.total_scans
                })
                
            else:
                print("✅ No survivors detected in this scan")
                print(f"📝 Scene description: {analysis.get('detailed_description', 'No description')}")
            
        except Exception as e:
            print(f"❌ Error processing analysis: {e}")
            print(f"Raw response: {response_text}")
    
    def stop_detection_system(self):
        """Stop the detection system"""
        print("🛑 Stopping body detection system...")
        
        self.is_detecting = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=5)
        
        print("\n📊 DETECTION STATISTICS:")
        print(f"   Total scans performed: {self.total_scans}")
        print(f"   Survivors found: {self.survivors_found}")
        print(f"   Detection rate: {(self.survivors_found/max(self.total_scans, 1)):.2f} per scan")
        
        print("✅ Body detection system stopped")
    
    def get_detection_status(self):
        """Get detection system status"""
        return {
            'is_detecting': self.is_detecting,
            'total_scans': self.total_scans,
            'survivors_found': self.survivors_found,
            'last_scan_time': self.last_scan_time,
            'index_id': self.index.id if self.index else None
        }