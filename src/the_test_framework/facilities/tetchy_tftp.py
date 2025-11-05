from logging import getLogger
import os
import socket
import threading
from multiprocessing.sharedctypes import Synchronized, Value
from typing import Dict, Tuple, Protocol
from threading import Thread
import uuid


# TFTP opcodes and error codes
OP_RRQ = 1
OP_WRQ = 2
OP_DATA = 3
OP_ACK = 4
OP_ERROR = 5
OP_OACK = 6  # RFC 2347/2348 option acknowledgment

ERR_UNDEF = 0
ERR_NOT_FOUND = 1
ERR_ACCESS = 2
ERR_NO_SPACE = 3
ERR_ILLEGAL = 4
ERR_UNKNOWN_TID = 5
ERR_EXISTS = 6
ERR_NO_USER = 7

DEFAULT_BLKSIZE = 512
MIN_BLKSIZE = 8
MAX_BLKSIZE = 1468  # fits in Ethernet MTU 1500 (20 IP + 8 UDP + 4 TFTP)


logger = getLogger(__name__)


class NewTransferCallback(Protocol):
    def __call__(self, client_addr: str, filename: str, transfer_id: str):
        """called when a new read request for a file is received

        :param client_addr: IP address of the client
        :param filename: requested filename
        :param transfer_id: uuid for this transfer to match follow-up callbacks
        """


class TransferEndedCallback(Protocol):
    def __call__(self, transfer_id: str, error: str | None = None):
        """called when a transfer has been ended

        :param transfer_id: a UUID for this transfer to match follow-up callbacks
        :param error: optional error message
        """


class UpdateSentBytesCallback(Protocol):
    def __call__(self, transfer_id: str, sent_bytes: int, total_size: int):
        """called to update the bytes sent so far

        :param sent_bytes: bytes sent so far
        :param total_size: total filesize in bytes
        :param transfer_id: a UUID for this transfer to match follow-up callbacks
        """


class GossipGirlie:
    """manages communication with non-TFTP entities for TetchyTFTPServer"""
    def __init__(self):
        self._new_transfer_callbacks: dict[str, NewTransferCallback] = {}
        self._transfer_ended_callbacks: dict[str, TransferEndedCallback] = {}
        self._update_sent_bytes_callbacks: dict[str, UpdateSentBytesCallback] = {}

    def _issue_new_transfer_callback(
            self,
            client_addr: str,
            filename: str,
            transfer_id: str,
    ):
        """issues "new transfer" callbacks

        :param client_addr: IP of the client
        :param filename: name of the requested file
        :param transfer_id: a UUID for this transfer to match follow-up callbacks
        """
        kwargs = {"client_addr": client_addr,
                  "filename": filename,
                  "transfer_id": transfer_id}
        for callback in self._new_transfer_callbacks.values():
            Thread(target=callback, kwargs=kwargs, daemon=True).start()

    def _issue_transfer_ended_callback(
            self,
            transfer_id: str,
            error: str | None = None,
    ):
        """issues "transfer ended" callbacks

        :param transfer_id: a UUID for this transfer to match follow-up callbacks
        :param error: optional error message
        """
        kwargs = {"transfer_id": transfer_id, "error": error}
        for callback in self._transfer_ended_callbacks.values():
            Thread(target=callback, kwargs=kwargs, daemon=True).start()

    def _issue_update_sent_bytes_callback(
            self,
            transfer_id: str,
            sent_bytes: int,
            total_size: int,

    ):
        """issues "update on sent bytes" callbacks

        :param sent_bytes: bytes sent so far
        :param total_size: total filesize in bytes
        :param transfer_id: a UUID for this transfer to match follow-up callbacks
        """
        kwargs = {"transfer_id": transfer_id,
                  "sent_bytes": sent_bytes,
                  "total_size": total_size}
        for callback in self._update_sent_bytes_callbacks.values():
            Thread(target=callback, kwargs=kwargs, daemon=True).start()

    def subscribe(
            self,
            new_transfer_callback: NewTransferCallback | None = None,
            update_sent_bytes_callback: UpdateSentBytesCallback | None = None,
            transfer_ended_callback: TransferEndedCallback | None = None,
    ) -> str:
        """register callbacks for TFTP status"""
        callback_id = uuid.uuid4().hex
        if new_transfer_callback is not None:
            self._new_transfer_callbacks[callback_id] = new_transfer_callback
        if update_sent_bytes_callback is not None:
            self._update_sent_bytes_callbacks[callback_id] = update_sent_bytes_callback
        if transfer_ended_callback is not None:
            self._transfer_ended_callbacks[callback_id] = transfer_ended_callback
        return callback_id

    def unsubscribe(self, subscription_id: str):
        self._new_transfer_callbacks.pop(subscription_id, None)
        self._update_sent_bytes_callbacks.pop(subscription_id, None)
        self._transfer_ended_callbacks.pop(subscription_id, None)


class TetchyTFTPServer:
    """TFTP Server, which reports"""
    def __init__(
            self,
            root: str,
            host: str = "0.0.0.0",
            port: int = 69,
            timeout: float = 3.0,
            retries: int = 5,
            default_blksize: int = DEFAULT_BLKSIZE,
            running: Synchronized | None = None,
            sent_bytes: Synchronized | None = None,
    ):
        self.root = os.path.abspath(root)
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.default_blksize = max(MIN_BLKSIZE, min(default_blksize, MAX_BLKSIZE))
        self._running: Synchronized = running or Value("b", True)       # pyright: ignore reportAttributeAccessIssue
        self._sent_bytes: Synchronized = sent_bytes or Value("i", True) # pyright: ignore reportAttributeAccessIssue
        self._sock = None
        os.makedirs(self.root, exist_ok=True)

        self.ipc = GossipGirlie()

    @property
    def sent_bytes(self) -> int:
        with self._sent_bytes.get_lock():
            return self._sent_bytes.value

    def _safe_path(self, name: str) -> str | None:
        # Disallow directory traversal and absolute paths
        name = name.replace("\\", "/")
        p = os.path.abspath(os.path.normpath(os.path.join(self.root, name)))
        if not p.startswith(self.root + os.sep) and p != self.root:
            return None
        return p

    def _recv_req(self, data: bytes) -> Tuple[int, str, str, Dict[str,str]]:
        # Parse RRQ/WRQ: <2B opcode> <filename> 0 <mode> 0 [opt\0val\0]...
        op = int.from_bytes(data[:2], 'big')
        parts = data[2:].split(b"\x00")
        if len(parts) < 2:
            raise ValueError("malformed request")
        filename = parts[0].decode(errors='ignore')
        mode = parts[1].decode(errors='ignore').lower()
        opts: Dict[str, str] = {}
        for i in range(2, len(parts) - 1, 2):
            k = parts[i].decode(errors='ignore').lower()
            v = parts[i+1].decode(errors='ignore')
            if k:
                opts[k] = v
        return op, filename, mode, opts

    def _oack(self, sock, addr, opts) -> bool:
        # Build OACK
        payload = b"\x00" + bytes([OP_OACK])
        for k, v in opts.items():
            payload += k.encode() + b"\x00" + str(v).encode() + b"\x00"

        for attempt in range(self.retries):
            sock.sendto(payload, addr)
            sock.settimeout(self.timeout)
            try:
                pkt, src = sock.recvfrom(2048)
            except socket.timeout:
                continue

            if src != addr:
                self._send_error(sock, src, ERR_UNKNOWN_TID,
                                 "Unknown transfer ID")
                continue

            # ACK(0) = 0x00 0x04 0x00 0x00
            if len(pkt) >= 4 and pkt[1] == OP_ACK and pkt[2:4] == b"\x00\x00":
                return True
        return False

    def _send_error(self, sock: socket.socket, addr: Tuple[str,int], code: int, msg: str):
        pkt = b"\x00" + bytes([OP_ERROR]) + code.to_bytes(2,'big') + msg.encode() + b"\x00"
        try:
            sock.sendto(pkt, addr)
        except Exception:
            pass

    def _send_ack(self, sock: socket.socket, addr: Tuple[str,int], block: int):
        pkt = b"\x00" + bytes([OP_ACK]) + block.to_bytes(2,'big')
        sock.sendto(pkt, addr)

    def _send_data(self, sock: socket.socket, addr: Tuple[str,int], block: int, chunk: bytes):
        pkt = b"\x00" + bytes([OP_DATA]) + block.to_bytes(2,'big') + chunk
        sock.sendto(pkt, addr)
        with self._sent_bytes.get_lock():
            self._sent_bytes.value += len(chunk)

    def _negotiate(self, opts: Dict[str, str], filesize: int | None = None) -> \
    Dict[str, int]:
        accepted: Dict[str, int] = {}
        if 'blksize' in opts:
            try:
                req = int(opts['blksize'])
                accepted['blksize'] = max(MIN_BLKSIZE, min(req, MAX_BLKSIZE))
            except Exception:
                pass
        if 'timeout' in opts:
            try:
                t = int(opts['timeout'])
                accepted['timeout'] = max(1, min(t, 255))
            except Exception:
                pass
        if 'tsize' in opts:
            # If client asked tsize=0 on RRQ, reply with the real size
            if filesize is not None:
                accepted['tsize'] = max(0, int(filesize))
        return accepted

    def _handle_rrq(self, client_addr: Tuple[str, int], filename: str, mode: str, opts: Dict[str, str]):
        transfer_id = uuid.uuid4().hex
        self.ipc._issue_new_transfer_callback(transfer_id, client_addr[0], filename)

        if mode != 'octet':
            logger.info("RRQ rejected: mode %s not supported", mode)
            return
        path = self._safe_path(filename)
        if not path or not os.path.isfile(path):
            self.ipc._issue_transfer_ended_callback(transfer_id, "file not found!")
            logger.info("RRQ file not found: %s", filename)
            # Respond from a new TID per RFC
            tsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tsock.bind((self.host, 0))
            self._send_error(tsock, client_addr, ERR_NOT_FOUND, "File not found")
            tsock.close()
            return

        filesize = os.path.getsize(path)
        blksize = self.default_blksize
        accepted = self._negotiate(opts, filesize=filesize)

        tsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tsock.bind((self.host, 0))
        tsock.settimeout(self.timeout)
        try:
            if accepted:
                if 'blksize' in accepted:
                    blksize = accepted['blksize']

                # Wait for ACK(0). If the client doesn’t send it, fall back to DATA(1).
                if not self._oack(tsock, client_addr,
                                  {k: str(v) for k, v in accepted.items()}):
                    logger.info(
                        "RRQ: no ACK to OACK from %s; falling back to sending DATA(1)",
                        client_addr)

            block = 1

            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(blksize)
                    for attempt in range(self.retries):
                        self._send_data(tsock, client_addr, block, chunk)
                        try:
                            pkt, src = tsock.recvfrom(4 + 64)
                        except socket.timeout:
                            continue

                        if src != client_addr:
                            self._send_error(tsock, src, ERR_UNKNOWN_TID,
                                             "Unknown transfer ID")
                            continue
                        if (len(pkt) >= 4 and pkt[1] == OP_ACK and
                                int.from_bytes(pkt[2:4], 'big') == block):
                            self.ipc._issue_update_sent_bytes_callback(
                                transfer_id=transfer_id,
                                sent_bytes=block * blksize,
                                total_size=filesize)
                            break
                    else:
                        logger.info("RRQ: retries exhausted to %s (block %d)",
                                     client_addr, block)
                        self.ipc._issue_transfer_ended_callback(
                            transfer_id, "retries exhausted")
                        return

                    if len(chunk) < blksize:  # last block
                        return
                    block = (block + 1) & 0xFFFF
                    if block == 0:
                        block = 1
        finally:
            tsock.close()

    def _handle_wrq(self, client_addr: Tuple[str,int], filename: str, mode: str, opts: Dict[str,str]):
        if mode != 'octet':
            logger.info("WRQ rejected: mode %s not supported", mode)
            return
        path = self._safe_path(filename)
        if not path:
            tsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tsock.bind((self.host, 0))
            self._send_error(tsock, client_addr, ERR_ACCESS, "Access violation")
            tsock.close()
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            # Overwrite allowed; change to ERR_EXISTS to forbid
            pass

        blksize = self.default_blksize
        accepted = self._negotiate(opts)
        tsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tsock.bind((self.host, 0))
        tsock.settimeout(self.timeout)

        try:
            if accepted:
                if 'blksize' in accepted:
                    blksize = accepted['blksize']
                if not self._oack(tsock, client_addr, {k:str(v) for k,v in accepted.items()}):
                    logger.info("WRQ: no DATA after OACK from %s", client_addr)
                    return
            else:
                # ACK block 0 to start WRQ without options
                self._send_ack(tsock, client_addr, 0)

            expected = 1
            with open(path, 'wb') as f:
                while True:
                    for attempt in range(self.retries):
                        try:
                            pkt, src = tsock.recvfrom(blksize + 4 + 64)
                        except socket.timeout:
                            continue
                        if src != client_addr:
                            self._send_error(tsock, src, ERR_UNKNOWN_TID, "Unknown transfer ID")
                            continue
                        if len(pkt) >= 4 and pkt[1] == OP_DATA:
                            block = int.from_bytes(pkt[2:4], 'big')
                            data = pkt[4:]
                            if block == expected:
                                f.write(data)
                                self._send_ack(tsock, client_addr, block)
                                if len(data) < blksize:
                                    return  # last block
                                expected = (expected + 1) & 0xFFFF
                                if expected == 0:
                                    expected = 1
                                break
                            else:
                                # duplicate or out-of-order; re-ACK last received
                                self._send_ack(tsock, client_addr, (expected - 1) & 0xFFFF)
                        else:
                            # ignore other packets
                            pass
                    else:
                        logger.info("WRQ: retries exhausted from %s (expect block %d)", client_addr, expected)
                        return
        finally:
            tsock.close()

    def _serve_once(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(1.0)
        # Receive a single RRQ/WRQ on the control socket
        try:
            pkt, addr = self._sock.recvfrom(2048)
        except socket.timeout:
            return
        if len(pkt) < 4:
            return
        try:
            op_req, filename, mode, opts = self._recv_req(pkt)
        except ValueError as e:
            # illegal TFTP operation
            logger.exception("Illegal TFTP operation", exc_info=e)
            es = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            es.bind((self.host, 0))
            self._send_error(es, addr, ERR_ILLEGAL, "Illegal TFTP operation")
            es.close()
            return

        logger.info("%s %s from %s opts=%s",
                     "RRQ" if op_req==OP_RRQ else "WRQ" if op_req==OP_WRQ else str(op_req),
                     filename, addr, opts)

        if op_req == OP_RRQ:
            threading.Thread(target=self._handle_rrq, args=(addr, filename, mode, opts), daemon=True).start()
        elif op_req == OP_WRQ:
            threading.Thread(target=self._handle_wrq, args=(addr, filename, mode, opts), daemon=True).start()
        else:
            es = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            es.bind((self.host, 0))
            self._send_error(es, addr, ERR_ILLEGAL, "Illegal TFTP operation")
            es.close()

    def serve(self):
        logger.info("TFTP listening on %s:%d (root=%s)", self.host, self.port, self.root)
        try:
            while self._running.value:
                self._serve_once()
        finally:
            if self._sock is not None:
                self._sock.close()
