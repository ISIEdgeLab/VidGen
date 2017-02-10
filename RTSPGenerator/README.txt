Included in this directory is:
	RSTP_client.py  
	RSTP_server.py

RTSP gstreamer client and server. 

These generate UDP and TCP - UDP for RTP video, and TCP for RTSP control support.
If you are looking for generating just a single UDP flow, use the plain RTP
server/client.

Currently RTSP support for renegotiation of resolution/size and retransmission of lost packets
is turned off. 

One RTSP server can serve data to many clients.


