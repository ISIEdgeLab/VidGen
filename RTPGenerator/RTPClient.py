#!/usr/bin/python 

import gi
import time
import signal
import sys
import argparse
import time
import logging

LOGGER = logging.getLogger(__name__)

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

try:
  gi.require_version('Gst', '1.0')
except:
  print("This requires GST>=1.0")
  raise
from gi.repository import Gst, GObject

class RTPClient:
  # gst-launch-1.0 -v  udpsrc port=5000 ! "application/x-rtp, clock-rate=90000, encoding-name=(string)H264, payload=96,framerate=30/1" ! rtph264depay! avdec_h264 ! fpsdisplaysink sync=true text-overlay=false  fps-update-interval=600  video-sink=fakesink
  def __init__(self, port=5000, timeout=60, width=320, height=240, fr=60, stats_file=None, lazy_printing=False):
    self.use_buffer = True
    self.metric_period = 1.0
    self._logger = logging.getLogger(__name__)
    self.timeout = timeout
    self.exit = False
    self.port = port
    self.lazy_printing = lazy_printing
    
    if stats_file == None:
      self.stats_file = None
    else:
      try:
        self.stats_file = open(stats_file, 'w')
      except Exception as e:
        print(e)
        self.stats_file = None
        pass
      
    # We want to exit gracefully
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
      try:
        signum = getattr(signal,i)
        signal.signal(signum,self.sighandler)
      except (RuntimeError,ValueError),m:
        print "Not handling signal %s"%i
        pass

    # Stats
    self.rend = 0
    self.drop = 0
    self.rtx = 0
    
    self.src = Gst.ElementFactory.make('udpsrc')
    self.src.set_property("port", self.port)
    #self.caps = Gst.Caps('application/x-rtp,clock-rate=90000,clock-base=(uint)101553131,seqnum-base=(uint)64602,encoding-name=(string)H264,payload=96,framerate=%d/1,width=%d,height=%d' % (fr,width,height))
    self.caps = Gst.Caps('application/x-rtp,clock-rate=90000,encoding-name=(string)H264, payload=96,framerate=(fraction)%d/1,width=(int)%d,height=(int)%d' % (fr,width,height))
    self.filter = Gst.ElementFactory.make("capsfilter", "filter")
    self.filter.set_property("caps", self.caps)
    
    if self.use_buffer:
      self.buffer = Gst.ElementFactory.make('rtpjitterbuffer')
      self.buffer.set_property('mode', 'synced')
      self.buffer.set_property('drop-on-latency', 'true')
      self.buffer.set_property('latency', 200)
      self.buffer.set_property('do-retransmission', 'true')
      self.buffer.set_property('rtx-max-retries', 0)
      self.buffer.set_property('rtx-min-retry-timeout', 50)
      self.buffer.set_property('mode', 0)
    
    self.depay = Gst.ElementFactory.make('rtph264depay')
    self.audio = Gst.ElementFactory.make('avdec_h264')
    self.fsink = Gst.ElementFactory.make('fpsdisplaysink')
    self.fsink.set_property('sync', 'false')
    self.fsink.set_property('text-overlay', 'false')
    self.fsink.set_property('fps-update-interval', 600)
    self.sink = Gst.ElementFactory.make('fakesink')
    self.fsink.set_property('video-sink', self.sink)
    
    self.pipeline = Gst.Pipeline()                                                    
    
    self.pipeline.add(self.src)
    self.pipeline.add(self.filter)
    if self.use_buffer:
      self.pipeline.add(self.buffer)
    self.pipeline.add(self.depay)
    self.pipeline.add(self.audio)
    self.pipeline.add(self.fsink)                                                        

    self.src.link_filtered(self.filter)
    if self.use_buffer:
      self.filter.link(self.buffer)
      self.buffer.link(self.depay)
    else:
      self.filter.link(self.depay)
    self.depay.link(self.audio)
    self.audio.link(self.fsink)                                                                                        

    # Gstreamer bus messages
    self.bus = self.pipeline.get_bus()
    self.bus.add_signal_watch()
    self.bus.connect("message::tag", self.bus_message_tag)

    # Main loop
    self.mainloop = GObject.MainLoop()
    GObject.timeout_add(1000, self.update_stats)
  
  def sighandler(self, signum, frame):
    print("Caught signal %d" % signum)
    self.exit = True
  
  def update_stats(self):
    ts = str(time.time())
    drop = self.fsink.get_property('frames-dropped')
    rend = self.fsink.get_property('frames-rendered')
    maxfps = self.fsink.get_property('max-fps')
    minfps = self.fsink.get_property('min-fps')
    if self.use_buffer:
      s = self.buffer.get_property('stats')
      rtx = s.get_value('rtx-count')
      buffer_fill = self.buffer.get_property('percent')
      mesg = ("%s MIN:%d MAX:%d FPS:%d DropPS:%d RTX-count:%s Buffer:%s" %(ts, minfps, maxfps, rend-self.rend,drop-self.drop, rtx-self.rtx, str(buffer_fill)))
      self.rtx = rtx
    else:
      buffer_fill = 0
      mesg = ("%s FPS:%d DropPS:%d RTX-count:%s Buffer:%s" %(ts, rend-self.rend,drop-self.drop, "-1", "-1"))
    self.output(mesg)
    self.drop = drop
    self.rend = rend
    self.timeout = self.timeout - 1;
    if self.timeout < 0 or self.exit:
      self.stop()
    return True
  
  def bus_message_tag(self, bus, message):
    taglist = message.parse_tag()
    for x in range(taglist.n_tagss()):
      print taglist.nth_tag_name(x)
  
  def run(self):
    print("Setting pipeline to play.")
    ret = self.pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
      print("Unalbe to set the pipeline to playing.")
      exit(-1)
    try:
      self.mainloop.run()
    except KeyboardInterrupt:
      print("Killed by ^C")
      self.stop()
    except Exception as e:
      print("Exception: %s" % e)
      self.stop()

  def stop(self):
    print("Exiting")
    try:
      self.pipeline.set_state(Gst.State.NULL)
    except Exception as e:
      print("Failed to stop Gstreamer pipline.")
    self.exit = True
    if self.stats_file != None:
      try:
        self.stats_file.close()
      except Exception as e:
        print("Failed to close stats file: %s" % e)
    sys.stdout.flush()
    exit(1)
  
  def output(self, mesg):
    if self.stats_file == None:
      print(mesg)
      if not self.lazy_printing:
        sys.stdout.flush()
    else:
      self.stats_file.write(mesg + '\n')
      if not self.lazy_printing:
        self.stats_file.flush()

def main():
  GObject.threads_init()
  Gst.init(None)
  parser = argparse.ArgumentParser(description='RTP Client')
  parser.add_argument('-p', '--port', type=int, default=5000, help='RTP server port number')
  parser.add_argument('-t', '--timeout', type=int, default=60, help='Time to live.')
  parser.add_argument('-s', '--statsfile', default=None, help='File to log stats to.')
  parser.add_argument('-l', '--lazy_printing', default=False, action='store_true') 
  parser.add_argument('-f', '--framerate', default=60, type=int, help='Framerate (should match server)')
  parser.add_argument('-H', '--height', default=720, type=int, help='Geometry of frame: height')
  parser.add_argument('-W', '--width', default=1280, type=int, help='Geometry of frame: width')
  args = parser.parse_args()
  
  print(args)
  
  client = RTPClient(port=args.port, timeout=args.timeout, stats_file=args.statsfile,  width=args.width, height=args.height, fr=args.framerate, lazy_printing=args.lazy_printing)

  # Set up quitting cleanly
  def signal_handler(signal, frame):
    print("Quitting after getting quit signal.")
    client.stop()
    sys.exit(0)

  client.run()
    
if __name__ == "__main__":
  main()
