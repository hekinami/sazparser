from zipfile import ZipFile
from xml.dom.minidom import parse, parseString
from isodate import parse_datetime
from io import StringIO


class SazFile:
    class ParseError(Exception):
        pass

    def __init__(self, filename):
        self.filename = filename
        self._zipfile = None
        self._sessions = []
        self._cfilelist = []
        self._mfilelist = []
        self._sfilelist = []
        self._session_num = 0

    @property
    def zipfile(self):
        if self._zipfile is None:
            self._zipfile = ZipFile(self.filename)
        return self._zipfile

    @property
    def cfilelist(self):
        if not self._cfilelist:
            self._cfilelist = [
                x for x in self.zipfile.namelist()
                if x.startswith('raw') and x.endswith('_c.txt')
            ]
        return self._cfilelist

    @property
    def mfilelist(self):
        if not self._mfilelist:
            self._mfilelist = [
                x for x in self.zipfile.namelist()
                if x.startswith('raw') and x.endswith('xml')
            ]
        return self._mfilelist

    @property
    def sfilelist(self):
        self._sfilelist = [
                x for x in self.zipfile.namelist()
                if x.startswith('raw') and x.endswith('_s.txt')
            ]
        return self._sfilelist

    @property
    def html(self):
        fname = '_index.htm'
        return self.zipfile.read(fname).decode('utf-8')

    @property
    def content_type(self):
        pass

    @property
    def session_num(self):
        if self._session_num == 0:
            clen = len(self.cfilelist)
            mlen = len(self.mfilelist)
            slen = len(self.sfilelist)

            if not (clen == mlen == slen):
                raise self.ParseError('files missing')

            self._session_num = clen

        return self._session_num

    @property
    def sessions(self):
        if self._sessions == []:
            for i in range(self.session_num):
                rawdata = {
                    "c": self.zipfile.read(self.cfilelist[i]),
                    "m": self.zipfile.read(self.mfilelist[i]),
                    "s": self.zipfile.read(self.sfilelist[i]),
                }
                session = Session(rawdata)
                self._sessions.append(session)

        return self._sessions

    @property
    def sequence_time(self):
        starttime = min([
            parse_datetime(s.timing['ClientBeginRequest'])
            for s in self.sessions
            if str(parse_datetime(s.timing['ClientBeginRequest'])) != '0001-01-01 00:00:00'
        ])

        endtime = max([
            parse_datetime(s.timing['ClientDoneResponse'])
            for s in self.sessions
            if str(parse_datetime(s.timing['ClientDoneResponse'])) != '0001-01-01 00:00:00'
        ])

        return (endtime - starttime).total_seconds()


class Session:
    def __init__(self, rawdata):
        self._rawdata = rawdata
        self._crequest = None
        self._srequest = None
        self._metadata = None

    @property
    def client_request(self):
        if self._crequest is None:
            self._crequest = ClientRequest(self._rawdata['c'])

        return self._crequest

    @property
    def server_request(self):
        if self._srequest is None:
            self._srequest = ServerRequest(self._rawdata['s'])

        return self._srequest

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = MetaData(self._rawdata['m'])

        return self._metadata

    @property
    def timing(self):
        return self.metadata.timing

    @property
    def is_static(self):
        return self.server_request.content_type in [
            b'image/png', b'image/gif', b'text/javascript', b'text/css'
        ]

    @property
    def https_handshake_time(self):
        return int(self.timing['HTTPSHandshakeTime'])

    @property
    def tcp_connec_time(self):
        return int(self.timing['TCPConnectTime'])

    @property
    def dns_time(self):
        return int(self.timing['DNSTime'])

    @property
    def gateway_time(self):
        return int(self.timing['GatewayTime'])

    @property
    def server_time(self):
        ret = 0
        starttime = parse_datetime(self.timing['ServerGotRequest'])
        endtime = parse_datetime(self.timing['ServerBeginResponse'])

        if not (str(starttime) == '0001-01-01 00:00:00' \
           or str(endtime) == '0001-01-01 00:00:00'):
            ret = (endtime - starttime).total_seconds()
            ret = 0 if ret < 0 else ret

        return ret

    @property
    def download_time(self):
        ret = 0
        starttime = parse_datetime(self.timing['ServerBeginResponse'])
        endtime = parse_datetime(self.timing['ClientDoneResponse'])

        if not (str(starttime) == '0001-01-01 00:00:00' \
           or str(endtime) == '0001-01-01 00:00:00'):
            ret = (endtime - starttime).total_seconds()
            ret = 0 if ret < 0 else ret

        return ret


class InfoBase:
    def __init__(self, rawdata):
        self._rawdata = rawdata


class Request(InfoBase):
    def __init__(self, rawdata):
        super(Request, self).__init__(rawdata)
        self._message = ''
        self._headers = {}
        self._body = None

    @property
    def message(self):
        if not self._message:
            self._message = self._rawdata.split(b'\r\n')[0]
        return self._message

    @property
    def headers(self):
        if not self._headers:
            self._headers = {
                h.split(b':')[0].strip(): h.split(b':', 1)[1].strip()
                for h in self._rawdata.split(b'\r\n\r\n')[0].split(b'\r\n')[1:]
            }
        return self._headers

    @property
    def body(self):
        if self._body is None:
            self._body = self._rawdata.split(b'\r\n\r\n', 1)[1]
        return self._body


class ClientRequest(Request):
    @property
    def method(self):
        return self.message.split(b' ')[0]


class ServerRequest(Request):
    @property
    def status(self):
        return self.message.split(b' ')[1]

    @property
    def content_type(self):
        ret = None
        try:
            ret = self.headers[b'Content-Type'].split(b';')[0].strip()
        except KeyError:
            pass
        return ret


class MetaData(InfoBase):
    def __init__(self, rawdata):
        super(MetaData, self).__init__(rawdata)
        self._timing = {}

    @property
    def timing(self):
        if not self._timing:
            dom = parseString(self._rawdata.decode('utf-8-sig'))
            item = dom.getElementsByTagName('SessionTimers')[0]

            for key in item.attributes.keys():
                self._timing[key] = item.attributes[key].value

        return self._timing


def main():
    import argparse
    parser = argparse.ArgumentParser(description='saz file parser')
    parser.add_argument('filename', help='saz file name')
    args = parser.parse_args()

    sazfile = SazFile(args.filename)
    static_count, server_time, dserver_time = 0, 0.0, 0.0
    download_time, ddownload_time = 0.0, 0.0
    dns_time, tcp_connec_time, https_handshake_time, gateway_time = 0, 0, 0, 0
    ddns_time, dtcp_connec_time, dhttps_handshake_time, dgateway_time = 0, 0, 0, 0
    for num, session in enumerate(sazfile.sessions):
        if session.is_static:
            static_count += 1
            server_time += session.server_time
            download_time += session.download_time
            dns_time += session.dns_time
            tcp_connec_time += session.tcp_connec_time
            https_handshake_time += session.https_handshake_time
            gateway_time += session.gateway_time
        else:
            dserver_time += session.server_time
            ddownload_time += session.download_time
            ddns_time += session.dns_time
            dtcp_connec_time += session.tcp_connec_time
            dhttps_handshake_time += session.https_handshake_time
            dgateway_time += session.gateway_time
    print(
        "{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8},{:8}".format(
            sazfile.session_num,
            static_count,
            round(server_time, 2),
            round(dserver_time, 2),
            round(download_time, 2),
            round(ddownload_time, 2),
            dns_time, ddns_time,
            tcp_connec_time, dtcp_connec_time,
            https_handshake_time, dhttps_handshake_time,
            gateway_time, dgateway_time,
        )
    )


if __name__ == '__main__':
    main()
