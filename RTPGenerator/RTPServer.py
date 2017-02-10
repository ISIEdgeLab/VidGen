#!/usr/bin/python 
import gi
import time
import argparse
import signal

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

GObject.threads_init()
Gst.init(None)

class RTPServer:
  
  pipeline=None
  
  def __init__(self, fr=60, width=320, height=240, port=5000, client='localhost', stats_file=None):
    self.client=client
    self.port = port
    use_timeoverlay = False
    
    # Try to exit gracefully
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
      try:
        signum = getattr(signal,i)
        signal.signal(signum,self.sighandler)
      except (RuntimeError,ValueError),m:
        print "Not handling signal %s"%i
        pass
    
    if stats_file != None:
      try:
        self.stats_file = open(stats_file, 'w')
      except Exception as e:
        print("Could not open stats file: %s." % stats_file)
        self.stats_file = None
        pass
    else:
      self.stats_file = None

    self.src = Gst.ElementFactory.make('videotestsrc')
    self.src.set_property("is-live", 1)
    print("Using width %d x height %d at framerate %d" % (width,height,fr))
    self.caps = Gst.Caps('video/x-raw,framerate=(fraction)%d/1,width=(int)%d,height=(int)%d'% (fr,width, height))
    #self.caps =  Gst.Caps('video/x-raw,clock-rate=90000,clock-base=(uint)101553131,seqnum-base=(uint)64602,framerate=(fraction)%d/1,width=%d,height=%d '% (fr, width, height))
    self.filter = Gst.ElementFactory.make("capsfilter", "filter")
    self.filter.set_property("caps", self.caps)
    if use_timeoverlay:
      self.timeoverlay = Gst.ElementFactory.make('timeoverlay')
    self.encode = Gst.ElementFactory.make('x264enc')
    self.encode.set_property('key-int-max', 50)
    #self.encode.set_property('bframes', 4)
    #self.encode.set_property('bitrate', 500)
    self.encode.set_property('tune', 'zerolatency')
    self.encode.set_property('speed-preset', 'superfast')
    self.pay = Gst.ElementFactory.make('rtph264pay')
    self.pay.set_property("name", 'pay0')
    self.pay.set_property("pt", 96)
    
    # UDP Sink
    self.sink = Gst.ElementFactory.make('udpsink')
    self.sink.set_property('host', self.client)  
    self.sink.set_property('port', self.port)   

    self.pipeline = Gst.Pipeline()
    
    self.pipeline.add(self.src)
    self.pipeline.add(self.filter)
    if use_timeoverlay:
      self.pipeline.add(self.timeoverlay)
    self.pipeline.add(self.encode)
    self.pipeline.add(self.pay)
    self.pipeline.add(self.sink)
    
    self.src.link_filtered(self.filter)
    if use_timeoverlay:
      self.filter.link(self.timeoverlay)
      self.timeoverlay.link(self.encode)
    else:
      self.filter.link(self.encode)
    self.encode.link(self.pay)
    self.pay.link(self.sink)
    
    self.bus = self.pipeline.get_bus()
  
  def sighandler(self, signum, frame):
    print("Caught signal %d" % signum)
    self.stop()
    exit()
  
  def set_start(self):
    ret = self.pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
      mesg = "Unable to set the pipeline to the playing state."
      self.output(mesg)
      return False
    return True
  
  def pop_messages(self):
    message = self.bus.timed_pop_filtered(1000, Gst.MessageType.ANY)
    if message != None:
      if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        self.output("Error received from element %s: %s" % (message.src.get_name(), err))
        self.output("Debugging information: %s" % debug)
      elif message.type == Gst.MessageType.EOS:
        self.output("End-Of-Stream reached.")
        return False
      elif message.type == Gst.MessageType.STATE_CHANGED:
        if isinstance(message.src, Gst.Pipeline):
          old_state, new_state, pending_state = message.parse_state_changed()
          mesg = "Pipeline state changed from %s to %s." % (old_state.value_nick, new_state.value_nick)
          self.output(mesg)
      else:
        self.output("Unexpected message received. %s " % message.src.get_name())
        return True
    return True
  
  def stop(self):
    self.pipeline.set_state(Gst.State.NULL)
    if self.stats_file != None:
      self.stats_file.close()
    
  def output(self, mesg):
    if self.stats_file == None:
      print(mesg)  
    else:
      self.stats_file.write(mesg)
  

def main():
  parser = argparse.ArgumentParser(description='Test video source served via RTP')
  parser.add_argument('-t', '--timeout', type=int, default=0, help="Time till server is automatically killed (if none given, server runs till killed)")
  parser.add_argument('-c', '--client', default='localhost', help="Client (RTP is 1:1, use RTSP for 1:many)")
  parser.add_argument('-p', '--port', type=int, default=5000, help="Server port")
  parser.add_argument('-f', '--framerate', type=int, default=60, help='Desired framerate for video served.')  
  parser.add_argument('-s', '--statfile', default=None, help='Name of file to log stats in.')
  parser.add_argument('-W', '--width', type=int, default=1280, help='Width of video frame.')
  parser.add_argument('-H', '--height', type=int, default=720, help='Height of video frame.')
  args = parser.parse_args()
  GObject.threads_init()
  Gst.init(None)
  server = RTPServer(fr=args.framerate, width=args.width, height=args.height, port=args.port, client=args.client, stats_file=args.statfile)

  if not server.set_start():
    print("Failed to start.")
    exit(-1)

  start = time.time()
  print("Started server:")
  print(args)
  while True:
    try:
      ret = server.pop_messages()
      if not ret:
        server.stop()
        break
      if args.timeout > 0: 
        now = time.time()
        if now > start + args.timeout:
          print("Hit timeout. Exiting.")
          server.stop()
          break
    except Exception as e:
      server.stop()
      print("Breaking: %s" % e)
      break
  

if __name__ == "__main__":
  main()


