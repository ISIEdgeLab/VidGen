#!/usr/bin/python 

import gi
import time
import signal
import argparse
import logging
import time

LOGGER = logging.getLogger(__name__)

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GstRtspServer

class RTSPClient:
  #gst-launch-1.0 -v rtspsrc location="rtsp://localhost:5000/video" ! rtph264depay ! avdec_h264 ! fpsdisplaysink sync=true text-overlay=false fps-update-interval=600 video-sink=fakesink
  def __init__(self, server='localhost', port=5000, timeout=60):
    self.rtpbin_last_rtpstats = {}
    self.prev_packets_lost = 0
    self.packets_lost = 0
    self.metric_period = 1.0
    self._logger = logging.getLogger(__name__)
    self.timeout = timeout
    
    # Stats
    self.rend = 0
    self.drop = 0
    self.last_jitterbuffer_stats = dict()
    self.session_stats = dict()
    
    self.location = "rtsp://%s:%d/video" % (server, port)
    self.pipeline = Gst.parse_launch('rtspsrc drop-on-latency=true location="%s" name="src" ! rtph264depay ! avdec_h264 ! fpsdisplaysink name=sink sync=true text-overlay=false fps-update-interval=600 video-sink=fakesink' % self.location)
    self.sink = self.pipeline.get_by_name('sink')
    self.pad = self.sink.get_static_pad('sink')
    self.caps = self.pad.get_current_caps()
    self.source = self.pipeline.get_by_name('src')
    self.source.connect("new-manager", self.new_src_manager)
    self.last_jitterbuffer = None
    
    
    # Gstreamer bus messages
    self.bus = self.pipeline.get_bus()
    self.bus.add_signal_watch()
    self.bus.connect("message", self.handle_message)

    # Main loop
    self.mainloop = GObject.MainLoop()
    GObject.timeout_add(1000 * 5, self.update_stats)
  
  def new_src_manager(self, rtspsrc, manager):
    self.rtpbin = manager
    self.rtpbin.connect("on-ssrc-active", self.ssrc_active)
  
  def ssrc_active(self, rtpbin, session_id, ssrc):
    assert rtpbin == self.rtpbin
    session = rtpbin.emit("get-internal-session", session_id)
    if session is not None:
      source = session.emit("get-source-by-ssrc", ssrc)
      stats = source.get_property('stats')
      if stats is not None:
        for tag in ['jitter']:
          self.session_stats[tag] = stats.get_uint(tag)[1]
        for tag in ['bitrate', 'packets-received', 'packets-lost']:
          if tag != 'packets-lost':
            value = stats.get_uint64(tag)[1]
          else:
            value = stats.get_int(tag)[1]
          if tag == 'bitrate':
            value = "%s" % (str(float(value)/1000) + 'kbps')
          if tag in self.session_stats and self.session_stats[tag] != value:
            self.session_stats[tag+'last'] = self.session_stats[tag]
            self.session_stats[tag] = value
          elif tag not in self.session_stats:
            self.session_stats[tag+'last'] = 0
            self.session_stats[tag] = value
          else:
            self.session_stats[tag] = value
        caps = "%s" % self.pad.get_current_caps()
        if caps != None:
          if 'width' in caps:
            width = caps.split('width=')[1].split(',')[0]
            if 'height' in caps:
              height = caps.split('height=')[1].split(',')[0]
              self.session_stats['geometry'] = '%sx%s' %(width, height)

    
  def update_stats(self):
    drop = self.sink.get_property('frames-dropped')
    rend = self.sink.get_property('frames-rendered')
    if self.last_jitterbuffer != None:
      buffer_stats = self.last_jitterbuffer.get_property('stats')
      old_jstats = self.last_jitterbuffer_stats
      new_stats = dict(num_lost=buffer_stats.get_uint64('num-lost')[1], num_late=buffer_stats.get_uint64('num-late')[1], num_dup=buffer_stats.get_uint64('num-duplicates')[1] , rtx_count=buffer_stats.get_uint64('rtx-count')[1], rtx_success_count=buffer_stats.get_uint64('rtx-success-count')[1])
      self.last_jitterbuffer_stats = new_stats    
      diff_stats = { name: val - old_jstats.get(name, 0) for name, val in new_stats.items() }
      diff_stats['buffer'] = self.last_jitterbuffer.get_property('percent')
    else:
      diff_stats = {}
    
    
    output_msg = "ts:%d," % int(time.time())
    #for tag in ['num_late', 'num_lost', 'num_dup', 'rtx_count', 'rtx_success_count', 'buffer']:
    #  if tag in diff_stats:
    #    output_msg = output_msg + tag + ":%d," % (diff_stats[tag])
    for tag in self.session_stats:
      if 'last' not in tag:
        if tag in ['packets-received', 'packets-lost']:
          output_msg = output_msg + tag + ":%d," % (self.session_stats[tag] - self.session_stats[tag+'last'])
        elif tag in ['geometry', 'bitrate']:
          output_msg = output_msg + tag + ":%s," % (self.session_stats[tag])
        else:
          output_msg = output_msg + tag + ":%d," % (self.session_stats[tag])
    output_msg = output_msg + "FPS:%d" %((rend-self.rend)/5)
    print(output_msg)
    self.drop = drop
    self.rend = rend
    self.timeout = self.timeout - 1;
    if self.timeout < 0:
      self.stop()
    return True
  
  def handle_message(self, bus, msg):
    if msg.type == Gst.MessageType.STREAM_STATUS:
      status, owner = msg.parse_stream_status()
      if owner.get_name() == 'rtpjitterbuffer0':
        self.last_jitterbuffer = owner
        self.last_jitterbuffer_stats = dict()
        #self.last_jitterbuffer.set_property('do-retransmission', 1)

  def run(self):
    print("Setting pipeline to play.")
    self._logger.info("Connectng to %s", self.location)
    ret = self.pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
      print("Unalbe to set the pipeline to playing.")
      exit(-1)
    self.mainloop.run()

  def stop(self):
    print("Exiting")
    self.pipeline.set_state(Gst.State.NULL)
    self.exit = True
    exit(1)

if __name__ == "__main__":
  GObject.threads_init()
  Gst.init(None)
  parser = argparse.ArgumentParser(description='RTSP/RTP Client')
  parser.add_argument('-s', '--server', default='localhost', help='RTSP server name or address')
  parser.add_argument('-p', '--port', type=int, default=5000, help='RTSP server port number')
  parser.add_argument('-t', '--timeout', type=int, default=60, help='Time to live.')
  args = parser.parse_args()
             
  client = RTSPClient(server=args.server, port=args.port, timeout=args.timeout)
  client.run()
    
