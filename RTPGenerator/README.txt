Included in this directory is:
	RTP_client.py  
	RTP_server.py

RTP gstreamer client and server. 

This is UDP only - no RTSP control support. This means, no renegotiation of
resolution/size, no retransmission of lost packets, no information on if
a client is connected to a server AND each client/server is a 1:1 pair.

If you are looking for a 1:many video service, use the RTSP client/server.


