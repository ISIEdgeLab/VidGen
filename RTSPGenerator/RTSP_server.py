#!/usr/bin/python 
import gi
import argparse

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GstRtspServer, GstRtsp

GObject.threads_init()
Gst.init(None)

class RTSP_Server:
  def __init__(self, fr=30, width=1280, height=720, port=5000, use_tcp=False):
    self.server = GstRtspServer.RTSPServer.new()
    self.address = '0.0.0.0'
    self.port = str(port)
    
    self.launch_description = '( videotestsrc is-live=1 ! queue ! video/x-raw, framerate=%d/1, width=%d, height=%d  ! timeoverlay ! x264enc  tune=zerolatency ! queue ! rtph264pay pt=96 config-interval=1 name=pay0 )' % (fr, width, height)
    
    self.server.set_address(self.address)
    self.server.set_service(self.port)
    
    self.server.connect("client-connected",self.client_connected) 
    self.factory = GstRtspServer.RTSPMediaFactory.new()
    self.factory.set_launch(self.launch_description)
    self.factory.set_shared(True)
  
    # Force TCP?
    if use_tcp:
      self.factory.set_protocols(GstRtsp.RTSPLowerTrans.TCP)
  
    self.factory.set_transport_mode(GstRtspServer.RTSPTransportMode.PLAY)
    self.mount_points = self.server.get_mount_points()
    self.mount_points.add_factory('/video', self.factory)
    
    self.server.attach(None)
    print("Stream Ready")
    GObject.MainLoop().run()
  
  def client_connected(self, arg1, arg2):
    print("Client Connected")
                                                                    
 
def main():
  parser = argparse.ArgumentParser(description='Test video source served via RTSP/RTP')
  parser.add_argument('-p', '--port', type=int, default=5000, help="Server port")
  parser.add_argument('-f', '--framerate', type=int, default=30, help='Desired framerate for video served.')  
  parser.add_argument('-W', '--width', type=int, default=1280, help='Width of video frame.')
  parser.add_argument('-H', '--height', type=int, default=720, help='Height of video frame.')
  parser.add_argument('-T', '--tcp', action='store_true', default=False, help='Force all communication over TCP')
  args = parser.parse_args()
  server = RTSP_Server(fr=args.framerate, width=args.width, height=args.height, port=args.port, use_tcp=args.tcp)

if __name__ == "__main__":
  main()


