import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstVideo, GLib

Gst.init(None)

class settings:
    stream_location = 'rtmp://127.0.0.1/dash/streamname_'

class Main:
    def __init__(self):
        self.mainloop = GLib.MainLoop()

        self.pipeline = Gst.parse_launch('playbin uri="http://127.0.0.1:8000/all.mpd" audio-sink="fakesink sync=false"')

        self.clock = self.pipeline.get_pipeline_clock()

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::error', self.on_error)
        
        #Create the elements in the video sink bin 
        #video/x-h264 ! h264parse ! mp4mux ! filesink location=video.mp4 
        self.bin = Gst.Bin.new("video-bin")
        self.malm([
            ['capsfilter', None, {'caps': 'video/x-raw'}],            
            ['qtmux', None, {}],
            ['filesink', None, {'location':'video.mov'}],
        ],self.bin)
        
        first = None
        for element in self.bin.iterate_elements():
            first = element

        self.pad = first.get_static_pad("sink")
        ghostpad = Gst.GhostPad.new("sink", self.pad)
        self.bin.add_pad(ghostpad)
        
        self.pipeline.set_property('video-sink', self.bin)        
        
   
    def malm(self, to_add, pipe):
        # Link elements.
        prev = None
        for n in to_add:
            element = Gst.ElementFactory.make(n[0], n[1])
            if not element:
                raise Exception('cannot create element {}'.format(n[0]))
        
            if n[1]: setattr(self, n[1], element)
            
            for p,v in n[2].items():
                if p == 'caps':
                    caps = Gst.Caps.from_string(v)
                    element.set_property('caps', caps)
                else:
                    element.set_property(p,v)
                
            pipe.add(element)
            if prev:
                prev.link(element)
            
            prev = element

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add(2*1000, self.read_caps, None)
        self.mainloop.run()


    def read_caps(self, user_data):
        print(self.pad.get_property("caps"))
        
    def stop(self): 
        print('Exiting...')
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, 'stream')
        self.pipeline.set_state(Gst.State.NULL)
        self.mainloop.quit()

    def on_error(self, bus, msg):
        print('on_error', msg.parse_error())


main = Main()
try:
    main.run()
except KeyboardInterrupt:
    main.stop()
