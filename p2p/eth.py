import logging
from typing import (
    cast,
    List,
    Tuple,
    TYPE_CHECKING
)

from rlp import sedes

from eth_typing import (
    BlockIdentifier,
)

from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransactionFields

from p2p.protocol import (
    BaseBlockHeaders,
    Command,
    Protocol,
    _DecodedMsgType,
)
from p2p.rlp import BlockBody
from p2p.sedes import HashOrNumber

if TYPE_CHECKING:
    from p2p.peer import (  # noqa: F401
        ChainInfo
    )


# Max number of items we can ask for in ETH requests. These are the values used in geth and if we
# ask for more than this the peers will disconnect from us.
MAX_STATE_FETCH = 384
MAX_BODIES_FETCH = 128
MAX_RECEIPTS_FETCH = 256
MAX_HEADERS_FETCH = 192


class Status(Command):
    _cmd_id = 0
    structure = [
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('td', sedes.big_endian_int),
        ('best_hash', sedes.binary),
        ('genesis_hash', sedes.binary),
    ]


class NewBlockHashes(Command):
    _cmd_id = 1
    structure = sedes.CountableList(sedes.List([sedes.binary, sedes.big_endian_int]))


class Transactions(Command):
    _cmd_id = 2
    structure = sedes.CountableList(BaseTransactionFields)


class GetBlockHeaders(Command):
    _cmd_id = 3
    structure = [
        ('block_number_or_hash', HashOrNumber()),
        ('max_headers', sedes.big_endian_int),
        ('skip', sedes.big_endian_int),
        ('reverse', sedes.boolean),
    ]


class BlockHeaders(BaseBlockHeaders):
    _cmd_id = 4
    structure = sedes.CountableList(BlockHeader)

    def extract_headers(self, msg: _DecodedMsgType) -> Tuple[BlockHeader, ...]:
        return cast(Tuple[BlockHeader, ...], tuple(msg))


class GetBlockBodies(Command):
    _cmd_id = 5
    structure = sedes.CountableList(sedes.binary)


class BlockBodies(Command):
    _cmd_id = 6
    structure = sedes.CountableList(BlockBody)


class NewBlock(Command):
    _cmd_id = 7
    structure = [
        ('block', sedes.List([BlockHeader,
                              sedes.CountableList(BaseTransactionFields),
                              sedes.CountableList(BlockHeader)])),
        ('total_difficulty', sedes.big_endian_int)]


class GetNodeData(Command):
    _cmd_id = 13
    structure = sedes.CountableList(sedes.binary)


class NodeData(Command):
    _cmd_id = 14
    structure = sedes.CountableList(sedes.binary)


class GetReceipts(Command):
    _cmd_id = 15
    structure = sedes.CountableList(sedes.binary)


class Receipts(Command):
    _cmd_id = 16
    structure = sedes.CountableList(sedes.CountableList(Receipt))


class ETHProtocol(Protocol):
    name = 'eth'
    version = 63
    _commands = [
        Status, NewBlockHashes, Transactions, GetBlockHeaders, BlockHeaders, BlockHeaders,
        GetBlockBodies, BlockBodies, NewBlock, GetNodeData, NodeData,
        GetReceipts, Receipts]
    cmd_length = 17
    logger = logging.getLogger("p2p.eth.ETHProtocol")

    def send_handshake(self, head_info: 'ChainInfo') -> None:
        resp = {
            'protocol_version': self.version,
            'network_id': self.peer.network_id,
            'td': head_info.total_difficulty,
            'best_hash': head_info.block_hash,
            'genesis_hash': head_info.genesis_hash,
        }
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending ETH/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def send_get_node_data(self, node_hashes: List[bytes]) -> None:
        cmd = GetNodeData(self.cmd_id_offset)
        header, body = cmd.encode(node_hashes)
        self.send(header, body)

    def send_node_data(self, nodes: List[bytes]) -> None:
        cmd = NodeData(self.cmd_id_offset)
        header, body = cmd.encode(nodes)
        self.send(header, body)

    def send_get_block_headers(self,
                               block_number_or_hash: BlockIdentifier,
                               max_headers: int,
                               skip: int,
                               reverse: bool,
                               ) -> None:
        """Send a GetBlockHeaders msg to the remote.

        This requests that the remote send us up to max_headers, starting from
        block_number_or_hash if reverse is False or ending at block_number_or_hash if reverse is
        True.
        """
        if max_headers > MAX_HEADERS_FETCH:
            raise ValueError(
                "Cannot ask for more than {} block headers in a single request".format(
                    MAX_HEADERS_FETCH))
        cmd = GetBlockHeaders(self.cmd_id_offset)
        data = {
            'block_number_or_hash': block_number_or_hash,
            'max_headers': max_headers,
            'skip': skip,
            'reverse': reverse}
        header, body = cmd.encode(data)
        self.send(header, body)

    def send_block_headers(self, headers: Tuple[BlockHeader]) -> None:
        cmd = BlockHeaders(self.cmd_id_offset)
        header, body = cmd.encode(headers)
        self.send(header, body)

    def send_get_block_bodies(self, block_hashes: List[bytes]) -> None:
        cmd = GetBlockBodies(self.cmd_id_offset)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)

    def send_block_bodies(self, blocks: List[BlockBody]) -> None:
        cmd = BlockBodies(self.cmd_id_offset)
        header, body = cmd.encode(blocks)
        self.send(header, body)

    def send_get_receipts(self, block_hashes: List[bytes]) -> None:
        cmd = GetReceipts(self.cmd_id_offset)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)

    def send_receipts(self, receipts: List[List[Receipt]]) -> None:
        cmd = Receipts(self.cmd_id_offset)
        header, body = cmd.encode(receipts)
        self.send(header, body)

    def send_transactions(self, transactions: List[BaseTransactionFields]) -> None:
        cmd = Transactions(self.cmd_id_offset)
        header, body = cmd.encode(transactions)
        self.send(header, body)
