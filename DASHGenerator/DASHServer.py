import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstVideo, GLib

Gst.init(None)

class settings:
    stream_location = 'rtmp://127.0.0.1/dash/streamname_'
    speed_preset = 3
    amplification = 4

class Main:
    def __init__(self):
        self.mainloop = GLib.MainLoop()

        self.pipeline = Gst.Pipeline()

        self.clock = self.pipeline.get_pipeline_clock()

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::error', self.on_error)

        rates = [
            ['low', 'video/x-raw, width=640, height=360', 500, 3],
            ['med', 'video/x-raw, width=1280, height=720', 1500, 3],
            ['high', 'video/x-raw, width=1920, height=1080', 5000, 4]
        ]

        # Video input
        # filesrc location=result.mp4 ! decodebin2 ! ffmpegcolorspace ! video/x-raw-rgb ! avimux !
        self.malm([
            ['multifilesrc', None, {'location': './jellyfish-25-mbps-hd-hevc.mpg', 'loop':'true'}],
            ['videoparse', None, {'width':1920,'height':1080, 'framerate':Gst.Fraction(30, 1)}],
            #['videotestsrc', None, {}],
            ['capsfilter', None, {'caps': 'video/x-raw, width=1920, height=1080'}],
            ['videoconvert', None, {}],
            ['deinterlace', None, {}],
            ['videorate', None, {}],
            ['capsfilter', None, {'caps': 'video/x-raw, framerate=30000/1001' }],
            ['tee', 'vinput', {}]
        ])

        # Create each encoder, muxer, and rtmpsink.
        for rate in rates:
            self.malm([
                ['queue', 'v{}'.format(rate[0]), {'max-size-bytes': 104857600}],
                ['videoscale', None, {}],
                ['capsfilter', None, {'caps': rate[1]}],
                ['x264enc', None, {
                    'speed-preset': settings.speed_preset,
                    'tune': 'zerolatency',
                    'bitrate': rate[2],
                    'threads': rate[3],
                    'option-string': 'scenecut=0'
                }],
                ['capsfilter', None, {'caps': 'video/x-h264, profile=baseline'}],
                ['h264parse', None, {}],
                ['flvmux', 'm{}'.format(rate[0]), {'streamable': True}],
                ['rtmpsink', None, {'location': settings.stream_location + rate[0]}]
            ])

            self.vinput.link(getattr(self, 'v{}'.format(rate[0])))

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add(2 * 1000, self.do_keyframe, None)
        self.mainloop.run()

    def stop(self): 
        print('Exiting...')
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, 'stream')
        self.pipeline.set_state(Gst.State.NULL)
        self.mainloop.quit()

    def do_keyframe(self, user_data):
        # Forces a keyframe on all video encoders
        event = GstVideo.video_event_new_downstream_force_key_unit(self.clock.get_time(), 0, 0, True, 0)
        self.pipeline.send_event(event)

        return True

    def on_error(self, bus, msg):
        print('on_error', msg.parse_error())

    def malm(self, to_add):
        # Make-add-link multi
        prev = None
        for n in to_add:
            element = Gst.ElementFactory.make(n[0], n[1])

            if not element:
                raise Exception('cannot create element {}'.format(n[0]))

            if n[1]: setattr(self, n[1], element)

            for p, v in n[2].items():
                if p == 'caps':
                    caps = Gst.Caps.from_string(v)
                    element.set_property('caps', caps)
                else:
                    element.set_property(p, v)

            self.pipeline.add(element)
            if prev: prev.link(element)

            prev = element

main = Main()
try:
    main.run()
except KeyboardInterrupt:
    main.stop()
