# -*- coding: utf-8 -*-
import asyncio
from socket import gethostname

class HttpResponder(asyncio.Protocol):
    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print('Connection from {}'.format(peername))
        self.transport = transport
        pass

    def connection_lost(self, exc):
        print('Connection lost')
        pass

    def data_received(self, data):
        message = data.decode()
        print('Data received: {!r}'.format(message))
        print('Close the client socket')
        #self.transport.close()
        pass

    def eof_received(self):
        print('End data')
        pass

class HttpRequest:
    def __init__(self, method, path, version, headers):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers

    def pprint(self):
        print('{} {} {}'.format(self.method, self.path, self.version))
        for h in self.headers:
            print ('  {}: {}'.format(h, self.headers[h]))
        print()

class HttpAnswer:
    def __init__(self, request):
        self.request = request
        self.statusCode = 200
        self.statusText = 'OK'
        self.version = 'HTTP/1.1'
        self.headers = {
            'Content-Type' : 'text/html; charset=utf8',
            'Server' : 'Linux UPnP/1.0 DoorDev/1.3-50131 (ZPS3)'
        }
        self.data = None

    def write(self, writer):
        writer.write('{} {} {}\r\n'.format(self.version, self.statusCode, self.statusText).encode('latin1'))
        for h in self.headers:
            writer.write('{}: {}\r\n'.format(h, self.headers[h]).encode('latin1'))
        writer.write(b'\r\n')
        if self.data != None:
            writer.write(self.data.encode('utf-8'))
            writer.write(b'\r\n')

    def pprint(self):
        print('{} {} {}'.format(self.version, self.statusCode, self.statusText))
        for h in self.headers:
            print('  {}: {}'.format(h, self.headers[h]))
        print()

    def execute(self):
        pass

class ServerErrorAnswer(HttpAnswer):
    def execute(self):
        self.statusCode = 500
        self.statusText = 'Internal Server Error'
        self.data = '<html><body><h1>Internal Server Error</h1><p>An internal server error. See logs.</p></body></html>'

class DescriptionAnswer(HttpAnswer):
    def __init__(self, request, upnp):
        super(DescriptionAnswer, self).__init__(request)
        self.upnp = upnp

    def execute(self):

        self.headers['Content-Type'] = 'application/xml; charset=utf-8'
        URL = 'http://{}'.format(self.request.headers['host'])
        HOST = self.request.headers['host'].split(':')[0]
        HOSTNAME = gethostname()

        self.data = """<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0" configId="{CONFIGID}">
            <specVersion>
                <major>1</major>
                <minor>0</minor>
            </specVersion>
            <device>
                <deviceType>{DEVICE.deviceType}</deviceType>
                <friendlyName>{DEVICE.friendlyName}</friendlyName>
                <manufacturer>{DEVICE.manufacturer}</manufacturer>
                <manufacturerURL>{DEVICE.manufacturerURL}</manufacturerURL>
                <modelDescription>{DEVICE.Description}</modelDescription>
                <modelName>{DEVICE.modelName}</modelName>
                <modelNumber>{DEVICE.modelNumber}</modelNumber>
                <UDN>uuid:{DEVICE.uuid}</UDN>
                <UPC>{DEVICE.upc}</UPC>
                <iconList>
                <icon>
                    <mimetype>image/png</mimetype>
                    <width>256</width>
                    <height>256</height>
                    <depth>32</depth>
                    <url>{URL}/icon256.png</url>
                </icon>
                <icon>
                    <mimetype>image/png</mimetype>
                    <width>128</width>
                    <height>128</height>
                    <depth>32</depth>
                    <url>{URL}/icon128.png</url>
                </icon>
                <icon>
                    <mimetype>image/png</mimetype>
                    <width>32</width>
                    <height>32</height>
                    <depth>32</depth>
                    <url>{URL}/icon32.png</url>
                </icon>
                </iconList>
                <serviceList>
                    <service>
                        <serviceType>urn:doorctl.sadmin.fr:service:doorgate:1</serviceType>
                        <serviceId>urn:doorctl.sadmin.fr:serviceId:1</serviceId>
                        <SCPDURL>{URL}/scpd.xml</SCPDURL>
                        <controlURL>{URL}/control</controlURL>
                        <eventSubURL>{URL}/event</eventSubURL>
                    </service>
                  <!-- TODO -->
                </serviceList>
                <deviceList>
                  <!-- TODO -->
                </deviceList>
                <presentationURL>https://{HOST}/</presentationURL>
            </device>
        </root>
        """.format(UUID=self.upnp.device.uuid, DEVICE=self.upnp.device, URL=URL, CONFIGID=self.upnp.configId, HOST=HOST, HOSTNAME=HOSTNAME)

class ScpdAnswer(HttpAnswer):
    def execute(self):

        self.headers['Content-Type'] = 'application/xml; charset=utf-8'
        URL = 'http://{}'.format(self.request.headers['host'])

        self.data = """<?xml version="1.0"?>
        <scpd xmlns="urn:schemas-upnp-org:service-1-0" configId="CONFIGID">
            <specVersion>
                <major>1</major>
                <minor>0</minor>
            </specVersion>
            <actionList>
            </actionList>
        </scpd>
        """.format(UUID=UUID, URL=URL, CONFIGID=CONFIGID)

class HttpServer:
    def __init__(self, config):
        self.config = config

    def InConnection(self, reader, writer):
        header = yield from reader.readline()
        cheaders = header.decode('latin1').strip()
        method, path, vers = cheaders.split(' ')
        headers = dict()

        while not reader.at_eof():
            rawheaders = yield from reader.readline()
            headline = rawheaders.decode('latin1').strip().lower()
            if headline == '':
                break
            head, value = headline.split(':', maxsplit=1)
            headers[head.strip()] = value.strip()

        request = HttpRequest(method, path, vers, headers)
        request.pprint()
        ans = self.HttpRouting(request)
        ans.execute()
        ans.pprint()
        ans.write(writer)
        writer.close()

    def HttpRouting(self, request):
        if request.path == '/descr.xml':
            ans = DescriptionAnswer(request, self.config.annoncer)
        elif request.path == '/scpd.xml':
            ans = ScpdAnswer(request)
        else:
            ans = ServerErrorAnswer(request)
        return ans

class HTTP:
    def __init__(self, annoncer, port, netbind):
        self.port = port
        self.netbind = netbind
        self.server = None
        self.http = HttpServer(self)
        self.annoncer = annoncer

        if self.netbind == '0.0.0.0':
            self.netBind = None

    def initLoop(self, loop):
        self.server = asyncio.start_server(self.http.InConnection, port=self.port, host=self.netBind)
        self.httploop = loop.run_until_complete(self.server)

    def dispose(self):
        pass